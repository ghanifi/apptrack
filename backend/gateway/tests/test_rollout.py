"""AppTrack — Staged rollout + release health tests.

Saf mantık: fraction state machine, auto-halt eşik değerlendirme, Play Reporting parse.
Google/Apple API'leri ve DB'ye dokunmaz.
"""
import pytest

from app.routers.rollouts import next_fraction, ROLLOUT_STEPS
from app import release_health as rh


# ---- fraction state machine ----

def test_next_fraction_steps():
    assert next_fraction(0.01) == 0.1
    assert next_fraction(0.1) == 0.5
    assert next_fraction(0.5) == 1.0


def test_next_fraction_caps_at_full():
    assert next_fraction(1.0) == 1.0
    assert next_fraction(0.99) == 1.0


def test_next_fraction_from_start_of_steps():
    # başlangıç 0 → ilk adım
    assert next_fraction(0.0) == ROLLOUT_STEPS[0]


# ---- evaluate_halt ----

def _snap(cf, users=5000):
    return rh.HealthSnapshot(crash_free_rate=cf, distinct_users=users)


def test_halt_below_absolute_threshold():
    halt, reason = rh.evaluate_halt(_snap(0.985), threshold=0.99, baseline=None, min_users=1000)
    assert halt is True and "eşik" in reason


def test_no_halt_above_threshold():
    halt, reason = rh.evaluate_halt(_snap(0.995), threshold=0.99, baseline=None, min_users=1000)
    assert halt is False and reason is None


def test_min_users_guard_skips_evaluation():
    # kötü crash-free ama kullanıcı sayısı eşiğin altında → değerlendirme yok
    halt, _ = rh.evaluate_halt(_snap(0.10, users=50), threshold=0.99, baseline=None, min_users=1000)
    assert halt is False


def test_halt_on_baseline_drop():
    # mutlak eşiğin üstünde ama baseline'dan >0.5pp düşüş
    halt, reason = rh.evaluate_halt(_snap(0.992), threshold=0.99, baseline=0.999, min_users=1000)
    assert halt is True and "baseline" in reason


def test_no_halt_small_baseline_drop():
    # yalnız 0.3pp düşüş → halt yok
    halt, _ = rh.evaluate_halt(_snap(0.996), threshold=0.99, baseline=0.999, min_users=1000)
    assert halt is False


# ---- Play Reporting parse ----

def _crash_row(rate, users):
    return {"metrics": [
        {"metric": "userPerceivedCrashRate", "decimalValue": {"value": str(rate)}},
        {"metric": "distinctUsers", "decimalValue": {"value": str(users)}},
    ]}


def test_parse_crash_rate_basic():
    snap = rh._parse_crash_rate_response({"rows": [_crash_row(0.012, 1500)]})
    assert snap is not None
    assert abs(snap.crash_free_rate - 0.988) < 1e-9
    assert snap.distinct_users == 1500


def test_parse_crash_rate_picks_latest_row_with_data():
    rows = [_crash_row(0.05, 100), {"metrics": [{"metric": "distinctUsers", "decimalValue": {"value": "9"}}]}]
    # son satırda crash metriği yok → bir önceki (crash_rate 0.05) kullanılır
    snap = rh._parse_crash_rate_response({"rows": rows})
    assert snap is not None
    assert abs(snap.crash_free_rate - 0.95) < 1e-9


def test_parse_crash_rate_empty():
    assert rh._parse_crash_rate_response({"rows": []}) is None
    assert rh._parse_crash_rate_response({}) is None


def test_decimal_handles_formats():
    assert rh._decimal({"decimalValue": {"value": "0.5"}}) == 0.5
    assert rh._decimal({"value": "3"}) == 3.0
    assert rh._decimal({}) is None
    assert rh._decimal(None) is None


def test_crash_free_clamped():
    # crash rate > 1 gibi absürt değerde crash_free 0'a kırpılır
    snap = rh._parse_crash_rate_response({"rows": [_crash_row(1.5, 10)]})
    assert snap.crash_free_rate == 0.0


# ---- Sentry release health (iOS auto-halt) ----

def test_parse_sentry_sessions_fraction():
    resp = {"groups": [{"totals": {"crash_free_rate(user)": 0.9945, "count_unique(user)": 812}}]}
    snap = rh._parse_sentry_sessions(resp)
    assert snap and abs(snap.crash_free_rate - 0.9945) < 1e-9 and snap.distinct_users == 812


def test_parse_sentry_sessions_percentage_tolerated():
    resp = {"groups": [{"totals": {"crash_free_rate(user)": 99.45, "count_unique(user)": 10}}]}
    snap = rh._parse_sentry_sessions(resp)
    assert snap and abs(snap.crash_free_rate - 0.9945) < 1e-9


def test_parse_sentry_sessions_empty_or_missing():
    assert rh._parse_sentry_sessions({"groups": []}) is None
    assert rh._parse_sentry_sessions({}) is None
    assert rh._parse_sentry_sessions({"groups": [{"totals": {"count_unique(user)": 5}}]}) is None
