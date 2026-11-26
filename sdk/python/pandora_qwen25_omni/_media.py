"""Private audio file adaptation for the native LM request interface."""

from tempfile import NamedTemporaryFile

import numpy as np

from ._api import InputError, ResourceError, UnsupportedFeatureError


_RATE = 16000
_MIN_SAMPLES = 400
_MAX_SAMPLES = 320000
_FILE_FORMATS = {"WAV", "WAVEX", "RF64", "FLAC", "MP3"}


def _read_mono(audio):
    frames = audio.frames
    if audio.channels == 1:
        waveform = audio.read(frames, dtype="float32")
        if waveform.size != frames or not np.isfinite(waveform).all():
            raise InputError("Audio contains incomplete or nonfinite samples")
        return waveform

    waveform = np.empty(frames, dtype=np.float32)
    offset = 0
    while offset < frames:
        block = audio.read(min(16384, frames - offset), dtype="float32", always_2d=True)
        if not len(block) or not np.isfinite(block).all():
            raise InputError("Audio contains incomplete or nonfinite samples")
        waveform[offset:offset + len(block)] = block.mean(axis=1, dtype=np.float64)
        offset += len(block)
    return waveform


def _audio_path(value, audio_files):
    """Keep an accepted native WAV or prepare a short-lived WAV for this request."""
    import soundfile as sf

    try:
        source = sf.SoundFile(value)
    except sf.LibsndfileError as error:
        raise InputError("Cannot decode audio file; expected a readable WAV, FLAC, or MP3") from error
    with source:
        if source.format not in _FILE_FORMATS:
            raise UnsupportedFeatureError("Expected WAV, FLAC, or MP3 audio")
        rate = source.samplerate
        if not 8000 <= rate <= 192000 or not 1 <= source.channels <= 8:
            raise UnsupportedFeatureError("Audio must have 1–8 channels at 8–192 kHz")
        if not _MIN_SAMPLES * rate <= source.frames * _RATE <= _MAX_SAMPLES * rate:
            raise InputError("Audio must be 0.025–20 seconds; trim longer files before sending")
        native_wav = (source.format == "WAV" and source.subtype in ("PCM_16", "FLOAT")
                      and rate == _RATE and source.channels == 1)
        waveform = _read_mono(source)

    if native_wav:
        return value
    if rate != _RATE:
        import soxr

        waveform = soxr.resample(waveform, rate, _RATE, quality="HQ")
    if not _MIN_SAMPLES <= waveform.size <= _MAX_SAMPLES or not np.isfinite(waveform).all():
        raise InputError("Cannot convert audio to finite 16 kHz mono PCM within the duration limit")

    try:
        # The request's ExitStack keeps this path valid until native media preparation returns.
        output = audio_files.enter_context(
            NamedTemporaryFile(prefix="pandora-omni-", suffix=".wav")  # noqa: SIM115
        )
        sf.write(output.name, waveform, _RATE, format="WAV", subtype="FLOAT")
    except (OSError, RuntimeError) as error:
        raise ResourceError("Cannot stage converted audio for the native request") from error
    return output.name
