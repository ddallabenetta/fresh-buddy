"""Audio helpers for the TTS service."""

from __future__ import annotations

import audioop
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def load_volume(default: float = 1.0) -> float:
    """Read the configured TTS volume from the environment."""
    raw = os.environ.get("TTS_VOLUME", str(default))
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid TTS_VOLUME %r, falling back to %s", raw, default)
        return default


def apply_volume(output_file: str | Path, volume: float) -> None:
    """Apply a linear gain to a WAV file in place."""
    if volume == 1.0:
        return

    volume = max(0.0, volume)

    import wave

    with wave.open(str(output_file), "rb") as reader:
        params = reader.getparams()
        frames = reader.readframes(reader.getnframes())

    scaled_frames = audioop.mul(frames, params.sampwidth, volume)

    with wave.open(str(output_file), "wb") as writer:
        writer.setparams(params)
        writer.writeframes(scaled_frames)
