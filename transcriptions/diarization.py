import logging
import wave
from functools import lru_cache

import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def pipeline(name, token):
    from pyannote.audio import Pipeline

    return Pipeline.from_pretrained(name, token=token or None)


def speaker_turns(path):
    if not settings.DIARIZATION_MODEL:
        return []
    try:
        import torch

        with wave.open(str(path), "rb") as audio:
            samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").astype(np.float32)
            sample_rate = audio.getframerate()
        result = pipeline(settings.DIARIZATION_MODEL, settings.DIARIZATION_TOKEN)({
            "waveform": torch.from_numpy(samples / 32768).unsqueeze(0),
            "sample_rate": sample_rate,
        })
        annotation = result.exclusive_speaker_diarization
        return [(turn.start, turn.end, label) for turn, _, label in annotation.itertracks(yield_label=True)]
    except Exception as error:
        logger.warning("diarization_failed error_type=%s", type(error).__name__)
        return []


def dominant_speaker(start, end, turns):
    overlap_by_label = {}
    for left, right, label in turns:
        overlap = min(end, right) - max(start, left)
        if overlap > 0:
            overlap_by_label[label] = overlap_by_label.get(label, 0) + overlap
    return max(overlap_by_label, key=overlap_by_label.get, default=None)
