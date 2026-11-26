"""Pandora LM v1 over the single native Qwen2.5-Omni C ABI."""
from collections.abc import Mapping
from contextlib import ExitStack
from dataclasses import dataclass, field
import math
import os
from pathlib import Path
import struct
import threading

from ._backend import (_Model as _NativeModel, BusyError, ClosedError, InputError,
                  ResourceError, UnsupportedFeatureError, _freeze, _local_path)


_STATISTIC_KEYS = (
    'prompt_tokens', 'prefix_tokens', 'context_tokens', 'media_tokens',
    'image_count', 'image_tokens', 'audio_count', 'audio_tokens', 'vision_buckets',
    'context_capacity', 'context_usable_tokens', 'new_prefill_tokens',
    'cached_tokens_before', 'cached_tokens_after', 'pending_eos_prepended',
    'generated_tokens', 'generated_tokens_including_eos', 'mrope_grid_count',
    'preprocess_ms', 'vision_invoke_ms', 'audio_invoke_ms_list', 'tower_invoke_ms',
    'lm_ttft_ms', 'decode_tokens_per_second', 'total_native_request_ms',
    'generation_config', 'sampling_execution',
)


@dataclass(frozen=True)
class GenerationResult:
    text: str
    audio: object
    finish_reason: str
    statistics: Mapping[str, object] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        values = {key: self.statistics[key] for key in _STATISTIC_KEYS if key in self.statistics}
        object.__setattr__(self, 'statistics', _freeze(values))


@dataclass(frozen=True)
class GenerationUpdate:
    delta: str
    text: str
    finish_reason: object = None
    audio_delta: object = None


class DynamicCache:
    """Lazy native KV ownership, bound to one model instance and process."""
    def __init__(self):
        self._pid = os.getpid()
        self._lock = threading.RLock()
        self._owner = self._cache = None
        self._closed = self._active = False
        self._valid = True

    def _check(self):
        if self._pid != os.getpid() or self._closed:
            raise ClosedError('Cache closed or inherited after fork')

    def _acquire(self, model, *, bind=True):
        with self._lock:
            self._check()
            if self._active:
                raise BusyError('Cache already has an active operation')
            if not self._valid:
                raise InputError('Cache chain ended incompletely; create a new DynamicCache')
            if self._owner is not None and self._owner is not model:
                raise InputError('Cache belongs to another model instance')
            if self._cache is None and bind:
                native = model._model.create_cache()
                self._owner, self._cache = model, native
            self._active = True
            return self._cache

    def _release(self, *, valid=True):
        with self._lock:
            self._valid = self._valid and valid
            self._active = False

    @classmethod
    def _from_native(cls, model, cache):
        obj = cls()
        obj._owner, obj._cache = model, cache
        return obj

    def query(self):
        """Return an immutable snapshot of this cache’s context usage and validity."""
        with self._lock:
            self._check()
            if self._active:
                raise BusyError('Cache has an active operation')
            if self._cache is None:
                return _freeze(dict(bound=False, valid=self._valid, turns=0))
            native = self._cache.query()
            state = {key: native[key] for key in (
                'turns', 'logical_history_tokens', 'pending_eos_tokens',
                'context_capacity', 'context_usable_tokens', 'kv_logical_payload_bytes',
            )}
            restore = native['snapshot_restore']
            state.update(
                bound=True, valid=native['valid'] and self._valid, effective_kv_tokens=native['n_past'],
                snapshot_restore={key: restore[key] for key in (
                    'total_restore_ms', 'total_bytes', 'history_tokens', 'historical_prefill_tokens',
                ) if key in restore},
            )
            return _freeze(state)

    def save(self, path):
        """Save a completed cache to a new private local directory."""
        with self._lock:
            self._check()
            if self._active:
                raise BusyError('Cache has an active operation')
            if self._cache is None or not self._valid:
                raise InputError('A completed bound cache is required')
            saved = self._cache.save(_local_path(path, "snapshot"))
            return _freeze({key: saved[key] for key in ('path', 'total_bytes', 'save_ms', 'history_tokens')})

    @classmethod
    def load(cls, path, model):
        """Restore a compatible snapshot and bind the new cache to model."""
        if not isinstance(model, LanguageModel):
            raise InputError('Expected this SDK LanguageModel')
        with model._lock:
            return cls._from_native(model, model._model.load_cache(_local_path(path, "snapshot")))

    def rebuild(self, *, system, retain_from_turn):
        """Return a new cache with a replacement system message and a retained turn suffix."""
        with self._lock:
            self._check()
            if self._active:
                raise BusyError('Cache has an active operation')
            if self._cache is None or not self._valid:
                raise InputError('A completed bound cache is required')
            if not isinstance(system, str) or '<|' in system or '\0' in system:
                raise InputError('Expected system text without template control markers or NUL')
            if type(retain_from_turn) is not int or not 0 <= retain_from_turn < 2**63:
                raise InputError('Expected a nonnegative completed turn index')
            native = self._cache.rebuild(system=system, retain_from_turn=retain_from_turn)
            return self._from_native(self._owner, native)

    def close(self):
        with self._lock:
            if self._pid != os.getpid():
                raise ClosedError('Cache inherited after fork')
            if self._active:
                raise BusyError('Close the active stream before its cache')
            if not self._closed:
                if self._cache is not None:
                    self._cache.close()
                self._closed = True

    def __enter__(self):
        self._check()
        return self

    def __exit__(self, *_):
        self.close()


