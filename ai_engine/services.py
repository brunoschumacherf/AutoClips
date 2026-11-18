import wave

import cv2
import numpy as np
from django.conf import settings

from .providers import provider


def audio_energy(path):
    with wave.open(str(path), "rb") as audio:
        rate = audio.getframerate()
        values = []
        while data := audio.readframes(rate):
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768
            values.append(round(float(np.sqrt(np.mean(samples ** 2))), 4))
    return values


def visual_signals(path, duration):
    capture = cv2.VideoCapture(str(path))
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    motion, faces, scenes = [], [], []
    previous = None
    try:
        for second in range(0, int(duration) + 1, max(2, int(duration) // 120)):
            capture.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
            readable, image = capture.read()
            if not readable:
                continue
            image = cv2.resize(image, (320, 180))
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            if previous is not None:
                change = float(cv2.absdiff(previous, gray).mean())
                motion.append([second, round(change, 2)])
                if change >= 34:
                    scenes.append(second)
            previous = gray
            boxes = detector.detectMultiScale(gray, 1.15, 5, minSize=(28, 28))
            if len(boxes):
                x, _, width, _ = max(boxes, key=lambda box: box[2] * box[3])
                faces.append([second, round((x + width / 2) / 320, 3)])
    finally:
        capture.release()
    return motion, faces, scenes


def suggestions(video, segments, energy, motion):
    duration = video.duration
    minimum = min(duration, video.options["minimum"])
    maximum = min(duration, video.options["maximum"])
    scorer = provider()
    candidates = []
    stride = max(1, len(segments) // 180)
    starts = [segment.start for segment in segments[::stride] if segment.start + minimum <= duration]
    starts = sorted(set([0, *starts, *range(0, max(1, int(duration - minimum)), max(1, int(maximum // 2)))]))
    for start in starts:
        eligible = [segment for segment in segments if segment.start >= start and segment.end <= start + maximum]
        endings = [segment.end for segment in eligible if segment.end - start >= minimum]
        end = endings[-1] if endings else min(duration, start + maximum)
        included = [segment for segment in eligible if segment.end <= end]
        text = " ".join(segment.text for segment in included)
        sample = energy[int(start):max(int(start) + 1, int(end) + 1)]
        movement = [change for second, change in motion if start <= second <= end]
        components = {
            "semantic": scorer.score(text),
            "audio": min(100, round((max(sample, default=0) * 0.55 + (sum(sample) / max(len(sample), 1)) * 0.45) * 420)),
            "visual": min(100, round(max(movement, default=0) * 3)),
            "context": 90 if text.endswith((".", "!", "?")) else (55 if text else 20),
            "technical": 90 if video.height >= 720 else 60,
        }
        weights = settings.SCORE_WEIGHTS
        score = round(sum(value * weights[key] for key, value in components.items()) / sum(weights.values()))
        candidates.append({"start": float(start), "end": float(end), "score": score, "components": components})
    selected = []
    for item in sorted(candidates, key=lambda entry: (-entry["score"], entry["start"])):
        if any(min(item["end"], other["end"]) - max(item["start"], other["start"]) >
               0.35 * min(item["end"] - item["start"], other["end"] - other["start"]) for other in selected):
            continue
        selected.append(item)
        if len(selected) == video.options["count"]:
            break
    return selected
