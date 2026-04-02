"""
FastAPI backend for Plant Genesis Simulator.
Jobs run in background threads; videos are stored in a temp directory.
"""
from __future__ import annotations

import os
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from simulation.parameters import PlantJobRequest
from simulation.animator import generate_video
from simulation.fate import compute_fate

app = FastAPI(title="Plant Genesis Simulator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (replace with Redis/DB for production)
JOBS: Dict[str, Dict[str, Any]] = {}

OUTPUT_DIR = Path(tempfile.gettempdir()) / "plant_genesis"
OUTPUT_DIR.mkdir(exist_ok=True)


# ------------------------------------------------------------------
# Background worker
# ------------------------------------------------------------------
def _run_job(job_id: str, params: PlantJobRequest) -> None:
    JOBS[job_id]["status"] = "processing"
    output_path = str(OUTPUT_DIR / f"{job_id}.mp4")

    try:
        def _update(p: float) -> None:
            JOBS[job_id]["progress"] = round(p * 100)

        fate = compute_fate(params)
        generate_video(params, output_path, progress_callback=_update)

        JOBS[job_id].update(
            status="done",
            progress=100,
            video_path=output_path,
            fate={
                "survived": fate.survived,
                "risk_score": round(fate.risk_score, 3),
                "extinction_era": fate.extinction_era,
                "extinction_reason": fate.extinction_reason,
                "survival_note": fate.survival_note,
            },
        )
    except Exception as exc:
        JOBS[job_id].update(status="error", error=str(exc))


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/jobs", status_code=202)
def create_job(params: PlantJobRequest) -> dict:
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "params": params.model_dump(),
    }
    thread = threading.Thread(target=_run_job, args=(job_id, params), daemon=True)
    thread.start()
    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    job = {k: v for k, v in JOBS[job_id].items() if k != "video_path"}
    return job


@app.get("/videos/{job_id}")
def get_video(job_id: str) -> FileResponse:
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    job = JOBS[job_id]
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Video not ready yet")
    video_path = job.get("video_path", "")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file missing")
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"plant_{job_id[:8]}.mp4",
    )
