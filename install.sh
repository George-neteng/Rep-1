#!/usr/bin/env bash
set -e
python3 -m venv venv
source venv/bin/activate
pip install --no-cache-dir --upgrade pip
# CPU-сборка torch: сервер без GPU, иначе pip тянет ~2 ГБ CUDA-пакетов
pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install --no-cache-dir -r requirements.txt
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
echo "Готово. Активируйте окружение: source venv/bin/activate"
