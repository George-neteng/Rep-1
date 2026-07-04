# ⚽ Анализ положения мяча (Computer Vision)

Веб-сервис на **YOLOv8 + Flask + OpenCV** для детекции мяча на фото/видео и
анализа его положения на поле. Выполнено в рамках индивидуального задания
по применению предобученных нейросетей в компьютерном зрении.

## Возможности
- Загрузка **изображения или видео** через веб-интерфейс (drag&drop).
- Детекция мяча (COCO `sports ball`, класс 32) и игроков (`person`, класс 0)
  предобученной моделью YOLOv8 — дообучение не требуется.
- **Анализ положения**:
  - центр мяча в пикселях и в нормированных координатах `[0..1]`;
  - зона поля (сетка 3×3): напр. «верхняя / центральная»;
  - расстояние до ближайшего игрока.
- Для **видео**: трек мяча (хвост траектории), тепловая карта позиций,
  распределение по зонам, видимость мяча (%), пройденный путь в пикселях.
- **История запросов** в SQLite (`history.db`).
- **Отчёты**: выгрузка результата в **PDF** (reportlab) и **Excel** (openpyxl).

## Архитектура
```
app.py        — Flask: маршруты /process, /history, /report
detector.py   — BallAnalyzer: YOLOv8 + анализ положения (фото и видео)
database.py   — SQLite, история запросов
report.py     — генерация PDF / XLSX
templates/    — index.html (интерфейс)
static/       — css, js, uploads, results, reports
deploy/       — systemd, nginx, инструкция
```

## API
| Метод | Маршрут | Описание |
|-------|---------|----------|
| POST | `/process` | файл `file` (+ `conf`) → JSON со статистикой и ссылкой на результат |
| GET  | `/history` | последние запросы (JSON) |
| GET  | `/report/pdf/<id>` | PDF-отчёт по запросу |
| GET  | `/report/xlsx/<id>` | Excel-отчёт по запросу |

Пример ответа `/process` (изображение):
```json
{
  "id": "a1b2c3d4",
  "media": "image",
  "elapsed": 0.42,
  "result_url": "/static/results/a1b2c3d4_result.jpg",
  "stats": {
    "ball_found": true,
    "players": 6,
    "ball_zone": "средняя / центральная",
    "ball_center": [641.0, 372.5],
    "ball_norm": [0.501, 0.517],
    "ball_conf": 0.88,
    "nearest_player_dist_px": 54.3
  }
}
```

## Быстрый старт
```bash
sudo apt install -y ffmpeg fonts-dejavu-core   # видео в H.264 + кириллица в PDF
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py
# http://localhost:5000
```

Развёртывание на сервере (gunicorn + nginx + HTTPS) — см. `deploy/DEPLOY.md`.

## Стек
Python · Flask · Ultralytics YOLOv8 · OpenCV · NumPy · SQLite · reportlab · openpyxl
