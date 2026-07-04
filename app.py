"""
app.py — Flask-бэкенд системы анализа положения мяча.

Маршруты:
  GET  /                      -> веб-интерфейс
  POST /process              -> приём файла, прогон через YOLOv8, JSON-статистика
  GET  /history              -> история запросов (JSON)
  GET  /report/<fmt>/<id>    -> выгрузка отчёта (fmt = pdf | xlsx)
"""

import os
import time
import uuid
from datetime import datetime

import cv2
from flask import (Flask, request, jsonify, render_template,
                   send_from_directory)
from werkzeug.utils import secure_filename

from detector import BallAnalyzer
from database import init_db, add_record, get_history
import report

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE, "static", "uploads")
RESULT_DIR = os.path.join(BASE, "static", "results")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VID_EXT = {".mp4", ".avi", ".mov", ".mkv"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 МБ

analyzer = BallAnalyzer(
    model_path=os.environ.get("YOLO_MODEL", "yolov8n.pt"),
    conf=float(os.environ.get("YOLO_CONF", "0.25")),
)
init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    if "file" not in request.files or not request.files["file"].filename:
        return jsonify(error="Файл не передан"), 400

    f = request.files["file"]
    name = secure_filename(f.filename)
    ext = os.path.splitext(name)[1].lower()
    uid = uuid.uuid4().hex[:8]
    src = os.path.join(UPLOAD_DIR, f"{uid}_{name}")
    f.save(src)

    # порог уверенности можно задать ползунком на странице
    try:
        analyzer.conf = float(request.form.get("conf", analyzer.conf))
    except (TypeError, ValueError):
        pass

    t0 = time.time()
    try:
        if ext in IMG_EXT:
            img = cv2.imread(src)
            if img is None:
                return jsonify(error="Не удалось прочитать изображение"), 400
            annotated, stats = analyzer.analyze_image(img)
            out_name = f"{uid}_result.jpg"
            cv2.imwrite(os.path.join(RESULT_DIR, out_name), annotated)
            media = "image"
        elif ext in VID_EXT:
            out_name = f"{uid}_result.mp4"
            stats = analyzer.analyze_video(
                src, os.path.join(RESULT_DIR, out_name))
            media = "video"
        else:
            return jsonify(error=f"Неподдерживаемый формат: {ext}"), 400
    except Exception as e:
        return jsonify(error=f"Ошибка обработки: {e}"), 500

    rec = {
        "id": uid,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "filename": name,
        "media": media,
        "elapsed": round(time.time() - t0, 2),
        "result_url": f"/static/results/{out_name}",
        "stats": stats,
    }
    add_record(rec)
    return jsonify(rec)


@app.route("/history")
def history():
    return jsonify(get_history(limit=50))


@app.route("/report/<fmt>/<rec_id>")
def make_report(fmt, rec_id):
    rec = report.find_record(rec_id)
    if not rec:
        return jsonify(error="Запись не найдена"), 404
    if fmt == "pdf":
        path = report.build_pdf(rec)
    elif fmt == "xlsx":
        path = report.build_xlsx(rec)
    else:
        return jsonify(error="Формат: pdf или xlsx"), 400
    return send_from_directory(os.path.dirname(path),
                               os.path.basename(path), as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
