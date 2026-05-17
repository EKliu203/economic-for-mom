#!/bin/bash
# 每日财经新闻爬取调度器启动脚本
# 用法: ./run_scheduler.sh

cd "$(dirname "$0")"
mkdir -p logs

if [ ! -d ".venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

echo "启动财经新闻爬取调度器..."
nohup python src/scheduler.py > logs/scheduler.out 2>&1 &
echo "调度器已在后台启动 (PID: $!)"
echo "查看日志: tail -f logs/scheduler.log"
