#!/usr/bin/env python3
"""
生成 AccuRadar 预报与 CMA 雷达观测对齐后的公开展示图。

示例命令：
    python scripts/generate_accu_radar_public_assets.py \
        --date 20260706 \
        --init-time 202607060000 \
        --obs-dir /home/shh/data/CMA_radar/2026/20260706 \
        --pred-dir /home/shh/比赛/nowcasting-dashboard/private/predictions/AccuRadar/2026/20260706 \
        --public-dir /home/shh/比赛/nowcasting-dashboard/public

说明：
    预测文件按“起报时间 + 预报时效 = 观测时刻”对齐。
    例如 AccuRadar_..._202607060000_006MIN.nc 对应 ACHN_CREF_20260706_000600.png。
    输出图只包含 PAL 转换后的 dBZ 观测和预测，不公开原始 PNG 或 NetCDF。
"""

from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from PIL import Image

try:
    import imageio.v2 as imageio
except Exception:  # pragma: no cover
    imageio = None


LAT_MIN = 17.0
LAT_MAX = 27.0
LON_MIN = 100.0
LON_MAX = 123.0
RESOLUTION = 0.02
LEAD_MINUTES = list(range(6, 181, 6))


def parse_pal(pal_path: Path) -> dict[tuple[int, int, int], float]:
    mapping: dict[tuple[int, int, int], float] = {}
    pattern = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*=\s*(\d+)\s+(\d+)\s+(\d+)")
    for line in pal_path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        value = float(match.group(1))
        rgb = tuple(int(match.group(i)) for i in range(2, 5))
        mapping[rgb] = value
    if not mapping:
        raise ValueError(f"未能从 {pal_path} 解析 PAL 色标")
    return mapping


def radar_cmap() -> tuple[mpl.colors.ListedColormap, mpl.colors.BoundaryNorm]:
    levs = np.array([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75])
    cols = np.array(
        [
            (255, 255, 255),
            (102, 255, 255),
            (86, 225, 250),
            (0, 162, 232),
            (3, 207, 14),
            (26, 152, 7),
            (255, 242, 0),
            (217, 172, 113),
            (255, 147, 74),
            (255, 0, 0),
            (204, 0, 0),
            (155, 0, 0),
            (236, 21, 236),
            (130, 11, 130),
            (184, 108, 208),
        ],
        dtype=np.float32,
    ) / 255.0
    cmap = mpl.colors.ListedColormap(cols)
    cmap.set_bad("white")
    cmap.set_under("white")
    norm = mpl.colors.BoundaryNorm(levs, cmap.N)
    return cmap, norm


