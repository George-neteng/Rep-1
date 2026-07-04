"""
detector.py — детекция и анализ положения мяча на основе YOLOv8.

В датасете COCO предобученная yolov8*.pt уже умеет находить нужные классы:
    32 — sports ball (мяч)
     0 — person     (игрок)

Класс BallAnalyzer:
  * analyze_image(img)            -> (аннотированное изображение, статистика)
  * analyze_video(in, out, ...)   -> статистика по ролику + трек/тепловая карта
"""

import os
import shutil
import subprocess

import cv2
import numpy as np
from ultralytics import YOLO

BALL_CLASS = 32
PERSON_CLASS = 0

# Подписи зон поля при делении кадра на сетку 3x3
COL_LABELS = ["левая", "центральная", "правая"]
ROW_LABELS = ["верхняя", "средняя", "нижняя"]


class BallAnalyzer:
    def __init__(self, model_path="yolov8n.pt", conf=0.25):
        # Веса скачиваются автоматически при первом запуске (ultralytics)
        self.model = YOLO(model_path)
        self.conf = conf

    # ---------- вспомогательное ----------

    def _zone(self, cx, cy, w, h):
        """Возвращает читаемое имя зоны и индексы (row, col) для сетки 3x3."""
        col = min(int(cx / w * 3), 2)
        row = min(int(cy / h * 3), 2)
        return f"{ROW_LABELS[row]} / {COL_LABELS[col]}", (row, col)

    def _draw_overlay(self, img, cx, cy, w, h, zone_latin=""):
        """Рисует сетку зон, перекрестие на мяче и подпись зоны.
        Подписи латиницей — OpenCV не умеет кириллицу в putText."""
        for i in (1, 2):
            cv2.line(img, (int(w / 3 * i), 0), (int(w / 3 * i), h), (255, 255, 0), 1)
            cv2.line(img, (0, int(h / 3 * i)), (w, int(h / 3 * i)), (255, 255, 0), 1)
        cv2.drawMarker(img, (int(cx), int(cy)), (0, 0, 255), cv2.MARKER_CROSS, 28, 2)
        cv2.circle(img, (int(cx), int(cy)), 18, (0, 0, 255), 2)
        if zone_latin:
            cv2.putText(img, f"Zone: {zone_latin}", (10, h - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return img

    @staticmethod
    def _zone_latin(row, col):
        rl = ["top", "mid", "bot"][row]
        cl = ["left", "center", "right"][col]
        return f"{rl}/{cl}"

    def _dominant_zone(self, zc):
        if zc.sum() == 0:
            return "мяч не обнаружен"
        idx = np.unravel_index(int(np.argmax(zc)), zc.shape)
        return f"{ROW_LABELS[idx[0]]} / {COL_LABELS[idx[1]]}"

    # ---------- изображение ----------

    def analyze_image(self, img):
        h, w = img.shape[:2]
        results = self.model(img, conf=self.conf,
                             classes=[BALL_CLASS, PERSON_CLASS], verbose=False)
        r = results[0]
        annotated = r.plot()  # рамки + подписи классов

        balls, players = [], []
        for box in r.boxes:
            cls = int(box.cls[0])
            xyxy = box.xyxy[0].cpu().numpy()
            cx = float((xyxy[0] + xyxy[2]) / 2)
            cy = float((xyxy[1] + xyxy[3]) / 2)
            conf = float(box.conf[0])
            item = {"bbox": [round(float(v), 1) for v in xyxy],
                    "center": (cx, cy), "conf": conf}
            if cls == BALL_CLASS:
                balls.append(item)
            elif cls == PERSON_CLASS:
                players.append(item)

        stats = {
            "width": w,
            "height": h,
            "players": len(players),
            "ball_found": len(balls) > 0,
        }

        if balls:
            ball = max(balls, key=lambda b: b["conf"])
            cx, cy = ball["center"]
            zone_name, (row, col) = self._zone(cx, cy, w, h)
            stats.update({
                "ball_center": [round(cx, 1), round(cy, 1)],
                "ball_norm": [round(cx / w, 3), round(cy / h, 3)],
                "ball_zone": zone_name,
                "ball_zone_idx": [row, col],
                "ball_conf": round(ball["conf"], 3),
            })
            if players:
                d = [float(np.hypot(cx - p["center"][0], cy - p["center"][1]))
                     for p in players]
                stats["nearest_player_dist_px"] = round(min(d), 1)
            annotated = self._draw_overlay(annotated, cx, cy, w, h,
                                           self._zone_latin(row, col))

        return annotated, stats

    # ---------- видео ----------

    def analyze_video(self, in_path, out_path, frame_stride=2, max_frames=None):
        cap = cv2.VideoCapture(in_path)
        if not cap.isOpened():
            raise RuntimeError("Не удалось открыть видеофайл")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out_fps = max(fps / max(frame_stride, 1), 1.0)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(out_path, fourcc, out_fps, (w, h))

        trajectory = []                       # центры мяча по обработанным кадрам
        zone_counts = np.zeros((3, 3), dtype=int)
        heat = np.zeros((h, w), dtype=np.float32)
        frame_idx = total = with_ball = 0

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % frame_stride != 0:
                frame_idx += 1
                continue
            total += 1

            r = self.model(frame, conf=self.conf,
                           classes=[BALL_CLASS, PERSON_CLASS], verbose=False)[0]
            annotated = r.plot()

            best = None
            for box in r.boxes:
                if int(box.cls[0]) == BALL_CLASS:
                    c = float(box.conf[0])
                    if best is None or c > best[2]:
                        xyxy = box.xyxy[0].cpu().numpy()
                        best = (float((xyxy[0] + xyxy[2]) / 2),
                                float((xyxy[1] + xyxy[3]) / 2), c)

            if best:
                cx, cy, _ = best
                trajectory.append((cx, cy))
                with_ball += 1
                col = min(int(cx / w * 3), 2)
                row = min(int(cy / h * 3), 2)
                zone_counts[row, col] += 1
                cv2.circle(heat, (int(cx), int(cy)), 25, 1.0, -1)
                annotated = self._draw_overlay(annotated, cx, cy, w, h,
                                               self._zone_latin(row, col))
                # рисуем «хвост» траектории
                for j in range(1, len(trajectory)):
                    p1 = tuple(map(int, trajectory[j - 1]))
                    p2 = tuple(map(int, trajectory[j]))
                    cv2.line(annotated, p1, p2, (0, 140, 255), 2)

            writer.write(annotated)
            frame_idx += 1
            if max_frames and total >= max_frames:
                break

        cap.release()
        writer.release()

        # OpenCV пишет mp4v — многие браузеры его не проигрывают в <video>.
        # Если есть ffmpeg, перекодируем в H.264 (yuv420p + faststart).
        _reencode_h264(out_path)

        # пройденная мячом дистанция (в пикселях)
        dist = 0.0
        for j in range(1, len(trajectory)):
            dist += float(np.hypot(trajectory[j][0] - trajectory[j - 1][0],
                                   trajectory[j][1] - trajectory[j - 1][1]))

        heat_path = out_path.rsplit(".", 1)[0] + "_heat.jpg"
        self._save_heatmap(heat, heat_path)

        return {
            "frames_processed": total,
            "frames_with_ball": with_ball,
            "ball_visibility_pct": round(100 * with_ball / max(total, 1), 1),
            "ball_distance_px": round(dist, 1),
            "zone_distribution": zone_counts.tolist(),
            "dominant_zone": self._dominant_zone(zone_counts),
            "heatmap_url": "/static/" + heat_path.split("static/", 1)[-1]
                           if "static/" in heat_path else heat_path,
        }

    @staticmethod
    def _save_heatmap(heat, path):
        if heat.max() > 0:
            heat = heat / heat.max()
        heat_u8 = (heat * 255).astype(np.uint8)
        heat_u8 = cv2.GaussianBlur(heat_u8, (0, 0), 9)
        color = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
        cv2.imwrite(path, color)


def _reencode_h264(path):
    """Перекодирует mp4v -> H.264 через ffmpeg, если он установлен.
    Без ffmpeg ролик остаётся в mp4v (файл валиден, но может не играть в браузере)."""
    if not shutil.which("ffmpeg"):
        return
    tmp = path + ".tmp.mp4"
    cmd = ["ffmpeg", "-y", "-i", path, "-c:v", "libx264",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", tmp]
    try:
        subprocess.run(cmd, check=True, timeout=600,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
