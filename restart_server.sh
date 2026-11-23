#!/usr/bin/env bash
set -e

APP_DIR="/home/raspberrypi3/stock_app"
VENV_PYTHON="/home/raspberrypi3/stock_app/venv/bin/python"
LOG_DIR="/home/raspberrypi3/stock_app/logs"
LOG_FILE="$LOG_DIR/runserver.log"

mkdir -p "$LOG_DIR"
cd "$APP_DIR"

echo "Stopping existing runserver processes..."
# 既存の runserver 関連プロセスを停止（自分自身やスクリプト名は除外）
pkill -f "manage.py runserver" || true
sleep 1

# もし残っていたら強制終了
if pgrep -f "manage.py runserver" >/dev/null 2>&1; then
    pkill -9 -f "manage.py runserver" || true
    sleep 1
fi

echo "Starting runserver with nohup..."
nohup "$VENV_PYTHON" manage.py runserver 0.0.0.0:8000 >> "$LOG_FILE" 2>&1 &

sleep 1
ps aux | grep "[m]anage.py runserver" || true
echo "Done. Log: $LOG_FILE"