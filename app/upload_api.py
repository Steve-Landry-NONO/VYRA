"""Import de fichiers déjà possédés pour conversion autorisée, sans accès aux réseaux sociaux.

Route distincte de yt-dlp : on ne tente pas de contourner les protections des plateformes.
Les données résident temporairement sur le disque éphémère de l'instance Render.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from . import main

router = APIRouter()
ALLOWED = {".mp4", ".webm", ".mov", ".mkv", ".m4v", ".mp3", ".m4a", ".wav", ".aac"}
VIDEO = {".mp4", ".webm", ".mov", ".mkv", ".m4v"}


def convert_uploaded(job: main.Job, source: Path) -> None:
    """Convertir le média fourni directement, sans requête à YouTube."""
    folder = source.parent
    target = folder / f"converted.{job.format}"
    try:
        with main.state_lock:
            job.status, job.progress = "converting", 35
            job.message = "Vérification du fichier importé…"
        check = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
             "-of", "json", str(source)],
            capture_output=True, text=True, check=True, timeout=25,
        )
        info = json.loads(check.stdout)
        duration = float(info.get("format", {}).get("duration", 0))
        streams = info.get("streams") or []
        if not 0 < duration <= main.MAX_DURATION:
            raise ValueError("duration: too long")
        if not streams:
            raise ValueError("Le fichier ne contient aucun flux multimédia.")
        if job.format == "mp4" and not any(s.get("codec_type") == "video" for s in streams):
            raise ValueError("Aucune piste vidéo dans ce fichier.")
        with main.state_lock:
            job.progress, job.message = 55, "Conversion par FFmpeg…"
        if job.format == "mp3":
            cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-threads", "1",
                   "-i", str(source), "-vn", "-map", "0:a:0", "-codec:a", "libmp3lame",
                   "-b:a", "192k", str(target)]
        else:
            cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-threads", "1",
                   "-i", str(source), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264",
                   "-preset", "ultrafast", "-crf", "27", "-pix_fmt", "yuv420p", "-c:a", "aac",
                   "-b:a", "128k", "-movflags", "+faststart", str(target)]
        subprocess.run(cmd, capture_output=True, check=True, timeout=min(main.MAX_DURATION * 3, 1200))
        if not target.is_file() or target.stat().st_size == 0:
            raise ValueError("Fichier converti absent ou vide.")
        if target.stat().st_size > main.MAX_FILE_BYTES:
            raise ValueError("maximum file size")
        source.unlink(missing_ok=True)
        with main.state_lock:
            job.file_path, job.filename = target, f"{job.title}.{job.format}"
            job.status, job.progress, job.message = "ready", 100, "Ton fichier converti est prêt !"
    except Exception as exc:
        main.record_failure("upload_conversion", "Fichier personnel", exc)
        shutil.rmtree(folder, ignore_errors=True)
        with main.state_lock:
            job.status, job.message = "error", "Conversion impossible."
            if isinstance(exc, subprocess.TimeoutExpired):
                job.error = "La conversion a dépassé sa durée maximale."
            elif "duration" in str(exc).lower():
                job.error = "La durée de ce fichier dépasse la limite de l'instance."
            elif "maximum file size" in str(exc).lower():
                job.error = "Le fichier converti dépasse la taille maximale."
            else:
                job.error = "Fichier illisible ou format incompatible avec la conversion demandée."


@router.post("/api/upload", status_code=202)
async def upload_and_convert(request: Request, file: UploadFile = File(...),
                             format: str = Form(...), rights_confirmed: bool = Form(False)):
    """Import autorisé et borné, réservé à l'instance protégée par mot de passe."""
    main.throttle(request, "upload", 3)
    main.prune()
    if not rights_confirmed:
        raise HTTPException(422, detail="Confirme que tu as le droit de traiter ce fichier.")
    if format not in {"mp4", "mp3"}:
        raise HTTPException(422, detail="Le format de sortie doit être MP4 ou MP3.")
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED:
        raise HTTPException(422, detail="Utilise MP4, MOV, WebM, MKV, M4V, MP3, M4A, WAV ou AAC.")
    if format == "mp4" and extension not in VIDEO:
        raise HTTPException(422, detail="Un fichier audio ne peut pas être transformé en vidéo MP4.")
    raw_size = request.headers.get("content-length")
    if raw_size and raw_size.isdigit() and int(raw_size) > main.MAX_FILE_BYTES + 1_048_576:
        raise HTTPException(413, detail="Fichier trop volumineux pour ce serveur.")
    with main.state_lock:
        running = sum(j.status in ("queued", "downloading", "converting") for j in main.jobs.values())
        if running >= main.MAX_PENDING:
            raise HTTPException(429, detail="Tous les créneaux de conversion sont occupés.")
    job_id = uuid.uuid4().hex
    folder = main.STORAGE_DIR / job_id
    folder.mkdir(parents=True, exist_ok=False)
    source = folder / f"uploaded{extension}"
    bytes_written = 0
    try:
        with source.open("wb") as dst:
            while chunk := await file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > main.MAX_FILE_BYTES:
                    raise HTTPException(413, detail="Fichier trop volumineux pour ce serveur.")
                dst.write(chunk)
        if not bytes_written:
            raise HTTPException(422, detail="Ce fichier est vide.")
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    finally:
        await file.close()

    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", Path(file.filename or "video").stem).strip("-")[:64] or "media"
    job = main.Job(id=job_id, title=safe_name, platform="Fichier personnel",
                   format=format, quality="original", url="")
    with main.state_lock:
        main.jobs[job_id] = job
        main.executor.submit(convert_uploaded, job, source)
    return {"job_id": job_id, "status": "queued"}
