"""Store Deploy Service -- test_rollout_exec.py

Staged rollout executor saf yardımcıları. Google/Apple API'lerine dokunmaz.
"""
import os
import sys

_APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
sys.path.insert(0, _APP_DIR)

from rollout_exec import _pick_release


def test_pick_release_prefers_status_order():
    releases = [{"status": "draft"}, {"status": "inProgress", "userFraction": 0.1}]
    assert _pick_release(releases, ("inProgress", "halted", "draft"))["status"] == "inProgress"


def test_pick_release_falls_back_to_first():
    # istenen statü yok → ilk release döner
    assert _pick_release([{"status": "completed"}], ("inProgress",))["status"] == "completed"


def test_pick_release_empty_returns_none():
    assert _pick_release([], ("inProgress",)) is None
