import logging
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import Request
from sqlalchemy import select, func, and_
from prometheus_client import Counter, Gauge

logger = logging.getLogger(__name__)

ANOMALY_DETECTED = Counter("apptrack_anomaly_detected_total", "Anomaly detections", ["type", "severity"])
ANOMALY_ACTIVE = Gauge("apptrack_active_anomalies", "Currently active anomalies")

THRESHOLDS = {
    "builds_per_hour": {"warn": 20, "critical": 50},
    "deploys_per_hour": {"warn": 10, "critical": 30},
    "failed_builds_rate": {"warn": 0.5, "critical": 0.8},
    "credential_changes_per_hour": {"warn": 5, "critical": 15},
    "api_errors_per_minute": {"warn": 50, "critical": 200},
    "login_failures_per_hour": {"warn": 10, "critical": 30},
}

_activity_log: dict[str, list[tuple[str, float]]] = defaultdict(list)
_active_anomalies: list[dict] = []

import time


def record_activity(tenant_id: str, activity_type: str):
    now = time.time()
    _activity_log[tenant_id].append((activity_type, now))
    _activity_log[tenant_id] = [(a, t) for a, t in _activity_log[tenant_id] if now - t < 7200]


def check_tenant_anomalies(tenant_id: str) -> list[dict]:
    now = time.time()
    hour_ago = now - 3600
    minute_ago = now - 60

    activities = _activity_log.get(tenant_id, [])
    recent_hour = [(a, t) for a, t in activities if t >= hour_ago]
    recent_minute = [(a, t) for a, t in activities if t >= minute_ago]

    anomalies = []

    builds = [a for a, _ in recent_hour if a == "build_trigger"]
    if len(builds) >= THRESHOLDS["builds_per_hour"]["critical"]:
        anomalies.append({"type": "builds_per_hour", "severity": "critical", "value": len(builds), "threshold": THRESHOLDS["builds_per_hour"]["critical"]})
        ANOMALY_DETECTED.labels(type="builds_per_hour", severity="critical").inc()
    elif len(builds) >= THRESHOLDS["builds_per_hour"]["warn"]:
        anomalies.append({"type": "builds_per_hour", "severity": "warning", "value": len(builds), "threshold": THRESHOLDS["builds_per_hour"]["warn"]})
        ANOMALY_DETECTED.labels(type="builds_per_hour", severity="warning").inc()

    deploys = [a for a, _ in recent_hour if a == "deploy_trigger"]
    if len(deploys) >= THRESHOLDS["deploys_per_hour"]["critical"]:
        anomalies.append({"type": "deploys_per_hour", "severity": "critical", "value": len(deploys), "threshold": THRESHOLDS["deploys_per_hour"]["critical"]})
        ANOMALY_DETECTED.labels(type="deploys_per_hour", severity="critical").inc()

    cred_changes = [a for a, _ in recent_hour if a == "credential_change"]
    if len(cred_changes) >= THRESHOLDS["credential_changes_per_hour"]["critical"]:
        anomalies.append({"type": "credential_changes_per_hour", "severity": "critical", "value": len(cred_changes), "threshold": THRESHOLDS["credential_changes_per_hour"]["critical"]})
        ANOMALY_DETECTED.labels(type="credential_changes_per_hour", severity="critical").inc()

    login_failures = [a for a, _ in recent_hour if a == "login_failure"]
    if len(login_failures) >= THRESHOLDS["login_failures_per_hour"]["critical"]:
        anomalies.append({"type": "login_failures_per_hour", "severity": "critical", "value": len(login_failures), "threshold": THRESHOLDS["login_failures_per_hour"]["critical"]})
        ANOMALY_DETECTED.labels(type="login_failures_per_hour", severity="critical").inc()

    api_errors = [a for a, _ in recent_minute if a == "api_error"]
    if len(api_errors) >= THRESHOLDS["api_errors_per_minute"]["critical"]:
        anomalies.append({"type": "api_errors_per_minute", "severity": "critical", "value": len(api_errors), "threshold": THRESHOLDS["api_errors_per_minute"]["critical"]})

    if anomalies:
        ANOMALY_ACTIVE.set(len(anomalies))

    return anomalies


def get_all_anomalies() -> dict:
    now = time.time()
    result = {}
    for tenant_id in _activity_log:
        anomalies = check_tenant_anomalies(tenant_id)
        if anomalies:
            result[tenant_id] = anomalies
    return result
