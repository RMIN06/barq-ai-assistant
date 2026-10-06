"""
Health check and metrics endpoints for Barq service.
"""
import os
import psutil
import time
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from config import GROQ_API_KEY, DEEPGRAM_API_KEY
from barqlog import get_logger

log = get_logger("health")

router = APIRouter(prefix="/health", tags=["health"])

# Prometheus metrics
REQUEST_COUNT = Counter("barq_requests_total", "Total requests", ["endpoint", "status"])
REQUEST_LATENCY = Histogram("barq_request_latency_seconds", "Request latency", ["endpoint"])
MEMORY_USAGE = Gauge("barq_memory_bytes", "Memory usage in bytes")
CPU_USAGE = Gauge("barq_cpu_percent", "CPU usage percent")
WAKE_DETECTIONS = Counter("barq_wake_detections_total", "Total wake word detections")
COMMANDS_PROCESSED = Counter("barq_commands_processed_total", "Total commands processed", ["intent"])
ERRORS = Counter("barq_errors_total", "Total errors", ["component"])


def check_groq_api() -> Dict[str, Any]:
    """Check Groq API connectivity."""
    if not GROQ_API_KEY:
        return {"status": "unconfigured", "message": "GROQ_API_KEY not set"}
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        models = client.models.list()
        return {"status": "healthy", "models": len(models.data)}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


def check_deepgram_api() -> Dict[str, Any]:
    """Check Deepgram API connectivity."""
    if not DEEPGRAM_API_KEY:
        return {"status": "unconfigured", "message": "DEEPGRAM_API_KEY not set"}
    try:
        import requests
        headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
        resp = requests.get("https://api.deepgram.com/v1/projects", headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return {"status": "healthy", "projects": len(data.get("projects", []))}
        else:
            return {"status": "unhealthy", "message": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


_microphone_cache = {"result": None, "timestamp": 0}

def check_microphone() -> Dict[str, Any]:
    """Check microphone availability using sounddevice blocking mode (like wake detection)."""
    global _microphone_cache
    import time
    now = time.time()
    if _microphone_cache["result"] and (now - _microphone_cache["timestamp"]) < 300:
        return _microphone_cache["result"]

    try:
        import sounddevice as sd
        import numpy as np
        # Test with a short blocking recording (same as wake detection)
        recording = sd.rec(16000, samplerate=16000, channels=1, dtype='float32')
        sd.wait()
        rms = np.sqrt(np.mean(recording**2))
        result = {"status": "healthy", "message": f"Microphone accessible via sounddevice (RMS: {rms:.6f})"}
    except OSError as e:
        if "No Default Input Device" in str(e) or "Error querying device" in str(e) or "Invalid device" in str(e):
            result = {"status": "unavailable", "message": "No microphone available (headless mode)"}
        else:
            result = {"status": "unhealthy", "message": str(e)}
    except Exception as e:
        result = {"status": "unhealthy", "message": str(e)}

    _microphone_cache = {"result": result, "timestamp": time.time()}
    return result


_speaker_cache = {"result": None, "timestamp": 0}


def check_speaker() -> Dict[str, Any]:
    """Check speaker/audio output availability (cached)."""
    global _speaker_cache
    import time
    now = time.time()
    if _speaker_cache["result"] and (now - _speaker_cache["timestamp"]) < 300:
        return _speaker_cache["result"]

    try:
        import pygame
        pygame.mixer.init()
        result = {"status": "healthy", "message": "Audio output available"}
    except Exception as e:
        if "WASAPI" in str(e) or "audio endpoint" in str(e):
            result = {"status": "unavailable", "message": "No audio output (headless mode)"}
        else:
            result = {"status": "unhealthy", "message": str(e)}

    _speaker_cache = {"result": result, "timestamp": time.time()}
    return result


def check_disk_space() -> Dict[str, Any]:
    """Check available disk space."""
    try:
        usage = psutil.disk_usage(".")
        free_gb = usage.free / (1024**3)
        status = "healthy" if free_gb > 1 else "warning" if free_gb > 0.1 else "critical"
        return {"status": status, "free_gb": round(free_gb, 2)}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


def check_memory() -> Dict[str, Any]:
    """Check memory usage."""
    try:
        process = psutil.Process()
        mem_mb = process.memory_info().rss / (1024**2)
        MEMORY_USAGE.set(process.memory_info().rss)
        status = "healthy" if mem_mb < 500 else "warning" if mem_mb < 1000 else "critical"
        return {"status": status, "memory_mb": round(mem_mb, 1)}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


def check_cpu() -> Dict[str, Any]:
    """Check CPU usage."""
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        CPU_USAGE.set(cpu)
        status = "healthy" if cpu < 50 else "warning" if cpu < 80 else "critical"
        return {"status": status, "cpu_percent": cpu}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


@router.get("/live")
async def liveness():
    """Kubernetes-style liveness probe - always returns 200 if process is alive."""
    REQUEST_COUNT.labels(endpoint="/health/live", status="200").inc()
    return {"status": "alive"}


@router.get("/ready")
async def readiness():
    """Kubernetes-style readiness probe - checks all critical dependencies."""
    checks = {
        "groq": check_groq_api(),
        "deepgram": check_deepgram_api(),
        "microphone": check_microphone(),
        "speaker": check_speaker(),
        "disk": check_disk_space(),
        "memory": check_memory(),
        "cpu": check_cpu(),
    }

    unhealthy = [k for k, v in checks.items() if v["status"] == "unhealthy"]
    unconfigured = [k for k, v in checks.items() if v["status"] == "unconfigured"]

    if unhealthy:
        REQUEST_COUNT.labels(endpoint="/health/ready", status="503").inc()
        return Response(
            content={"status": "not_ready", "checks": checks, "unhealthy": unhealthy},
            status_code=503,
            media_type="application/json"
        )

    if unconfigured:
        REQUEST_COUNT.labels(endpoint="/health/ready", status="200").inc()
        return {"status": "degraded", "checks": checks, "unconfigured": unconfigured}

    REQUEST_COUNT.labels(endpoint="/health/ready", status="200").inc()
    return {"status": "ready", "checks": checks}


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/")
async def health_root():
    """Combined health check."""
    checks = {
        "groq": check_groq_api(),
        "deepgram": check_deepgram_api(),
        "microphone": check_microphone(),
        "speaker": check_speaker(),
        "disk": check_disk_space(),
        "memory": check_memory(),
        "cpu": check_cpu(),
    }

    overall = "healthy"
    for v in checks.values():
        if v["status"] == "unhealthy":
            overall = "unhealthy"
            break
        elif v["status"] in ("warning", "critical", "unconfigured", "unavailable"):
            overall = "degraded"

    return {"status": overall, "checks": checks, "timestamp": time.time()}


def record_wake_detection():
    WAKE_DETECTIONS.inc()


def record_command(intent: str):
    COMMANDS_PROCESSED.labels(intent=intent).inc()


def record_error(component: str):
    ERRORS.labels(component=component).inc()