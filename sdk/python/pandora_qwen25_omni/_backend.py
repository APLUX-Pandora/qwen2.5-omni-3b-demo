import codecs
import ctypes as C
from contextlib import nullcontext
from dataclasses import dataclass
import json
import os
import queue
import threading
from types import MappingProxyType

from ._native import library
from ._runtime import Runtime


class OmniError(RuntimeError):
    def __init__(self, message, *, native_code=0, operation=""):
        super().__init__(message)
        self.native_code, self.operation = native_code, operation
class InputError(OmniError, ValueError): pass
class UnsupportedFeatureError(OmniError): pass
class BusyError(OmniError): pass
class ClosedError(OmniError): pass
class InferenceError(OmniError): pass
class ResourceError(OmniError): pass
class BackendError(InferenceError): pass
class InternalError(OmniError): pass


@dataclass(frozen=True)
class _GenerationResult:
    text: str
    finish_reason: str
    statistics: object


@dataclass(frozen=True)
class _GenerationUpdate:
    text: str
    delta: str
    finish_reason: object = None


def _freeze(value):
    if isinstance(value, dict): return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list): return tuple(_freeze(v) for v in value)
    return value


class _Options(C.Structure):
    _fields_ = [("struct_size", C.c_uint32), ("abi_version", C.c_uint32),
                ("data", C.c_char_p), ("size", C.c_uint64)]


_Callback = C.CFUNCTYPE(C.c_int32, C.c_void_p, C.c_uint64, C.c_void_p)


class _HandleLease:
    """Own a native output slot before entering a potentially interrupted call."""
    def __init__(self,native,closer):
        self.native,self.closer,self.pid=native,closer,os.getpid();self.out=C.c_uint64()
    def close(self):
        if self.pid!=os.getpid(): return
        value=self.out.value
        if value:self.native.call(self.closer,value);self.out.value=0
    def __del__(self):
        try:self.close()
        except BaseException:pass

class _ManagedHandle(int):
    def __new__(cls,lease):
        value=int.__new__(cls,lease.out.value);value._lease=lease;return value

class _Native:
    def __init__(self):
        self.lib = library()
        H, O, P = C.c_uint64, C.POINTER(_Options), C.POINTER(C.c_void_p)
        signatures = {
            "model_open": [C.c_void_p, O, C.POINTER(H)], "model_query": [H, P], "model_close": [H],
            "cache_save": [H,O,P], "cache_load": [H,O,C.POINTER(H)], "model_count": [H,O,P], "cache_fork": [H,O,C.POINTER(H)],
            "request_create": [H, O, C.POINTER(H)], "request_plan": [H,P],
            "cache_create": [H,C.POINTER(H)], "cache_query": [H,P], "cache_close": [H], "request_execute": [H, _Callback, C.c_void_p],
            "request_cancel": [H], "request_result": [H, P], "request_release": [H],
        }
        for name, args in signatures.items():
            f = getattr(self.lib, "q25o_" + name); f.argtypes, f.restype = args, C.c_int32
        self.lib.q25o_last_error.argtypes = []; self.lib.q25o_last_error.restype = C.c_char_p
        self.lib.q25o_buffer_free.argtypes = [C.c_void_p]; self.lib.q25o_buffer_free.restype = None
    def call(self, name, *args):
        lease=getattr(args[0],"_lease",None) if args else None
        closing=lease is not None and name==lease.closer
        if closing and not lease.out.value:return
        rc = getattr(self.lib, "q25o_" + name)(*args)
        if closing and rc in (0,4):lease.out.value=0;return
        if rc:
            raw = self.lib.q25o_last_error()
            data = json.loads(raw.decode()) if raw else {}
            cls = {1: InputError, 2: UnsupportedFeatureError, 3: BusyError, 4: ClosedError,
                   5: InferenceError, 6: ResourceError, 7: BackendError, 8: InternalError
                   }.get(rc, InternalError)
            raise cls(data.get("message", "Native inference failed"), native_code=data.get("native_code", 0), operation=data.get("operation") or name)
    def create(self, name, values, *prefix):
        try: data = json.dumps(values, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, UnicodeError) as exc: raise InputError("Invalid request encoding") from exc
        options = _Options(C.sizeof(_Options), 1, data, len(data))
        return self.allocate(name,*prefix,C.byref(options))
    def allocate(self,name,*args):
        closer={"model_open":"model_close","cache_create":"cache_close","cache_load":"cache_close","cache_fork":"cache_close","request_create":"request_release"}[name]
        lease=_HandleLease(self,closer)
        try:
            self.call(name,*args,C.byref(lease.out))
            return _ManagedHandle(lease)
        except BaseException:
            try:lease.close()
            except BaseException:pass
            raise
    def query(self, name, handle):
        out = C.c_void_p()
        try:
            self.call(name,handle,C.byref(out))
            return json.loads(C.string_at(out).decode("utf-8"))
        finally:
            if out.value:self.lib.q25o_buffer_free(out)


