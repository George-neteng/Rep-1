# Развёртывание на сервере

## 1. Код и зависимости
```bash
sudo mkdir -p /opt/football-app && sudo chown $USER /opt/football-app
cd /opt/football-app
git clone <URL_вашего_репозитория> .

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# системные пакеты: ffmpeg (перекодирование видео в H.264 для браузера)
# и шрифт с кириллицей для PDF-отчётов
sudo apt install -y ffmpeg fonts-dejavu-core
```

## 2. Предзагрузка весов модели
Чтобы сервис под `www-data` не пытался скачивать веса на первом запросе,
скачайте их заранее и положите рядом с `app.py`:
```bash
source venv/bin/activate
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
# ultralytics положит yolov8n.pt в текущую папку; убедитесь, что он в /opt/football-app
ls -lh yolov8n.pt
sudo chown -R www-data:www-data /opt/football-app
```
Для более точной детекции мелкого мяча можно взять модель побольше:
`YOLO_MODEL=yolov8s.pt` (или `m`/`l`) в unit-файле — тогда предзагрузите её же.

## 3. Проверка локально
```bash
source venv/bin/activate
python app.py            # http://127.0.0.1:5000
```

## 4. systemd + gunicorn
```bash
sudo cp deploy/football-app.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now football-app
sudo systemctl status football-app
```

## 5. nginx + HTTPS
```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/football-app
# впишите свой домен вместо example.com
sudo ln -s /etc/nginx/sites-available/football-app /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d example.com
```

После этого приложение доступно по `https://example.com/`.