def _messages(messages, audio_files):
    if not isinstance(messages, (list, tuple)) or not messages:
        raise InputError('messages must be a nonempty ordered sequence')
    result, expected = [], 'user'
    for index, message in enumerate(messages):
        if not isinstance(message, dict) or set(message) != {'role', 'content'}:
            raise InputError('Expected role/content messages')
        role = message['role']
        if not (index == 0 and role == 'system'):
            if role != expected:
                raise InputError('Invalid message role order')
            expected = 'assistant' if role == 'user' else 'user'
        content = message['content']
        if isinstance(content, str):
            content = [{'type': 'text', 'text': content}]
        if not isinstance(content, (list, tuple)):
            raise InputError('Expected text or ordered typed content')
        parts, images, audios = [], 0, 0
        for part in content:
            if not isinstance(part, dict):
                raise InputError('Expected a typed content item')
            kind = part.get('type')
            if kind == 'video':
                raise UnsupportedFeatureError('Video input is not delivered by this model')
            if kind not in ('text', 'image', 'audio') or set(part) != {'type', kind}:
                raise InputError('Expected type and its matching text/image/audio field')
            value = part[kind]
            if kind == 'text':
                if not isinstance(value, str) or '<|' in value:
                    raise InputError('Expected text without template control markers')
            else:
                if role != 'user':
                    raise InputError('Media belongs in user messages')
                images += kind == 'image'
                audios += kind == 'audio'
                if images > 8 or audios > 1:
                    raise InputError('At most eight images and one audio per user message')
            parts.append({'type': kind, kind: value})
        # Check the message's media limits before opening or staging any files.
        for part in parts:
            kind = part['type']
            if kind != 'text':
                part[kind] = _local_media(part[kind], kind, audio_files)
        result.append(dict(role=role, content=parts))
    if result[-1]['role'] != 'user':
        raise InputError('Last message must be user')
    return result