def _local_path(path, label):
    try:
        value = os.fspath(path)
        if not isinstance(value, str) or not value or '://' in value or '\0' in value:
            raise ValueError('Expected a nonempty local path')
        value.encode('utf-8')
    except (TypeError, ValueError) as error:
        raise InputError(f'Expected a nonempty local {label} path') from error
    return value


class _Model:
    def __init__(self): raise TypeError("Use _Model.from_pretrained")
    @classmethod
    def from_pretrained(cls, model_dir, *, runtime=None):
        if runtime is not None and not isinstance(runtime, Runtime):
            raise InputError("Runtime provider mismatch")
        obj = object.__new__(cls)
        obj._pid, obj._closed = os.getpid(), True
        obj._close_lock = threading.Lock()
        obj._native = _Native()
        try:
            values = {"model_dir": _local_path(model_dir, "model directory")}
            with (nullcontext() if runtime is None else runtime.borrow_handle()) as native_handle:
                obj._handle = obj._native.create("model_open", values, native_handle)
            obj._closed = False
            obj._capabilities = obj._native.query("model_query", obj._handle)
        except BaseException:
            if not obj._closed:
                obj.close()
            raise
        return obj
    def _check(self):
        if self._pid != os.getpid() or self._closed: raise ClosedError("Model is closed or inherited after fork")
    @property
    def capabilities(self):
        self._check()
        return _freeze(self._capabilities)
    def _request_values(self, messages, past_key_values, **options):
        self._check()
        values = dict(messages=messages, **options)
        if past_key_values is not None:
            if not isinstance(past_key_values, _Cache) or past_key_values._model is not self:
                raise InputError("past_key_values belongs to another model")
            past_key_values._check()
            values["cache_handle"] = past_key_values._handle
        return values

    def generate_stream(self, *, messages, past_key_values=None, **options):
        values = self._request_values(messages, past_key_values, **options)
        return _Stream(self, values, past_key_values)

    def count_tokens(self, *, messages, past_key_values=None, max_new_tokens=None):
        values = self._request_values(messages, past_key_values, max_new_tokens=max_new_tokens)
        try:
            data = json.dumps(values, ensure_ascii=False, allow_nan=False).encode('utf-8')
        except (TypeError, ValueError) as exc:
            raise InputError('Invalid request encoding') from exc
        opts=_Options(C.sizeof(_Options),1,data,len(data));result=C.c_void_p()
        try:
            self._native.call('model_count',self._handle,C.byref(opts),C.byref(result))
            return _freeze(json.loads(C.string_at(result).decode('utf-8')))
        finally:self._native.lib.q25o_buffer_free(result)
    def load_cache(self, path):
        """Load a completed local snapshot without historical inference.

        The model package must match the snapshot. Returns a new owned _Cache;
        close it before closing its model.
        """
        self._check()
        handle=self._native.create("cache_load",dict(path=path),self._handle)
        return _Cache._from_handle(self,handle)
    def create_cache(self):
        self._check()
        return _Cache(self)
    def close(self):
        if self._pid != os.getpid(): raise ClosedError("Model inherited after fork")
        with self._close_lock:
            if not self._closed:
                self._native.call("model_close", self._handle); self._closed = True
    def __enter__(self): self._check(); return self
    def __exit__(self, *_): self.close()


class _Cache:
    """One owned native dialog. Completed turns append KV; omit this object to start a new conversation."""
    def __init__(self, model):
        model._check()
        self._model, self._native, self._pid = model, model._native, os.getpid()
        self._closed = True; self._close_lock = threading.Lock()
        self._handle = self._native.allocate("cache_create",model._handle); self._closed = False
    def _check(self):
        if self._pid != os.getpid() or self._closed: raise ClosedError("Cache is closed or inherited after fork")
        self._model._check()
    def query(self):
        self._check(); return _freeze(self._native.query("cache_query", self._handle))
    @classmethod
    def _from_handle(cls,model,handle):
        obj=object.__new__(cls)
        obj._model,obj._native,obj._pid=model,model._native,model._pid
        obj._handle,obj._closed,obj._close_lock=handle,False,threading.Lock()
        return obj
    def save(self,path):
        """Atomically save an EOS-completed cache to a new private directory.

        Includes KV, exact token/media ledger and positional state. Snapshots
        contain conversation data; they are not encrypted model artifacts.
        Returns save time and file-size statistics. Existing paths are rejected.
        """
        self._check()
        data=json.dumps(dict(path=path),ensure_ascii=False).encode("utf-8")
        opts=_Options(C.sizeof(_Options),1,data,len(data));out=C.c_void_p()
        try:
            self._native.call("cache_save",self._handle,C.byref(opts),C.byref(out))
            return _freeze(json.loads(C.string_at(out).decode("utf-8")))
        finally: self._native.lib.q25o_buffer_free(out)
    def rebuild(self, *, system, retain_from_turn):
        """Rebuild a completed suffix with a new system header in a new cache.

        Retained token IDs/media embeddings are copied exactly; positions and KV
        are recomputed. Selection policy and summary generation belong to callers.
        """
        self._check()
        handle=self._native.create("cache_fork",dict(system=system,retain_from_turn=retain_from_turn),self._handle)
        obj=object.__new__(_Cache)
        obj._model,obj._native,obj._pid=self._model,self._native,self._pid
        obj._handle,obj._closed,obj._close_lock=handle,False,threading.Lock()
        return obj
    def close(self):
        if self._pid != os.getpid(): raise ClosedError("Cache inherited after fork")
        with self._close_lock:
            if not self._closed:
                self._native.call("cache_close",self._handle); self._closed=True
    def __enter__(self): self._check(); return self
    def __exit__(self,*_): self.close()


