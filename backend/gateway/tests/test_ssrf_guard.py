"""SSRF guard birim testi (SAST H-A/M-C/M-D altyapısı)."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

from app.ssrf_guard import (
    check_external_url, is_safe_external_url, SSRFError,
    SLACK_WEBHOOK_HOSTS, DISCORD_WEBHOOK_HOSTS, GOOGLE_TOKEN_HOSTS,
)


@pytest.mark.parametrize("url", [
    "http://accounts.google.com/x",          # https değil
    "https://169.254.169.254/latest/meta",   # cloud metadata
    "https://localhost/x",                    # loopback
    "https://127.0.0.1/x",
    "https://10.0.0.5/x",                     # private
    "https://192.168.1.1/x",
    "https://[::1]/x",                        # ipv6 loopback
    "ftp://example.com/x",                    # şema
    "",                                       # boş
])
def test_blocks_unsafe(url):
    assert is_safe_external_url(url) is False
    with pytest.raises(SSRFError):
        check_external_url(url)


def test_allows_public_https():
    assert is_safe_external_url("https://accounts.google.com/.well-known/openid-configuration") is True


def test_host_allowlist():
    assert is_safe_external_url("https://hooks.slack.com/services/A/B", SLACK_WEBHOOK_HOSTS) is True
    assert is_safe_external_url("https://evil.com/x", SLACK_WEBHOOK_HOSTS) is False
    assert is_safe_external_url("https://discord.com/api/webhooks/1/2", DISCORD_WEBHOOK_HOSTS) is True
    assert is_safe_external_url("https://oauth2.googleapis.com/token", GOOGLE_TOKEN_HOSTS) is True
    assert is_safe_external_url("https://attacker.example/token", GOOGLE_TOKEN_HOSTS) is False