def _local_media(value, kind, audio_files):
    value = _local_path(value, "media file")
    try:
        if not Path(value).is_file():
            raise InputError('Media file does not exist')
        if kind == 'audio':
            from ._media import _audio_path
            return _audio_path(value, audio_files)
        if kind == 'image':
            from PIL import Image
            try:
                with Image.open(value) as image:
                    if image.format not in ('JPEG', 'PNG'):
                        raise UnsupportedFeatureError('Expected JPEG or PNG')
                    if image.width * image.height > 40_000_000:
                        raise InputError('Image exceeds 40 megapixels')
                    image.verify()
            except Image.DecompressionBombError as error:
                raise InputError('Image exceeds 40 megapixels') from error
            except (SyntaxError, ValueError, struct.error) as error:
                if isinstance(error, InputError):
                    raise
                raise InputError('Invalid image file') from error
    except (OSError, RuntimeError) as error:
        if isinstance(error, (InputError, UnsupportedFeatureError, ResourceError)):
            raise
        raise InputError('Invalid media file') from error
    return value


class LanguageModel:
    def __init__(self):
        raise TypeError('Use LanguageModel.from_pretrained')

    @classmethod
    def from_pretrained(cls, model_dir, *, runtime=None):
        obj = object.__new__(cls)
        obj._lock = threading.RLock()
        obj._model = _NativeModel.from_pretrained(model_dir, runtime=runtime)
        return obj

    @property
    def capabilities(self):
        values = dict(self._model.capabilities)
        values.update(api='LM v1', outputs=['text'], audio_output=False,
                      audio_streaming=False, video_input=False,
                      streaming=bool(values.get('text_streaming')), cross_turn_cache=True,
                      cache_query=True, cache_snapshot=True, cache_rebuild=True,
                      token_count=True, generation_statistics=True,
                      generation_parameters=[name for name in
                          ('max_new_tokens','do_sample','temperature','top_p','top_k','repetition_penalty')
                          if name in values.get('generation_parameters', ())])
        return _freeze(values)

    def _options(self, max_new_tokens, do_sample, temperature, top_p, top_k,
                 repetition_penalty, return_audio):
        self._model._check()
        if return_audio is not False:
            raise UnsupportedFeatureError('Speech output is not delivered by this model')
        supported = self._model.capabilities.get('generation_parameters', ())
        for name, value in [('max_new_tokens', max_new_tokens), ('do_sample', do_sample),
                            ('temperature', temperature), ('top_p', top_p), ('top_k', top_k),
                            ('repetition_penalty', repetition_penalty)]:
            if value is not None and name not in supported:
                raise UnsupportedFeatureError('Native backend cannot control ' + name)
        if do_sample is not None and type(do_sample) is not bool:
            raise InputError('do_sample must be bool')
        if do_sample is not True and any(value is not None for value in (temperature, top_p, top_k)):
            raise InputError('temperature/top_p/top_k require do_sample=True for this call')
        if max_new_tokens is not None and (type(max_new_tokens) is not int or max_new_tokens <= 0):
            raise InputError('max_new_tokens must be a positive integer')
        for name, value in [('temperature', temperature), ('top_p', top_p),
                            ('repetition_penalty', repetition_penalty)]:
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0):
                raise InputError('Invalid ' + name)
        if top_p is not None and top_p > 1:
            raise InputError('top_p must be in (0,1]')
        if top_k is not None and (type(top_k) is not int or not 0 <= top_k <= 2147483647):
            raise InputError('top_k must be a nonnegative int32')
        return {name: value for name, value in {
            "max_new_tokens": max_new_tokens,
            "do_sample": do_sample,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "repetition_penalty": repetition_penalty,
        }.items() if value is not None}

    def generate(self, messages, *, max_new_tokens=None, do_sample=None, temperature=None,
                 top_p=None, top_k=None, repetition_penalty=None, return_audio=False,
                 past_key_values=None):
        with self.generate_stream(messages, max_new_tokens=max_new_tokens, do_sample=do_sample,
                                  temperature=temperature, top_p=top_p, top_k=top_k,
                                  repetition_penalty=repetition_penalty, return_audio=return_audio,
                                  past_key_values=past_key_values) as stream:
            for _ in stream:
                pass
            return stream.result

    def generate_stream(self, messages, *, max_new_tokens=None, do_sample=None, temperature=None,
                        top_p=None, top_k=None, repetition_penalty=None, return_audio=False,
                        past_key_values=None):
        with self._lock, ExitStack() as audio_files:
            options = self._options(max_new_tokens, do_sample, temperature, top_p, top_k,
                                    repetition_penalty, return_audio)
            messages = _messages(messages, audio_files)
            cache = past_key_values
            if cache is not None and not isinstance(cache, DynamicCache):
                raise InputError('Expected this SDK DynamicCache')
            if cache is not None and sum(message['role'] == 'user' for message in messages) != 1:
                raise InputError('Cached calls accept one user turn with an optional initial system')
            native = cache._acquire(self) if cache is not None else None
            try:
                # Native request creation has already decoded the media when it returns.
                stream = self._model.generate_stream(messages=messages, past_key_values=native, **options)
            except BaseException:
                if cache is not None:
                    cache._release()
                raise
            return _GenerationStream(stream, cache)

    def count_tokens(self, messages, *, past_key_values=None, max_new_tokens=None):
        """Plan the token budget for a request without running inference or binding an empty cache."""
        with self._lock, ExitStack() as audio_files:
            self._options(max_new_tokens, None, None, None, None, None, False)
            messages = _messages(messages, audio_files)
            cache = past_key_values
            if cache is not None and not isinstance(cache, DynamicCache):
                raise InputError('Expected this SDK DynamicCache')
            if cache is not None and sum(message['role'] == 'user' for message in messages) != 1:
                raise InputError('Cached calls accept one user turn with an optional initial system')
            native = cache._acquire(self, bind=False) if cache is not None else None
            try:
                return self._model.count_tokens(messages=messages, past_key_values=native,
                                                max_new_tokens=max_new_tokens)
            finally:
                if cache is not None:
                    cache._release()

    def close(self):
        with self._lock:
            self._model.close()

    def __enter__(self):
        self._model._check()
        return self

    def __exit__(self, *_):
        self.close()