class _Stream:
    def __init__(self, model, values, cache=None, *, request_handle=None):
        self._cache = cache
        self._model, self._native, self._pid = model, model._native, os.getpid()
        self._handle = request_handle if request_handle is not None else self._native.create("request_create", values, model._handle)
        self._queue, self._done, self._closing = queue.Queue(16), threading.Event(), threading.Event()
        self._decoder = codecs.getincrementaldecoder("utf-8")("strict")
        self._thread = None; self._error = None; self._result = None
        self._text = ""; self._closed = False; self._terminal = False
        self._close_lock = threading.Lock()
    def _check_pid(self):
        if self._pid != os.getpid(): raise ClosedError("Stream inherited after fork")
    def _run(self):
        @_Callback
        def callback(data, size, _):
            try:
                chunk = C.string_at(data, size)
                while not self._closing.is_set():
                    try: self._queue.put(chunk, timeout=.05); return 0
                    except queue.Full: continue
                return 1
            except BaseException as exc:
                self._error = exc; return 1
        try:
            self._native.call("request_execute", self._handle, callback, None)
            d = self._native.query("request_result", self._handle)
            self._native_result = d
            self._result = _GenerationResult(d["text"], d["finish_reason"], _freeze(d["statistics"]))
        except BaseException as exc: self._error = exc
        finally: self._done.set()
    def __iter__(self): return self
    def __next__(self):
        self._check_pid()
        if self._closed or self._terminal: raise StopIteration
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="qwen25-omni-stream", daemon=False)
            try:
                self._thread.start()
            except BaseException:
                # An unstarted thread cannot be joined. Retain any thread that
                # did start so close still waits before releasing the request.
                if self._thread.ident is None:
                    self._thread = None
                raise
        while True:
            try: chunk = self._queue.get(timeout=.05)
            except queue.Empty:
                if not self._done.is_set(): continue
                if self._error is not None: raise self._error
                cancelled = self._result is not None and self._result.finish_reason == "cancelled"
                # Cancellation can reject an in-flight callback. Do not flush an
                # incomplete UTF-8 suffix whose continuation was never delivered.
                delta = self._decoder.decode(b"", final=not cancelled)
                if delta:
                    self._text += delta
                    return _GenerationUpdate(self._text, delta)
                if self._result is None: raise InferenceError("Missing native terminal result")
                matches = (self._result.text.startswith(self._text) if cancelled else self._text == self._result.text)
                if not matches: raise InferenceError("Streaming text disagrees with native result")
                self._terminal = True
                return _GenerationUpdate(self._text, "", self._result.finish_reason)
            delta = self._decoder.decode(chunk)
            if delta:
                self._text += delta
                return _GenerationUpdate(self._text, delta)
    @property
    def result(self):
        self._check_pid()
        if not self._done.is_set(): raise BusyError("Stream result is not available")
        if self._error is not None: raise self._error
        if self._result is None: raise InferenceError("Missing native terminal result")
        return self._result
    def close(self):
        self._check_pid()
        with self._close_lock:
            if self._closed: return
            self._closing.set()
            cancel_error = None
            if self._thread is not None:
                try:
                    if not self._done.is_set():
                        self._native.call("request_cancel", self._handle)
                except BaseException as exc:
                    cancel_error = exc
                finally:
                    # A failed abort is not proof that native execution ended.
                    self._thread.join()
            try:
                self._native.call("request_release", self._handle)
            except BaseException as release_error:
                if cancel_error is not None:
                    raise cancel_error from release_error
                raise
            self._closed = True
            if cancel_error is not None: raise cancel_error
            if self._error is not None: raise self._error
    def __enter__(self): self._check_pid(); return self
    def __exit__(self, *_): self.close()
