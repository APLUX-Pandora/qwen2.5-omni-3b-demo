"""Internal bounded WAV validation for LM messages."""
import numpy as np
from ._api import InputError, UnsupportedFeatureError


def _audio(value):
    # soundfile supports the accepted PCM16 and FLOAT WAV subtypes without
    # lossy conversion or resampling. Metadata is checked before allocation.
    import soundfile as sf
    with sf.SoundFile(value) as audio:
        if audio.format != "WAV" or audio.subtype not in ("PCM_16", "FLOAT") or audio.samplerate != 16000 or audio.channels != 1:
            raise UnsupportedFeatureError("Expected mono 16 kHz PCM16/float32 WAV")
        if not 400 <= audio.frames <= 320000:
            raise InputError("Audio must have 400..320000 samples")
        data = audio.read(dtype="float32")
    if data.dtype != np.float32 or data.ndim != 1 or not 400 <= data.size <= 320000 or not np.isfinite(data).all():
        raise InputError("Expected bounded finite mono float32 PCM at 16 kHz")
    return np.ascontiguousarray(data)
