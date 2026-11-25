"""Bounded upload ownership and transport-level media validation."""
from pathlib import Path
import secrets
import struct
import tempfile
import threading
import time

MAX_UPLOAD = 10 * 1024 * 1024


class MediaError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def inspect_media(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        w, h = struct.unpack_from(">II", data, 16)
        if not w or not h or w * h > 40_000_000:
            raise MediaError("image_dimensions")
        return {"kind": "image", "suffix": ".png", "mime": "image/png"}
    if data.startswith(b"\xff\xd8\xff"):
        # The native SDK performs the actual image decoding and preprocessing.
        pos = 2
        while pos + 4 <= len(data):
            if data[pos] != 255:
                break
            while pos < len(data) and data[pos] == 255:
                pos += 1
            if pos >= len(data):
                break
            marker = data[pos]
            pos += 1
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                continue
            if marker == 0xDA or pos + 2 > len(data):
                break
            length = struct.unpack_from(">H", data, pos)[0]
            if length < 2 or pos + length > len(data):
                break
            if marker in (0xC0, 0xC1, 0xC2) and length >= 8:
                h, w = struct.unpack_from(">HH", data, pos + 3)
                if not w or not h or w * h > 40_000_000:
                    raise MediaError("image_dimensions")
                return {"kind": "image", "suffix": ".jpg", "mime": "image/jpeg"}
            pos += length
        raise MediaError("invalid_image")
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        if len(data) < 44 or struct.unpack_from("<I", data, 4)[0] + 8 != len(data):
            raise MediaError("invalid_wav")
        pos, fmt, payload = 12, None, None
        while pos + 8 <= len(data):
            name, size = data[pos:pos + 4], struct.unpack_from("<I", data, pos + 4)[0]
            start, end = pos + 8, pos + 8 + size
            if end > len(data):
                raise MediaError("invalid_wav")
            if name == b"fmt " and size >= 16:
                fmt = struct.unpack_from("<HHIIHH", data, start)
            elif name == b"data":
                if payload is not None:
                    raise MediaError("invalid_wav")
                payload = size
            pos = end + size % 2
        if fmt is None or payload is None:
            raise MediaError("invalid_wav")
        codec, channels, rate, byte_rate, block, bits = fmt
        if channels != 1 or rate != 16000 or (codec, bits) not in ((1, 16), (3, 32)):
            raise MediaError("wav_format")
        if block != bits // 8 or byte_rate != rate * block or payload % block:
            raise MediaError("invalid_wav")
        frames = payload // block
        if not 400 <= frames <= 320000:
            raise MediaError("wav_duration")
        return {"kind": "audio", "suffix": ".wav", "mime": "audio/wav", "duration": frames / rate}
    raise MediaError("unsupported_media")


class UploadStore:
    """Only this service's temporary directory is owned and removed."""
    def __init__(self, parent):
        Path(parent).mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix="session-", dir=parent)
        self.lock = threading.Lock()
        self.entries = {}

    def create(self, data):
        if not data or len(data) > MAX_UPLOAD:
            raise MediaError("upload_size")
        meta = inspect_media(data)
        with self.lock:
            self._expire()
            if len(self.entries) >= 16 or sum(e["size"] for e in self.entries.values()) + len(data) > 96 * 1024 * 1024:
                raise MediaError("upload_capacity")
            key, token = secrets.token_hex(16), secrets.token_hex(24)
            path = Path(self.directory.name) / (key + meta["suffix"])
            path.write_bytes(data)
            self.entries[key] = dict(path=path, token=token, created=time.monotonic(), size=len(data), meta=meta)
        return dict(id=key, token=token, **{k: v for k, v in meta.items() if k != "suffix"})

    def _expire(self):
        for key in list(self.entries):
            if time.monotonic() - self.entries[key]["created"] > 600:
                self.entries.pop(key)["path"].unlink(missing_ok=True)

    def take(self, key, token):
        if not isinstance(key, str) or not isinstance(token, str):
            raise MediaError("upload_expired")
        with self.lock:
            self._expire()
            entry = self.entries.get(key)
            if not entry or not secrets.compare_digest(entry["token"], token):
                raise MediaError("upload_expired")
            self.entries.pop(key)
            return entry["path"], entry["meta"]

    def take_many(self, refs, preset_counts):
        """Validate all ownership and message counts before consuming any upload."""
        with self.lock:
            self._expire();entries=[];seen=set();counts=dict(preset_counts)
            for key,token in refs:
                if not isinstance(key,str)or not isinstance(token,str)or key in seen:raise MediaError("upload_expired")
                entry=self.entries.get(key)
                if not entry or not secrets.compare_digest(entry["token"],token):raise MediaError("upload_expired")
                seen.add(key);entries.append((key,entry));counts[entry["meta"]["kind"]]+=1
            if counts["image"]>8 or counts["audio"]>1:raise MediaError("media_count")
            for key,_ in entries:self.entries.pop(key)
            return [(entry["path"],entry["meta"])for _,entry in entries]

    def discard(self, key, token):
        path, _ = self.take(key, token)
        path.unlink(missing_ok=True)

    def expire(self):
        with self.lock:
            self._expire()

    def close(self):
        self.directory.cleanup()
