#!/usr/bin/env bash
# 用途：在学校服务器创建短临预报评估看板的推荐目录结构。
# 示例命令：
#   bash scripts/setup_server_dirs.sh /home/shh/比赛/nowcasting-dashboard

set -euo pipefail

ROOT="${1:-/home/shh/比赛/nowcasting-dashboard}"

mkdir -p "$ROOT/private/observations"
mkdir -p "$ROOT/private/predictions"
mkdir -p "$ROOT/private/evaluation/config"
mkdir -p "$ROOT/private/evaluation/intermediate"
mkdir -p "$ROOT/private/evaluation/logs"
mkdir -p "$ROOT/public/data"
mkdir -p "$ROOT/public/cases"
mkdir -p "$ROOT/scripts"

if [ ! -e "$ROOT/private/observations/radar_png" ]; then
  ln -s /home/shh/data/CMA_radar/2025 "$ROOT/private/observations/radar_png"
fi

echo "created: $ROOT"

