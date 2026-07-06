#!/usr/bin/env python3
"""
生成短临预报评估看板的公开示例数据。

示例命令：
    python scripts/generate_demo_public_data.py --output public/data/dashboard.json

说明：
    这个脚本只生成脱敏示例 JSON，不读取原始雷达 PNG 或模型 NetCDF。
    后续接入真实评估脚本时，可以保持 public/data/dashboard.json 的字段结构不变。
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path


THRESHOLDS = [20, 35, 45]
LEAD_MINUTES = list(range(6, 181, 6))
MODELS = [
    ("accuradar", "AccuRadar", "demo", 0.70, 1.02, 0.80),
    ("model_02", "Model-02", "demo", 0.68, 1.14, 0.77),
    ("model_03", "Model-03", "demo", 0.64, 0.93, 0.82),
    ("model_04", "Model-04", "demo", 0.66, 1.08, 0.76),
    ("model_05", "Model-05", "demo", 0.62, 0.97, 0.79),
    ("model_06", "Model-06", "demo", 0.65, 1.04, 0.74),
]


def average(values: list[float]) -> float:
    return sum(values) / len(values)


def build_lead_metrics(base_ts: float, base_bias: float, base_ssim: float, model_shift: float) -> list[dict]:
    rows = []
    for lead in LEAD_MINUTES:
        decay = (lead - 6) / 174
        wave = math.sin(lead / 18 + model_shift) * 0.012
        ts = {}
        bias = {}
        for threshold, penalty in [(20, 0.00), (35, 0.16), (45, 0.29)]:
            ts_value = base_ts - penalty - 0.14 * decay + wave
            ts[str(threshold)] = round(max(0.05, min(0.95, ts_value)), 3)

            bias_wave = math.cos(lead / 24 + threshold / 30 + model_shift) * 0.035
            bias[str(threshold)] = round(max(0.35, min(1.85, base_bias + bias_wave - (threshold - 20) * 0.003 + decay * 0.035)), 3)

        ssim = round(max(0.1, min(0.95, base_ssim - 0.16 * decay + math.sin(lead / 30 + model_shift) * 0.01)), 3)
        rows.append({"lead_minute": lead, "ts": ts, "bias": bias, "ssim": ssim})
    return rows


def build_results() -> list[dict]:
    results = []
    for idx, (team_id, model_name, version, base_ts, base_bias, base_ssim) in enumerate(MODELS):
        lead_metrics = build_lead_metrics(base_ts, base_bias, base_ssim, idx * 0.8)
        summary_ts = {
            str(threshold): round(average([row["ts"][str(threshold)] for row in lead_metrics]), 3)
            for threshold in THRESHOLDS
        }
        summary_bias = {
            str(threshold): round(average([row["bias"][str(threshold)] for row in lead_metrics]), 3)
            for threshold in THRESHOLDS
        }
        summary_ssim = round(average([row["ssim"] for row in lead_metrics]), 3)
        composite_ts = round(summary_ts["20"] * 0.3 + summary_ts["35"] * 0.4 + summary_ts["45"] * 0.3, 3)
        results.append(
            {
                "team_id": team_id,
                "model_name": model_name,
                "version": version,
                "summary": {
                    "ts": summary_ts,
                    "bias": summary_bias,
                    "ssim": summary_ssim,
                    "composite_ts": composite_ts,
                },
                "lead_metrics": lead_metrics,
            }
        )
    return results


def build_demo() -> dict:
    tz = timezone(timedelta(hours=8))
    results = build_results()
    return {
        "dataset_version": "demo-radar-2025",
        "updated_at": datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %z"),
        "thresholds": THRESHOLDS,
        "lead_minutes": LEAD_MINUTES,
        "periods": [
            {"id": "test", "label": "测试集"},
            {"id": "last_1d", "label": "最近 1 天"},
            {"id": "last_7d", "label": "最近 7 天"},
            {"id": "last_30d", "label": "最近 30 天"},
        ],
        "models": [
            {"team_id": team_id, "model_name": model_name, "version": version}
            for team_id, model_name, version, *_ in MODELS
        ],
        "results": {
            "test": results,
            "last_1d": results,
            "last_7d": results,
            "last_30d": results,
        },
        "spatial_sample": {
            "src": "./cases/radar_spatial_sample.svg",
            "caption": "CMA radar sample: ACHN_CREF_20250131_043000, dBZ colormap",
        },
        "cases": [
            {
                "case_id": "case_20250131_043000",
                "title": "2025-01-31 04:30",
                "tags": ["强回波", "位相偏移"],
                "media": [
                    {"label": "观测", "src": "./cases/case_demo_obs.svg"},
                    {"label": "AlphaNet", "src": "./cases/case_demo_alpha.svg"},
                    {"label": "BetaFlow", "src": "./cases/case_demo_beta.svg"},
                ],
            },
            {
                "case_id": "case_20250131_150600",
                "title": "2025-01-31 15:06",
                "tags": ["较强对流", "范围偏差"],
                "media": [
                    {"label": "观测", "src": "./cases/case_demo_obs.svg"},
                    {"label": "AlphaNet", "src": "./cases/case_demo_alpha.svg"},
                    {"label": "GammaRadar", "src": "./cases/case_demo_gamma.svg"},
                ],
            },
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 dashboard.json 示例数据")
    parser.add_argument("--output", type=Path, default=Path("public/data/dashboard.json"))
    args = parser.parse_args()

    data = build_demo()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved: {args.output}")


if __name__ == "__main__":
    main()