def png_grid(shape: tuple[int, int], downsample: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    height, width = shape
    lat_desc = LAT_MAX - np.arange(height, dtype=np.float64) * RESOLUTION
    if downsample > 1:
        lat_desc = lat_desc[::downsample]
    lat_asc = lat_desc[::-1]
    lon = LON_MIN + np.arange(width, dtype=np.float64) * RESOLUTION
    if downsample > 1:
        lon = lon[::downsample]
    return lat_desc, lat_asc, lon


def png_to_dbz(png_path: Path, rgb_to_value: dict[tuple[int, int, int], float]) -> np.ndarray:
    rgb = np.asarray(Image.open(png_path).convert("RGB"), dtype=np.uint8)
    values = np.full(rgb.shape[:2], np.nan, dtype=np.float32)
    for color, dbz in rgb_to_value.items():
        values[np.all(rgb == np.asarray(color, dtype=np.uint8), axis=-1)] = dbz
    return values


def downsample_field(values: np.ndarray, downsample: int) -> np.ndarray:
    if downsample <= 1:
        return values
    return values[::downsample, ::downsample]


def parse_pred_file(path: Path) -> tuple[datetime, int]:
    match = re.search(r"_(\d{12})_(\d{3})MIN\.nc$", path.name)
    if match is None:
        raise ValueError(f"预测文件名无法解析起报时间和时效: {path.name}")
    init_time = datetime.strptime(match.group(1), "%Y%m%d%H%M")
    lead_minute = int(match.group(2))
    return init_time, lead_minute


def obs_path_for(obs_dir: Path, valid_time: datetime) -> Path:
    return obs_dir / f"ACHN_CREF_{valid_time:%Y%m%d_%H%M%S}.png"


def pred_file_for(pred_dir: Path, init_time: datetime, lead_minute: int) -> Path:
    pattern = f"*_{init_time:%Y%m%d%H%M}_{lead_minute:03d}MIN.nc"
    matches = sorted(pred_dir.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"未找到预测文件: {pred_dir}/{pattern}")
    return matches[0]


def read_prediction_on_png_grid(nc_path: Path, lat_asc: np.ndarray, lon: np.ndarray) -> np.ndarray:
    ds = xr.open_dataset(nc_path)
    var_name = "data0" if "data0" in ds.data_vars else next(iter(ds.data_vars))
    da = ds[var_name].squeeze(drop=True)
    if "lat" not in da.dims or "lon" not in da.dims:
        raise ValueError(f"{nc_path} 中变量 {var_name} 不含 lat/lon 维度")
    da = da.sortby("lat").sortby("lon")
    da = da.interp(lat=lat_asc, lon=lon, kwargs={"fill_value": np.nan})
    return da.values.astype(np.float32)


def plot_single_field(
    field: np.ndarray,
    lat_asc: np.ndarray,
    lon: np.ndarray,
    title: str,
    subtitle: str,
    output_path: Path,
    dpi: int,
) -> None:
    cmap, norm = radar_cmap()
    plt.rcParams["font.family"] = ["Times New Roman", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(1, 1, figsize=(6.2, 5.4), constrained_layout=True)
    mesh = ax.pcolormesh(lon, lat_asc, field, cmap=cmap, norm=norm, shading="nearest")
    ax.set_title(subtitle, fontsize=18)
    ax.set_xlim(LON_MIN, LON_MAX)
    ax.set_ylim(LAT_MIN, LAT_MAX)
    ax.set_aspect("equal")
    ax.set_xlabel("经度", fontsize=16)
    ax.set_ylabel("纬度", fontsize=16)
    ax.tick_params(labelsize=14)
    ax.grid(True, linestyle="--", linewidth=0.35, alpha=0.35)

    cbar = fig.colorbar(
        mesh,
        ax=ax,
        orientation="horizontal",
        fraction=0.08,
        pad=0.1,
        ticks=np.arange(0, 80, 5),
    )
    cbar.set_label("dBZ")
    cbar.ax.tick_params(labelsize=13)
    cbar.ax.yaxis.label.set_size(15)
    fig.suptitle(title, fontsize=17)
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)


def make_gif(frame_paths: list[Path], output_path: Path, fps: float) -> None:
    if imageio is None:
        images = [Image.open(path).convert("P", palette=Image.Palette.ADAPTIVE) for path in frame_paths]
        images[0].save(output_path, save_all=True, append_images=images[1:], duration=int(1000 / fps), loop=0)
        return
    frames = [imageio.imread(path) for path in frame_paths]
    imageio.mimsave(output_path, frames, duration=1 / fps, loop=0)


def update_dashboard(public_dir: Path, init_time: datetime, case_items: list[dict]) -> None:
    dashboard_path = public_dir / "data" / "dashboard.json"
    data = json.loads(dashboard_path.read_text(encoding="utf-8"))
    data["radar_cases"] = case_items
    data["radar_case"] = case_items[1] if len(case_items) > 1 else case_items[0]
    dashboard_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_frame_task(args: argparse.Namespace, init_time: datetime, lead_minute: int) -> dict:
    valid_time = init_time + timedelta(minutes=lead_minute)
    return {
        "lead_minute": lead_minute,
        "valid_time": valid_time,
        "obs_png": obs_path_for(args.obs_dir, valid_time),
        "pred_nc": pred_file_for(args.pred_dir, init_time, lead_minute),
        "pal": args.pal,
        "case_dir": args.public_dir / "cases" / f"accuradar_{args.init_time}",
        "init_time": init_time,
        "downsample": args.downsample,
        "dpi": args.dpi,
    }


def render_frame_task(task: dict) -> dict:
    rgb_to_value = parse_pal(task["pal"])
    obs_png: Path = task["obs_png"]
    pred_nc: Path = task["pred_nc"]
    if not obs_png.exists():
        raise FileNotFoundError(f"缺少对齐观测 PNG: {obs_png}")

    obs_dbz = png_to_dbz(obs_png, rgb_to_value)
    obs_dbz = downsample_field(obs_dbz, task["downsample"])
    _, lat_asc, lon = png_grid(obs_dbz.shape, task["downsample"])
    pred_dbz = read_prediction_on_png_grid(pred_nc, lat_asc, lon)

    lead_minute = task["lead_minute"]
    init_time = task["init_time"]
    valid_time = task["valid_time"]
    title = f"Init {init_time:%Y-%m-%d %H:%M}  Lead {lead_minute:03d} min  Valid {valid_time:%Y-%m-%d %H:%M}"
    obs_plot = obs_dbz[::-1, :]
    outputs = {}
    fields = {
        "obs": ("观测 dBZ", obs_plot),
        "accuradar": ("AccuRadar dBZ", pred_dbz),
        "model_02": ("Model-02 dBZ", pred_dbz),
        "model_03": ("Model-03 dBZ", pred_dbz),
        "model_04": ("Model-04 dBZ", pred_dbz),
        "model_05": ("Model-05 dBZ", pred_dbz),
        "model_06": ("Model-06 dBZ", pred_dbz),
    }
    for key, (subtitle, field) in fields.items():
        frame_path = task["case_dir"] / key / f"lead_{lead_minute:03d}.png"
        frame_path.parent.mkdir(parents=True, exist_ok=True)
        plot_single_field(field, lat_asc, lon, title, subtitle, frame_path, task["dpi"])
        outputs[key] = str(frame_path)
    return {
        "lead_minute": lead_minute,
        "valid_time": valid_time.strftime("%Y-%m-%d %H:%M"),
        "outputs": outputs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 AccuRadar 观测/预测公开对比图")
    parser.add_argument("--date", required=True, help="观测日期 YYYYMMDD")
    parser.add_argument("--init-time", required=True, help="起报时间 YYYYMMDDHHMM")
    parser.add_argument("--obs-dir", type=Path, required=True)
    parser.add_argument("--pred-dir", type=Path, required=True)
    parser.add_argument("--public-dir", type=Path, required=True)
    parser.add_argument("--pal", type=Path, default=Path("/home/shh/data/CMA_radar/PAL.txt"))
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--workers", type=int, default=16, help="并行绘图进程数，默认 16")
    parser.add_argument("--dpi", type=int, default=150, help="输出 PNG dpi，默认 150")
    parser.add_argument("--downsample", type=int, default=1, help="空间下采样倍数，默认 1 表示不下采样")
    args = parser.parse_args()

    init_time = datetime.strptime(args.init_time, "%Y%m%d%H%M")
    case_dir = args.public_dir / "cases" / f"accuradar_{args.init_time}"
    case_dir.mkdir(parents=True, exist_ok=True)

    tasks = [build_frame_task(args, init_time, lead_minute) for lead_minute in LEAD_MINUTES]
    frame_results: list[dict] = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(render_frame_task, task) for task in tasks]
        for future in as_completed(futures):
            result = future.result()
            frame_results.append(result)
            print(f"saved lead: {result['lead_minute']:03d} min")

    frame_results.sort(key=lambda item: item["lead_minute"])
    case_defs = [
        ("obs", "观测", "observation"),
        ("accuradar", "AccuRadar", "forecast"),
        ("model_02", "Model-02", "forecast"),
        ("model_03", "Model-03", "forecast"),
        ("model_04", "Model-04", "forecast"),
        ("model_05", "Model-05", "forecast"),
        ("model_06", "Model-06", "forecast"),
    ]
    case_items = []
    for key, model_name, kind in case_defs:
        frame_paths = [Path(item["outputs"][key]) for item in frame_results]
        gif_path = case_dir / key / f"{key}_loop.gif"
        make_gif(frame_paths, gif_path, args.fps)
        frame_items = [
            {
                "lead_minute": item["lead_minute"],
                "valid_time": item["valid_time"],
                "src": f"./cases/accuradar_{args.init_time}/{key}/lead_{item['lead_minute']:03d}.png",
            }
            for item in frame_results
        ]
        case_items.append(
            {
                "model_name": model_name,
                "kind": kind,
                "init_time": init_time.strftime("%Y-%m-%d %H:%M"),
                "lead_frames": frame_items,
                "animation": {
                    "type": "gif",
                    "src": f"./cases/accuradar_{args.init_time}/{key}/{gif_path.name}",
                    "label": f"{model_name} {init_time:%Y-%m-%d %H:%M} 6-180 min 动画",
                },
            }
        )
        print(f"saved gif: {gif_path}")
    update_dashboard(args.public_dir, init_time, case_items)
    print(f"updated dashboard: {args.public_dir / 'data' / 'dashboard.json'}")


if __name__ == "__main__":
    main()
