import time
import logging
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from prometheus_client import Counter, Gauge

logger = logging.getLogger(__name__)

WAF_BLOCKED = Counter("apptrack_waf_blocked_total", "Requests blocked by WAF", ["reason"])
WAF_SCORE_HIGH = Counter("apptrack_waf_high_score_total", "High risk score requests")
SUSPICIOUS_IPS = Gauge("apptrack_suspicious_ips", "Currently suspicious IPs")

SUSPICIOUS_PATTERNS = [
    "../", "..\\", "<script", "javascript:", "eval(", "exec(",
    "union select", "drop table", "insert into", "' or 1=1",
    "${", "{{", "%00", "\\x00",
]

SUSPICIOUS_HEADERS = ["x-forwarded-host", "x-original-url", "x-rewrite-url"]

MAX_SCORES: dict[str, list[tuple[float, float]]] = defaultdict(list)
BLOCKED_IPS: dict[str, float] = {}
IP_BLOCK_DURATION = 3600
SCORE_WINDOW = 300
SCORE_THRESHOLD = 50
REQUEST_RATE_WINDOW = 10
REQUEST_RATE_LIMIT = 50

_request_counts: dict[str, list[float]] = defaultdict(list)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _score_request(request: Request) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    path = request.url.path.lower()
    query = str(request.url.query).lower() if request.url.query else ""
    ua = (request.headers.get("user-agent") or "").lower()

    for pattern in SUSPICIOUS_PATTERNS:
        if pattern in path or pattern in query:
            score += 15
            reasons.append(f"suspicious_pattern:{pattern}")

    for h in SUSPICIOUS_HEADERS:
        if h in request.headers:
            score += 10
            reasons.append(f"suspicious_header:{h}")

    if not ua or ua == "-" or len(ua) < 5:
        score += 5
        reasons.append("missing_user_agent")

    bot_indicators = ["sqlmap", "nikto", "nmap", "masscan", "zgrab", "scrapy", "python-urllib"]
    for bot in bot_indicators:
        if bot in ua:
            score += 25
            reasons.append(f"known_scanner:{bot}")

    if ".env" in path or ".git" in path or "wp-admin" in path or ".php" in path:
        score += 20
        reasons.append("probe_path")

    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 50_000_000:
        score += 10
        reasons.append("oversized_body")

    return score, reasons


def _check_rate(ip: str) -> bool:
    now = time.time()
    _request_counts[ip] = [t for t in _request_counts[ip] if now - t < REQUEST_RATE_WINDOW]
    _request_counts[ip].append(now)
    return len(_request_counts[ip]) > REQUEST_RATE_LIMIT


class WAFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = _get_client_ip(request)
        now = time.time()

        if ip in BLOCKED_IPS:
            if now - BLOCKED_IPS[ip] < IP_BLOCK_DURATION:
                WAF_BLOCKED.labels(reason="ip_blocked").inc()
                return JSONResponse(status_code=403, content={"detail": "Access denied", "code": "WAF_BLOCKED"})
            else:
                del BLOCKED_IPS[ip]

        if _check_rate(ip):
            WAF_BLOCKED.labels(reason="rate_flood").inc()
            BLOCKED_IPS[ip] = now
            SUSPICIOUS_IPS.set(len(BLOCKED_IPS))
            logger.warning("WAF: IP %s blocked for rate flooding", ip)
            return JSONResponse(status_code=429, content={"detail": "Too many requests", "code": "WAF_RATE_FLOOD"})

        score, reasons = _score_request(request)

        MAX_SCORES[ip] = [(s, t) for s, t in MAX_SCORES[ip] if now - t < SCORE_WINDOW]
        if score > 0:
            MAX_SCORES[ip].append((score, now))

        cumulative = sum(s for s, _ in MAX_SCORES[ip])

        if cumulative >= SCORE_THRESHOLD:
            WAF_BLOCKED.labels(reason="high_score").inc()
            WAF_SCORE_HIGH.inc()
            BLOCKED_IPS[ip] = now
            SUSPICIOUS_IPS.set(len(BLOCKED_IPS))
            logger.warning("WAF: IP %s blocked (score=%d reasons=%s)", ip, cumulative, reasons)
            return JSONResponse(status_code=403, content={"detail": "Request blocked by security policy", "code": "WAF_SCORE_BLOCK"})

        request.state.waf_score = score
        request.state.waf_reasons = reasons

        response = await call_next(request)
        return response


def get_waf_stats() -> dict:
    now = time.time()
    active_blocks = {ip: int(now - t) for ip, t in BLOCKED_IPS.items() if now - t < IP_BLOCK_DURATION}
    return {
        "blocked_ips": len(active_blocks),
        "ips": active_blocks,
        "tracked_ips": len(MAX_SCORES),
    }
