"""One-process ASGI Web Demo using the public, installed model SDK."""
import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path
import queue
import signal
import threading
import time

import anyio
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from .media import MAX_UPLOAD, MediaError
from .service import BASE, PRESETS, Busy, Engine

LOG = logging.getLogger("omni.web")


def create_app(model_dir, run_dir):
    engine = None

    @asynccontextmanager
    async def lifespan(app):
        nonlocal engine
        engine = await anyio.to_thread.run_sync(Engine, model_dir, Path(run_dir) / "uploads")
        app.state.engine = engine

        async def expire_uploads():
            while True:
                await asyncio.sleep(30)
                engine.uploads.expire()
                await anyio.to_thread.run_sync(engine.expire_sessions)

        janitor = asyncio.create_task(expire_uploads())
        LOG.info("Encrypted model SDK ready")
        try:
            yield
        finally:
            janitor.cancel()
            try:
                await janitor
            except asyncio.CancelledError:
                pass
            with anyio.CancelScope(shield=True):
                await anyio.to_thread.run_sync(engine.close)

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def headers_and_origin(request, call_next):
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD") and origin:
            from urllib.parse import urlsplit
            if urlsplit(origin).netloc != request.headers.get("host"):
                return JSONResponse({"code": "origin_rejected"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob:; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.exception_handler(MediaError)
    async def media_error(request, exc):
        return JSONResponse({"code": exc.code}, status_code=400)

    @app.exception_handler(Busy)
    async def busy_error(request, exc):
        return JSONResponse({"code": "busy"}, status_code=409)

    async def body_bytes(request, maximum):
        data = bytearray()
        async for block in request.stream():
            if len(data) + len(block) > maximum:
                raise MediaError("upload_size")
            data.extend(block)
        return bytes(data)

    async def body_json(request):
        try:
            body = json.loads(await body_bytes(request, 32768))
            if not isinstance(body, dict):
                raise ValueError()
            return body
        except (ValueError, UnicodeError):
            raise MediaError("invalid_request") from None

    @app.get("/")
    async def index():
        return FileResponse(BASE / "static/index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/api/health")
    async def health():
        with engine.lock:
            busy = engine.active is not None or engine.operation is not None
            phase = engine.active.phase if engine.active else engine.operation or "idle"
        return {"ready": not engine.closing, "busy": busy, "phase": phase, "model": "Qwen2.5-Omni-3B", "target": engine.model.capabilities["target"], "inputs": ["text", "image", "audio"], "output": "text", "max_images_per_message":engine.model.capabilities["max_images_per_message"],"max_audio_per_message":1,"response_token_limit":256,"context_capacity":engine.model.capabilities["context_capacity"],"context_usable_tokens":engine.model.capabilities["context_usable_tokens"]}

    @app.post("/api/sessions")
    async def create_session(request:Request):
        body=await body_json(request)
        return await anyio.to_thread.run_sync(lambda:engine.create_session(body.get("owner_token")))

    @app.post("/api/owner")
    async def owner():
        import secrets
        return {"owner_token":secrets.token_hex(32)}

    @app.post("/api/history")
    async def history(request:Request):
        body=await body_json(request)
        return await anyio.to_thread.run_sync(lambda:engine.history.list(body.get("owner_token")))

    @app.post("/api/sessions/{key}/restore")
    async def restore_session(key:str,request:Request):
        body=await body_json(request)
        try:
            return await anyio.to_thread.run_sync(lambda:engine.restore_session(key,body.get("token")))
        except (Busy,MediaError):raise
        except Exception:
            LOG.exception("Conversation restore failed")
            return JSONResponse({"code":"restore_failed"},status_code=503)

    @app.post("/api/sessions/{key}/media/{name}")
    async def historical_media(key:str,name:str,request:Request):
        body=await body_json(request)
        with engine.lock:engine.session(key,body.get("token"))
        path=engine.history.media(key,name)
        return FileResponse(path,media_type="audio/wav" if path.suffix==".wav" else "image/jpeg" if path.suffix==".jpg" else "image/png")

    @app.delete("/api/sessions/{key}")
    async def close_session(key: str,request: Request):
        body=await body_json(request)
        await anyio.to_thread.run_sync(lambda: engine.close_session(key,body.get("token")))
        return {"removed":True}

    @app.post("/api/sessions/{key}/context")
    async def context(key: str,request: Request):
        body=await body_json(request)
        with engine.lock:
            session=engine.session(key,body.get("token"))
            return dict(session.context,active=session is engine.current and session.cache is not None)

    @app.get("/api/presets")
    async def presets():
        return [{"id": key, **spec} for key, spec in PRESETS.items()]

    @app.get("/api/presets/{key}/asset")
    async def preset_asset(key: str):
        spec = PRESETS.get(key)
        if not spec or "filename" not in spec:
            return JSONResponse({"code": "unknown_preset"}, status_code=404)
        return FileResponse(BASE / "samples" / spec["filename"], media_type="audio/wav" if key == "audio" else "image/png")

    @app.post("/api/uploads")
    async def upload(request: Request):
        data = await body_bytes(request, MAX_UPLOAD)
        return await anyio.to_thread.run_sync(lambda: engine.uploads.create(data))

    @app.delete("/api/uploads/{key}")
    async def discard(key: str, request: Request):
        body = await body_json(request)
        engine.uploads.discard(key, body.get("token", ""))
        return {"removed": True}

    @app.post("/api/jobs/{key}/cancel")
    async def cancel(key: str, request: Request):
        body = await body_json(request)
        await anyio.to_thread.run_sync(lambda: engine.cancel(key, body.get("token")))
        return {"stopped": True}

    @app.post("/api/generate")
    async def generate(request: Request):
        body = await body_json(request)
        job = await anyio.to_thread.run_sync(lambda: engine.submit(body))

        def event(name, value):
            return "event: " + name + "\ndata: " + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n\n"

        async def events():
            try:
                yield event("start", {"job_id": job.id, "token": job.token, "kind": job.kind})
                ping = time.monotonic()
                while True:
                    # Once done is observed, the producer cannot enqueue more
                    # events. Drain everything it queued before sending terminal.
                    done = job.done.is_set()
                    try:
                        name, value = job.events.get_nowait()
                        yield event(name, value)
                    except queue.Empty:
                        if done:
                            terminal = job.terminal or ("error", {"code": "inference_failed"})
                            yield event(*terminal)
                            break
                        if time.monotonic() - ping > 10:
                            yield ": keepalive\n\n"
                            ping = time.monotonic()
                        await asyncio.sleep(.03)
            finally:
                # Disconnect, Stop and shutdown all await the real provider call.
                with anyio.CancelScope(shield=True):
                    await anyio.to_thread.run_sync(job.cancel_and_wait)

        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
    return app


def main():
    p = argparse.ArgumentParser(description="Pandora Qwen2.5-Omni text-output Web Demo")
    p.add_argument("--model", required=True)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=7860)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = create_app(args.model, args.run_dir)

    class OwnedServer(uvicorn.Server):
        async def shutdown(self, sockets=None):
            # Cancel the native job before Uvicorn waits for SSE connections.
            engine = getattr(app.state, "engine", None)
            if engine is not None:
                with anyio.CancelScope(shield=True):
                    await anyio.to_thread.run_sync(engine.quiesce)
            await super().shutdown(sockets=sockets)

    server = OwnedServer(uvicorn.Config(app, host=args.host, port=args.port, workers=1, timeout_graceful_shutdown=5))
    # This CLI owns its process signal policy. A vendor's startup system() call
    # temporarily ignores SIGINT; a blocked signal remains available to sigwait.
    # The SDK itself never installs handlers or masks in embedding applications.
    watched = {signal.SIGINT, signal.SIGTERM}
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, watched)
    stopping = threading.Event()

    def watch_shutdown():
        while not stopping.is_set():
            info = signal.sigtimedwait(watched, .1)
            if info is not None:
                # Uvicorn observes this after startup or at its next loop tick.
                # Repeated signals keep the same graceful cleanup path.
                server.should_exit = True

    watcher = threading.Thread(target=watch_shutdown, name="omni-shutdown", daemon=False)
    try:
        watcher.start()
        server.run()
    finally:
        stopping.set()
        if watcher.ident is not None:
            watcher.join()
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


if __name__ == "__main__":
    main()
