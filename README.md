# 短临预报模型评估看板

这个项目用于公开展示短临雷达回波预报模型的客观评估结果。原始观测、模型 NetCDF 预测文件和内部评估过程留在学校服务器；GitHub Pages 只发布可公开的指标 JSON、缩略图和动图。

## 第一版目标

- 展示多个模型的 TS、BIAS、SSIM 对比
- 支持测试集、最近 1 天、最近 7 天、最近 30 天视角
- 展示 20、35、45 dBZ 阈值下的客观评分
- 展示典型个例的观测和各模型预报动图
- 通过 GitHub Pages 对外访问

## 客观评估口径

根据《第二届人工智能气象预报模型示范计划技术方案-临近方向.pdf》，第一版只纳入客观评估，不纳入专家主观评分。

- 检验对象：组合反射率
- 检验区域：中国南部
- 检验时效：0-3 小时，逐 6 分钟
- 阈值：20、35、45 dBZ
- TS：`H / (H + M + F)`
- BIAS：`(H + F) / (H + M)`
- SSIM：按全时序计算并展示
- 综合 TS 阈值权重：`TS20 * 0.3 + TS35 * 0.4 + TS45 * 0.3`
- 综合时效权重：`0-1h * 0.3 + 1-2h * 0.5 + 2-3h * 0.2`
- 综合 BIAS：按 20 dBZ 阈值计算

## 推荐服务器目录

见 [DATA_CONTRACT.md](./DATA_CONTRACT.md)。

## 本地预览

直接打开：

```bash
public/index.html
```

或者在项目根目录运行：

```bash
python -m http.server 8080 -d public
```

访问：

```text
http://127.0.0.1:8080/
```

## GitHub Pages

仓库推送到 GitHub 后，在仓库设置中：

```text
Settings -> Pages -> Build and deployment -> Source -> GitHub Actions
```

然后每次 push 到 `main`，`.github/workflows/pages.yml` 会自动发布 `public/`。

