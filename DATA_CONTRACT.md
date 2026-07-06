# 数据目录与公开格式规范

## 总原则

- 原始观测 PNG、模型预测 NetCDF、内部脚本和中间结果只放学校服务器。
- GitHub Pages 只发布可公开内容：指标 JSON、脱敏后的典型个例图片或动图。
- 正式榜单指标由统一评估脚本计算，团队成员不直接提交最终榜单指标。

## 学校服务器目录建议

建议部署根目录：

```text
/home/shh/比赛/nowcasting-dashboard/
  private/
    observations/
      radar_png -> /home/shh/data/CMA_radar/2025
    predictions/
      team_alpha/
        model_meta.json
        test/
        realtime/
      team_beta/
        model_meta.json
        test/
        realtime/
    evaluation/
      config/
      intermediate/
      logs/
  public/
    data/
      dashboard.json
    cases/
      case_20250131_043000_obs.png
      case_20250131_043000_team_alpha.gif
      case_20250131_043000_team_beta.gif
  scripts/
```

## 团队预测提交目录

每个团队一个目录：

```text
/home/shh/比赛/nowcasting-dashboard/private/predictions/<team_id>/
  model_meta.json
  test/
    <case_id>.nc
  realtime/
    YYYYMMDD/
      <init_time>.nc
```

`model_meta.json` 建议格式：

```json
{
  "team_id": "team_alpha",
  "model_name": "AlphaNet",
  "owner": "成员A",
  "version": "v0.1",
  "output_unit": "dBZ",
  "lead_interval_minutes": 6,
  "max_lead_minutes": 180,
  "created_at": "2026-07-06T12:00:00+08:00"
}
```

NetCDF 具体变量名等你确认后再固定。建议目标结构为：

```text
reflectivity[lead_time, y, x]
lead_time: minutes since init_time, 6, 12, ..., 180
lat[y] 或二维 lat[y, x]
lon[x] 或二维 lon[y, x]
```

## 公开 dashboard.json

网页读取：

```text
public/data/dashboard.json
```

字段约定见当前示例文件。后续统一评估脚本只需要持续覆盖这个 JSON 和 `public/cases/` 下的公开图片/动图。

## 雷达观测读取

临时可复用：

```text
/home/shh/data/CMA_radar/png_to_reflectivity_visualize.py
/home/shh/data/CMA_radar/PAL.txt
/home/shh/data/CMA_radar/2025
```

该脚本将 CMA 雷达组合反射率 PNG 按 PAL 色标转为 dBZ，并生成 NetCDF/可视化图。第一版网页不会公开原始 PNG，只公开由评估脚本生成的个例图或动图。