class _GenerationStream:
    def __init__(self, stream, cache):
        self._stream, self._cache = stream, cache
        self._result = None
        self._closed = False
        self._text = ""
        self._lock = threading.RLock()

    def __iter__(self):
        return self

    def __next__(self):
        if self._closed:
            raise StopIteration
        try:
            update = next(self._stream)
        except BaseException:
            self.close()
            raise
        with self._lock:
            if self._closed:
                raise StopIteration
            self._text = update.text
            if update.finish_reason is not None:
                self._finish()
            return GenerationUpdate(update.delta, update.text, update.finish_reason)

    def _finish(self):
        raw = self._stream.result
        text = self._text if raw.finish_reason == 'cancelled' else raw.text
        self._result = GenerationResult(text, None, raw.finish_reason, raw.statistics)
        try:
            self._stream.close()
        finally:
            if self._stream._closed:
                self._closed = True
                if self._cache is not None:
                    self._cache._release(valid=raw.finish_reason == 'stop')

    @property
    def result(self):
        if self._result is None:
            raise BusyError('Consume or close the stream before reading result')
        return self._result

    def close(self):
        with self._lock:
            if self._closed:
                return
            try:
                self._stream.close()  # Cancels and joins the real native worker.
            except BaseException:
                if self._stream._closed:
                    self._closed = True
                    if self._cache is not None:
                        self._cache._release(valid=False)
                raise
            raw = self._stream._result
            if raw is not None:
                text = self._text if raw.finish_reason == 'cancelled' else raw.text
                self._result = GenerationResult(text, None, raw.finish_reason, raw.statistics)
            else:
                self._result = GenerationResult('', None, 'cancelled')
            self._closed = True
            if self._cache is not None:
                self._cache._release(valid=self._result.finish_reason == 'stop')

    def __enter__(self):
        self._stream._check_pid()
        return self

    def __exit__(self, *_):
        self.close()
