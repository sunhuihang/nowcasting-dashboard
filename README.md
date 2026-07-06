# 短临预报模型评估看板

这个项目用于公开展示气象局比赛短临雷达回波预报模型的客观评估结果。核心原则是：**原始观测 PNG、预测 NetCDF、内部评估中间文件只留在学校服务器；GitHub Pages 只发布可公开的指标 JSON、图片和前端代码。**

## 当前部署位置

学校服务器项目目录：

```text
/home/shh/比赛/nowcasting-dashboard
```

本地 Codex 临时工作副本：

```text
D:\codex_work\tmp\nowcasting-dashboard
```

实际应以服务器目录为准，因为真实观测、预测和公开图片都在服务器上生成，并从服务器推送到 GitHub。

## 公开访问地址

GitHub Pages 已经部署成功，外网访问地址：

```text
https://sunhuihang.github.io/nowcasting-dashboard/
```

GitHub 仓库：

```text
https://github.com/sunhuihang/nowcasting-dashboard
```

当前 Pages 发布方式为 GitHub Actions，发布目录为 `public/`。

## 当前网页功能

- 模型排名表
- 客观评分公式展示
- TS / BIAS / SSIM 总评分表
- TS / BIAS / SSIM 逐 6 分钟折线图
  - 每个指标各 4 张图：20 dBZ、35 dBZ、45 dBZ、阈值综合
  - 每张图中不同颜色代表不同模型
  - x 轴刻度字号已调大，右侧 `180` 和 `min` 分两行显示，避免重叠
- 经典个例
  - 经典个例时间选择，目前为 `2026-07-06 00:00`
  - 播放速度选择：`0.5x / 1x / 2x / 4x`
  - 单帧展示：选择 6-180 min 预报时效
  - 3 小时预报：统一时钟驱动的同步帧播放器，避免多个 GIF 不同步
  - 当前展示 7 路：观测、AccuRadar、Model-02、Model-03、Model-04、Model-05、Model-06

已删除首页顶部 4 个概览卡片：

```text
模型数量
当前最佳
经典个例
评估时效
```

## 重要数据约定

观测数据：

```text
/home/shh/data/CMA_radar/2026/20260706
```

观测为 CMA radar PNG。网页不直接展示原始 PNG，只展示 PAL 色标转换后的组合反射率 dBZ 图。

AccuRadar 预测数据：

```text
/home/shh/比赛/nowcasting-dashboard/private/predictions/AccuRadar/2026/20260706
```

预测为 NetCDF，当前变量结构示例：

```text
data0(time, dtime, member, level, lat, lon)
units: dBZ
lat: 17.0 ... 27.0
lon: 100.0 ... 123.0
```

预测和观测对齐规则：

```text
有效时刻 = 起报时间 + 预报时效
```

例如：

```text
AccuRadar_20260706001401_P_REFMOSAIC_202607060000_006MIN.nc
```

对应观测：

```text
ACHN_CREF_20260706_000600.png
```

注意：预测 nc 的经纬度范围和 PNG 观测网格可能有轻微差异。绘图时统一使用 PNG 的经纬度范围：

```text
lat: 17.0-27.0
lon: 100.0-123.0
resolution: 0.02 degree
```

预测场插值到 PNG 网格后再绘图。

## 客观评分口径

参考《第二届人工智能气象预报模型示范计划技术方案-临近方向.pdf》，当前只做客观评估，不做专家主观评分。

阈值：

```text
20 dBZ, 35 dBZ, 45 dBZ
```

TS：

```text
TS = H / (H + M + F)
```

BIAS：

```text
BIAS = (H + F) / (H + M)
```

SSIM：

```text
SSIM = l(x,y) * c(x,y) * s(x,y)
```

阈值综合：

```text
S = S20 * 0.3 + S35 * 0.4 + S45 * 0.3
```

总评分：

```text
S_total = mean(S_0-1h) * 0.3
        + mean(S_1-2h) * 0.5
        + mean(S_2-3h) * 0.2
```

注意：不是最后除以 30 帧。正确做法是先分别计算 0-1h、1-2h、2-3h 内逐 6 分钟评分的平均值，再按时段权重加权。

当前前端 `public/app.js` 的 `totalScore()` 已按这个逻辑计算。

## 公开文件和私有文件

可以公开到 GitHub Pages：

```text
public/
scripts/
.github/
README.md
DATA_CONTRACT.md
```

不要公开：

```text
private/
*.nc
原始观测 PNG
原始预测 NetCDF
评估中间文件
服务器压缩包
```

建议 `.gitignore` 至少包含：

```gitignore
private/
*.zip
*.nc
__pycache__/
*.pyc
.DS_Store
```

## 关键脚本

生成 AccuRadar 经典个例公开图：

```text
scripts/generate_accu_radar_public_assets.py
```

示例命令：

```bash
cd /home/shh/比赛/nowcasting-dashboard
/home/shh/miniconda3/envs/sunhh/bin/python scripts/generate_accu_radar_public_assets.py \
  --date 20260706 \
  --init-time 202607060000 \
  --obs-dir /home/shh/data/CMA_radar/2026/20260706 \
  --pred-dir /home/shh/比赛/nowcasting-dashboard/private/predictions/AccuRadar/2026/20260706 \
  --public-dir /home/shh/比赛/nowcasting-dashboard/public \
  --workers 16 \
  --dpi 150 \
  --downsample 1
```

