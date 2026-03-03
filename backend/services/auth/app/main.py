import time

from fastapi import FastAPI

_START_TIME = time.time()

app = FastAPI(title="Auth Service", version="0.9.0")


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "auth",
        "version": "0.9.0",
        "uptime_seconds": int(time.time() - _START_TIME),
    }
