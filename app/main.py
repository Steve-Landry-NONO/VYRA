"""Vyra's small, self-hosted download service.

Only public, authorized videos should be processed. This server does not accept
credentials, browser cookies, or private account access.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import secrets
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
logger = logging.getLogger("vyra.diagnostics")
STORAGE_DIR = Path(os.getenv("VYRA_STORAGE_DIR", str(Path(tempfile.gettempdir()) / "vyra-media")))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
MAX_DURATION = int(os.getenv("VYRA_MAX_DURATION_SECONDS", "7200"))
MAX_FILE_BYTES = int(os.getenv("VYRA_MAX_FILE_BYTES", str(500 * 1024 * 1024)))
INSPECT_TTL = 10 * 60
FILE_TTL = 45 * 60
MAX_PENDING = 6

@asynccontextmanager
async def application_lifespan(application: FastAPI):
    start_optional_diagnostic()
    yield


app = FastAPI(title="Vyra Downloader", version="2.1.0", docs_url=None, redoc_url=None, lifespan=application_lifespan)
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="vyra-worker")
state_lock = threading.RLock()
rate_lock = threading.Lock()
inspections: dict[str, dict[str, Any]] = {}
jobs: dict[str, "Job"] = {}
rate_history: dict[str, deque[float]] = defaultdict(deque)

DOMAINS: dict[str, set[str]] = {
    "YouTube": {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be", "www.youtu.be"},
    "Instagram": {"instagram.com", "www.instagram.com", "m.instagram.com"},
    "TikTok": {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"},
    "Snapchat · bêta": {"snapchat.com", "www.snapchat.com", "t.snapchat.com"},
}


class InspectRequest(BaseModel):
    url: str = Field(min_length=12, max_length=2000)


class DownloadRequest(BaseModel):
    inspection_id: str = Field(min_length=32, max_length=40)
    format: str = Field(pattern="^(mp4|mp3)$")
    quality: str = Field(max_length=6)


@dataclass
class Job:
    id: str
    title: str
    platform: str
    format: str
    quality: str
    url: str
    created_at: float = field(default_factory=time.time)
    status: str = "queued"
    progress: int = 0
    message: str = "En attente d’un créneau…"
    error: str | None = None
    file_path: Path | None = None
    filename: str | None = None


def platform_from_url(raw_url: str) -> str:
    """Reject arbitrary URLs, hosts, schemes, ports, and credentials (SSRF guard)."""
    try:
        url = urlsplit(raw_url.strip())
        hostname = (url.hostname or "").lower().rstrip(".")
        if (
            url.scheme != "https"
            or url.username is not None
            or url.password is not None
            or url.port is not None
            or "\\" in raw_url
            or not url.path
            or url.path == "/"
        ):
            raise ValueError("URL non autorisée")
    except ValueError:
        raise HTTPException(status_code=422, detail="Utilise un lien HTTPS public vers une vidéo.")
    for name, domains in DOMAINS.items():
        if hostname not in domains:
            continue
        path = url.path.lower()
        if name == "YouTube" and hostname.endswith("youtube.com"):
            valid_path = path == "/watch" or any(
                path.startswith(prefix) and len(path) > len(prefix)
                for prefix in ("/shorts/", "/live/", "/embed/", "/v/")
            )
        elif name == "Instagram":
            valid_path = any(path.startswith(prefix) and len(path) > len(prefix)
                             for prefix in ("/reel/", "/p/", "/tv/", "/stories/"))
        elif name == "TikTok" and hostname not in ("vm.tiktok.com", "vt.tiktok.com"):
            valid_path = ("/video/" in path or path.startswith("/t/") or path.startswith("/v/"))
        elif name.startswith("Snapchat") and hostname != "t.snapchat.com":
            valid_path = path.startswith(("/spotlight/", "/story/", "/@", "/add/"))
        else:
            valid_path = True
        if not valid_path:
            raise HTTPException(status_code=422, detail="Utilise le lien direct d’une vidéo, d’un Reel ou d’une Story publique.")
        return name
    raise HTTPException(status_code=422, detail="Plateforme non prise en charge. Utilise YouTube, Instagram, TikTok ou Snapchat public.")


def throttle(request: Request, action: str, limit: int) -> None:
    # Do not trust X-Forwarded-For unless a trusted proxy is explicitly configured.
    ip = request.client.host if request.client else "unknown"
    key = f"{ip}:{action}"
    now = time.monotonic()
    with rate_lock:
        history = rate_history[key]
        while history and now - history[0] > 60:
            history.popleft()
        if len(history) >= limit:
            raise HTTPException(status_code=429, detail="Trop de demandes. Réessaie dans une minute.")
        history.append(now)


def prune() -> None:
    now = time.time()
    with state_lock:
        for key, item in list(inspections.items()):
            if now - item["created_at"] > INSPECT_TTL:
                del inspections[key]
        for key, job in list(jobs.items()):
            if job.status in ("ready", "error") and now - job.created_at > FILE_TTL:
                if job.file_path:
                    shutil.rmtree(job.file_path.parent, ignore_errors=True)
                del jobs[key]


def failure_category(exc: Exception) -> str:
    """Return a non-sensitive diagnostic category; never log a video URL or token."""
    message = str(exc).lower()
    if "confirm you're not a bot" in message or "confirm you’re not a bot" in message or "unusual traffic" in message:
        return "youtube_bot_check"
    if "no supported javascript runtime" in message or "n challenge solving failed" in message or "signature solving failed" in message:
        return "youtube_javascript"
    if "http error 429" in message or "too many requests" in message:
        return "rate_limited"
    if "http error 403" in message or "forbidden" in message:
        return "access_forbidden"
    if "login" in message or "sign in" in message or "cookies" in message or "authentication" in message or "members-only" in message:
        return "login_required"
    if "private" in message or "not available" in message or "unavailable" in message:
        return "video_unavailable"
    if "unsupported url" in message or "no suitable extractor" in message:
        return "unsupported_url"
    if "too long" in message or "duration" in message:
        return "duration_limit"
    if "file is larger" in message or "max-filesize" in message or "maximum file size" in message:
        return "size_limit"
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return "timeout"
    return "unknown"


def readable_error(exc: Exception) -> str:
    """Keep frontend responses accurate without disclosing private extractor traces."""
    category = failure_category(exc)
    explanations = {
        "youtube_bot_check": "YouTube demande une vérification anti-robot au serveur VYRA. La vidéo peut être publique : cela ne signifie pas que vous devez vous connecter. Essaie VYRA localement ou réessaie plus tard.",
        "youtube_javascript": "YouTube nécessite un composant JavaScript supplémentaire. La configuration du moteur doit être vérifiée.",
        "rate_limited": "La plateforme limite temporairement les requêtes du serveur. Réessaie plus tard.",
        "access_forbidden": "La plateforme refuse l’accès depuis ce serveur (HTTP 403). Le contenu peut pourtant être public.",
        "login_required": "Ce contenu nécessite une authentification que VYRA n’utilise pas.",
        "video_unavailable": "Cette vidéo est privée, indisponible ou retirée de la plateforme.",
        "unsupported_url": "Ce type de lien n’est pas encore pris en charge. Essaie un lien direct vers une vidéo publique.",
        "duration_limit": "La vidéo dépasse la durée autorisée sur ce serveur.",
        "size_limit": "Le fichier dépasse la taille maximale autorisée sur ce serveur.",
        "timeout": "La plateforme n’a pas répondu à temps. Réessaie dans quelques instants.",
    }
    return explanations.get(category, "L’analyse de cette vidéo a échoué. Consulte le diagnostic du serveur ou essaie un autre lien public.")


def record_failure(stage: str, platform: str, exc: Exception) -> None:
    """Store only error category and exception class, never URLs, cookies or tokens."""
    logger.warning("Echec VYRA etape=%s plateforme=%s categorie=%s type=%s",
                   stage, platform, failure_category(exc), type(exc).__name__)


def smoke_test_youtube() -> None:
    """One-off diagnostic enabled only with a URL supplied in Render env vars."""
    url = os.getenv("VYRA_DIAGNOSTIC_URL", "").strip()
    if not url:
        return
    try:
        if platform_from_url(url) != "YouTube":
            logger.warning("Diagnostic YouTube ignoré : domaine non autorisé")
            return
        metadata_from_url(url)
    except Exception as exc:
        record_failure("diagnostic", "YouTube", exc)
    else:
        logger.info("Diagnostic YouTube : extraction des metadonnees reussie")


def start_optional_diagnostic() -> None:
    if os.getenv("VYRA_DIAGNOSTIC_URL", "").strip():
        executor.submit(smoke_test_youtube)


def metadata_from_url(url: str) -> dict[str, Any]:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise RuntimeError("Le moteur yt-dlp n’est pas installé. Consulte le README.") from exc

    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
        "socket_timeout": 15,
        "retries": 2,
        "playlistend": 1,
        "ignoreerrors": False,
        "logger": SilentLogger(),
        "js_runtimes": {"node": {}},
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
    if not isinstance(info, dict):
        raise ValueError("Aucune vidéo détectée")
    if info.get("entries") is not None or info.get("_type") in {"playlist", "multi_video"}:
        raise ValueError("Ce lien renvoie une sélection de contenus plutôt qu’une vidéo unique")
    if info.get("is_live"):
        raise ValueError("Les diffusions en direct ne sont pas prises en charge")
    duration = info.get("duration")
    if duration is not None and duration > MAX_DURATION:
        raise ValueError("duration: too long")
    formats = info.get("formats") or []
    heights: set[int] = set()
    for item in formats:
        if not isinstance(item, dict):
            continue
        height = item.get("height")
        if item.get("vcodec") != "none" and isinstance(height, (int, float)) and 0 < height <= 4320:
            heights.add(int(height))
    if not heights and isinstance(info.get("height"), int) and info["height"] > 0:
        heights.add(info["height"])

    thumbnail = str(info.get("thumbnail") or "")
    if not thumbnail.startswith("https://"):
        thumbnail = ""

    return {
        "title": str(info.get("title") or "Vidéo sans titre")[:180],
        "creator": str(info.get("uploader") or info.get("channel") or "Créateur non renseigné")[:100],
        "duration": duration if isinstance(duration, (int, float)) else None,
        "thumbnail": thumbnail,
        "heights": sorted(heights, reverse=True)[:12],
        "id": str(info.get("id") or "")[:100],
    }


class SilentLogger:
    def debug(self, msg: str) -> None:  # noqa: ARG002
        pass

    def warning(self, msg: str) -> None:  # noqa: ARG002
        pass

    def error(self, msg: str) -> None:  # noqa: ARG002
        pass


def run_download(job: Job) -> None:
    folder = STORAGE_DIR / job.id
    folder.mkdir(parents=True, exist_ok=True)
    try:
        from yt_dlp import YoutubeDL

        def progress_hook(data: dict[str, Any]) -> None:
            with state_lock:
                if data.get("status") == "downloading":
                    total = data.get("total_bytes") or data.get("total_bytes_estimate")
                    downloaded = data.get("downloaded_bytes", 0)
                    job.status = "downloading"
                    job.message = "Téléchargement de la vidéo…"
                    if total:
                        job.progress = max(job.progress, min(89, int(downloaded / total * 89)))
                elif data.get("status") == "finished":
                    job.status = "converting"
                    job.progress = max(job.progress, 92)
                    job.message = "Préparation du fichier…"

        def post_hook(data: dict[str, Any]) -> None:
            if data.get("status") == "started":
                with state_lock:
                    job.status = "converting"
                    job.progress = max(job.progress, 92)
                    job.message = "Conversion du format…"

        with state_lock:
            job.status = "downloading"
            job.message = "Connexion à la plateforme…"

        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "outtmpl": str(folder / "media.%(ext)s"),
            "paths": {"home": str(folder)},
            "socket_timeout": 20,
            "retries": 3,
            "fragment_retries": 3,
            "max_filesize": MAX_FILE_BYTES,
            "max_downloads": 1,
            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [post_hook],
            "logger": SilentLogger(),
            "js_runtimes": {"node": {}},
        }
        if job.format == "mp3":
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"
            }]
        else:
            if job.quality == "best":
                opts["format"] = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b"
            else:
                height = int(job.quality)
                opts["format"] = (
                    f"bv*[height<={height}][ext=mp4]+ba[ext=m4a]/"
                    f"b[height<={height}][ext=mp4]/"
                    f"bv*[height<={height}]+ba/b[height<={height}]"
                )
            opts["merge_output_format"] = "mp4"
            opts["recodevideo"] = "mp4"

        with YoutubeDL(opts) as ydl:
            ydl.download([job.url])

        candidates = [
            p for p in folder.glob("media.*")
            if p.is_file() and p.suffix.lower() == f".{job.format}"
        ]
        if not candidates:
            raise RuntimeError("Le fichier final n’a pas été créé")
        final = max(candidates, key=lambda path: path.stat().st_mtime)
        if final.stat().st_size > MAX_FILE_BYTES:
            raise RuntimeError("maximum file size")
        safe_title = re.sub(r"[\\/\x00-\x1f\x7f]+", " ", job.title).strip(" .")[:85] or "video"
        with state_lock:
            job.file_path = final
            job.filename = f"{safe_title}.{job.format}"
            job.status = "ready"
            job.progress = 100
            job.message = "Ton fichier est prêt !"
    except Exception as exc:
        record_failure("download", job.platform, exc)
        shutil.rmtree(folder, ignore_errors=True)
        with state_lock:
            job.status = "error"
            job.error = readable_error(exc)
            job.message = "Le traitement a échoué."


@app.middleware("http")
async def test_access_gate(request: Request, call_next):
    """Protect a hosted test instance with Basic Auth; never store its secret in Git.

    Local development remains open unless VYRA_REQUIRE_AUTH=1 is explicitly set.
    The health endpoint is public so hosting probes can detect a healthy instance.
    """
    if os.getenv("VYRA_REQUIRE_AUTH") != "1" or request.url.path == "/api/health":
        return await call_next(request)

    password = os.getenv("VYRA_ACCESS_PASSWORD", "")
    if not password:
        return JSONResponse(status_code=503, content={"detail": "Accès de test non configuré."})

    expected_user = os.getenv("VYRA_ACCESS_USER", "testeur")
    authorization = request.headers.get("Authorization", "")
    accepted = False
    if authorization.startswith("Basic ") and len(authorization) < 4096:
        try:
            raw = base64.b64decode(authorization[6:], validate=True).decode("utf-8")
            if ":" in raw:
                user, provided = raw.split(":", 1)
                accepted = secrets.compare_digest(user, expected_user) and secrets.compare_digest(provided, password)
        except (ValueError, UnicodeError, binascii.Error):
            pass
    if not accepted:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentification requise pour la version de test."},
            headers={"WWW-Authenticate": 'Basic realm="VYRA - Acces de test", charset="UTF-8"'},
        )
    return await call_next(request)


@app.get("/api/health")
def health() -> dict[str, Any]:
    try:
        import yt_dlp  # noqa: F401
        engine = True
    except ImportError:
        engine = False
    return {"ok": True, "engine": engine, "ffmpeg": shutil.which("ffmpeg") is not None}


@app.post("/api/inspect")
async def inspect(request: Request, payload: InspectRequest) -> dict[str, Any]:
    throttle(request, "inspect", 12)
    prune()
    url = payload.url.strip()
    platform = platform_from_url(url)
    try:
        meta = await asyncio.wait_for(asyncio.to_thread(metadata_from_url, url), timeout=75)
    except Exception as exc:
        record_failure("inspect", platform, exc)
        raise HTTPException(status_code=422, detail=readable_error(exc)) from exc
    inspection_id = uuid.uuid4().hex
    with state_lock:
        inspections[inspection_id] = {"url": url, "platform": platform, "meta": meta, "created_at": time.time()}
    return {"inspection_id": inspection_id, "platform": platform, **meta}


@app.post("/api/download", status_code=202)
async def download(request: Request, payload: DownloadRequest) -> dict[str, Any]:
    throttle(request, "download", 5)
    prune()
    with state_lock:
        item = inspections.get(payload.inspection_id)
        if not item:
            raise HTTPException(status_code=410, detail="L’analyse a expiré. Analyse de nouveau ton lien.")
        if payload.format == "mp3":
            if payload.quality != "audio":
                raise HTTPException(status_code=422, detail="Format audio invalide.")
        elif payload.quality != "best" and payload.quality not in {str(x) for x in item["meta"]["heights"]}:
            raise HTTPException(status_code=422, detail="Cette résolution n’est pas disponible pour cette vidéo.")
        if sum(j.status in ("queued", "downloading", "converting") for j in jobs.values()) >= MAX_PENDING:
            raise HTTPException(status_code=429, detail="Le service est occupé. Réessaie dans un instant.")
        job = Job(
            id=uuid.uuid4().hex, title=item["meta"]["title"], platform=item["platform"],
            format=payload.format, quality=payload.quality, url=item["url"]
        )
        jobs[job.id] = job
        executor.submit(run_download, job)
    return {"job_id": job.id, "status": job.status}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    prune()
    with state_lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Téléchargement introuvable ou expiré.")
        return {
            "id": job.id,
            "status": job.status,
            "progress": job.progress,
            "message": job.message,
            "error": job.error,
            "filename": job.filename,
            "download_url": f"/api/jobs/{job.id}/file" if job.status == "ready" else None,
        }


@app.get("/api/jobs/{job_id}/file")
def job_file(job_id: str):
    prune()
    with state_lock:
        job = jobs.get(job_id)
        if job is None or job.status != "ready" or job.file_path is None:
            raise HTTPException(status_code=404, detail="Ce fichier n’est pas disponible.")
        if not job.file_path.is_file():
            raise HTTPException(status_code=404, detail="Le fichier a expiré.")
        return FileResponse(
            path=job.file_path,
            media_type="audio/mpeg" if job.format == "mp3" else "video/mp4",
            filename=job.filename,
            content_disposition_type="attachment",
        )


from .upload_api import router as upload_router
app.include_router(upload_router)

app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
