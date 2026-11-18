import wave

import numpy as np
from functools import lru_cache
from math import exp

from django.conf import settings


@lru_cache(maxsize=1)
def model():
    from faster_whisper import WhisperModel

    return WhisperModel(settings.WHISPER_MODEL, device=settings.WHISPER_DEVICE,
                        compute_type=settings.WHISPER_COMPUTE_TYPE, cpu_threads=settings.WHISPER_CPU_THREADS)


def recognize(path, language):
    with wave.open(str(path), "rb") as audio:
        waveform = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").astype(np.float32) / 32768
    segments, info = model().transcribe(
        waveform, language=language or None, word_timestamps=True, vad_filter=True,
    )
    results = []
    for segment in segments:
        if segment.end <= segment.start or not segment.text.strip():
            continue
        results.append({
            "start": segment.start, "end": segment.end, "text": segment.text.strip(),
            "confidence": min(1, exp(segment.avg_logprob)),
            "words": [{"start": word.start, "end": word.end, "text": word.word.strip(), "confidence": word.probability}
                      for word in (segment.words or [])],
        })
    return info.language, info.language_probability, results