脚本当前行为：

- 16 进程并行绘图
- 默认 dpi 150
- 默认不下采样
- 观测 PNG 先按 PAL 转 dBZ
- 预测 nc 插值到 PNG 网格
- 使用 AGENTS.md 中约定的雷达组合反射率离散色标
- colorbar 放在图下方
- 生成 30 个 lead 的公开 PNG
- 生成观测、AccuRadar、5 个占位模型的公开帧与 GIF
- 更新 `public/data/dashboard.json` 的 `radar_cases`

生成 demo 指标数据：

```text
scripts/generate_demo_public_data.py
```

注意：它只生成脱敏示例指标，不读取真实数据。

## GitHub Pages 部署

当前仓库已经从服务器目录推送到 GitHub。GitHub Pages workflow 位于：

```text
.github/workflows/pages.yml
```

GitHub 仓库设置：

```text
Settings -> Pages -> Build and deployment -> Source -> GitHub Actions
```

workflow 会发布：

```text
public/
```

部署状态记录：

- 首次推送已完成，远端分支为 `main`
- GitHub Pages Source 已设置为 `GitHub Actions`
- 第一次 Actions 发布曾在 `actions/deploy-pages@v4` 阶段出现 `Deployment failed, try again later.`
- 通过空提交 `Retry GitHub Pages deployment` 重新触发后部署成功
- 后续如果遇到同类临时失败，通常重新运行 workflow 或推一个小提交即可

服务器到 GitHub 的 HTTPS push 不稳定，当前已经改用 SSH Deploy Key。服务器私钥路径：

```text
/home/shh/.ssh/id_ed25519_nowcasting_dashboard
```

远端地址：

```bash
git@github.com:sunhuihang/nowcasting-dashboard.git
```

后续更新流程建议在服务器执行：

```bash
cd /home/shh/比赛/nowcasting-dashboard
git status --short
git add public scripts .github README.md DATA_CONTRACT.md .gitignore
git commit -m "Update dashboard"
GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519_nowcasting_dashboard' git push
```

提交前务必检查不要包含 `private/`、`.nc`、原始 PNG。

敏感文件检查命令：

```bash
git ls-files | grep -E '(^private/|\.nc$|\.zip$)'
```

如果没有输出，说明当前 Git 跟踪文件中没有这些敏感数据。

`.gitignore` 当前至少应包含：

```gitignore
private/
*.zip
*.nc
__pycache__/
*.pyc
.DS_Store
```

## 当前占位模型

当前网页中已有 6 个评分模型：

```text
AccuRadar
Model-02
Model-03
Model-04
Model-05
Model-06
```

经典个例中展示 7 路：

```text
观测
AccuRadar
Model-02
Model-03
Model-04
Model-05
Model-06
```

目前 Model-02 到 Model-06 的个例图暂时复用 AccuRadar 数据。后续真实模型数据到位后，需要按同一接口生成各自的公开帧。

## 后续 TODO

1. 接入真实评估脚本
   - 统一读取各模型 NetCDF
   - 统一读取 CMA radar PNG
   - 按 `起报时间 + 预报时效 = 观测时刻` 对齐
   - 统一计算 TS、BIAS、SSIM
   - 输出 `public/data/dashboard.json`

2. 支持多个模型真实预报
   - 当前只有 AccuRadar 有真实 nc
   - 后续将 Model-02 到 Model-06 替换为真实模型名和真实预测数据

3. 支持多个经典个例
   - 当前只有 `2026-07-06 00:00`
   - 后续在 `radar_cases` 中追加其他起报时间
   - 前端已经支持按 `经典个例时间` 选择

4. 实时评分
   - 最近 1 天
   - 最近 7 天
   - 最近 30 天
   - 仍然只公开指标 JSON 和公开图，不公开原始数据

5. GitHub Pages 更新自动化
   - 服务器定时生成 `public/data/dashboard.json` 和 `public/cases/`
   - 自动 `git add/commit/push`
   - 注意自动提交前做敏感文件检查

6. 清理旧占位资产
   - 早期遗留的 `public/cases/accuradar_202607060000/lead_*.png`
   - 早期 `accuradar_compare.gif`
   - 如果前端不再引用，可以删除，减小仓库体积

## 后续继续工作提示

如果新开 Codex 窗口，请先让 Codex 读取：

```text
/home/shh/比赛/nowcasting-dashboard/README.md
/home/shh/比赛/nowcasting-dashboard/DATA_CONTRACT.md
/home/shh/比赛/nowcasting-dashboard/scripts/generate_accu_radar_public_assets.py
/home/shh/比赛/nowcasting-dashboard/public/data/dashboard.json
```

并提醒：

- 默认中文回复
- 不要修改服务器 Python 环境
- 原始数据不进 GitHub
- 绘图使用 PNG 观测网格范围
- 预测按起报时间加 lead 对齐观测
- 降水/雷达绘图遵守 AGENTS.md 的气象配色规范
