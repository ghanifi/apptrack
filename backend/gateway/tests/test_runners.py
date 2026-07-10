"""AppTrack — Self-hosted runner sihirbazı testleri.

Saf fonksiyonlar: kurulum bloğu üretimi, download eşleme, label çözümü.
GitHub API'ye ve DB'ye dokunmaz.
"""
from app.routers import runners as rn


# ---- pick_download ----

_DOWNLOADS = [
    {"os": "osx", "architecture": "arm64",
     "download_url": "https://github.com/actions/runner/releases/download/v2.335.1/actions-runner-osx-arm64-2.335.1.tar.gz",
     "filename": "actions-runner-osx-arm64-2.335.1.tar.gz"},
    {"os": "linux", "architecture": "x64",
     "download_url": "https://github.com/actions/runner/releases/download/v2.335.1/actions-runner-linux-x64-2.335.1.tar.gz",
     "filename": "actions-runner-linux-x64-2.335.1.tar.gz"},
]


def test_pick_download_matches_os_arch():
    got = rn.pick_download(_DOWNLOADS, "linux", "x64")
    assert got and "linux-x64" in got["filename"]


def test_pick_download_missing_returns_none():
    assert rn.pick_download(_DOWNLOADS, "win", "arm64") is None
    assert rn.pick_download([], "osx", "arm64") is None


# ---- resolve_labels ----

def test_resolve_labels_platform_defaults():
    assert rn.resolve_labels(None, "osx", "arm64") == "self-hosted,macOS,ARM64"
    assert rn.resolve_labels("", "linux", "x64") == "self-hosted,Linux,X64"
    assert rn.resolve_labels(None, "linux", "arm64") == "self-hosted,Linux,ARM64"


def test_resolve_labels_custom_wins():
    assert rn.resolve_labels("apptrack-ios, extra", "osx", "arm64") == "apptrack-ios,extra"


# ---- build_setup_script ----

def test_setup_script_osx_no_sudo():
    s = rn.build_setup_script(
        repo_url="https://github.com/o/r",
        download_url=_DOWNLOADS[0]["download_url"], filename=_DOWNLOADS[0]["filename"],
        token="REGTOK", labels="self-hosted,macOS,ARM64", os_name="osx")
    assert "--url https://github.com/o/r --token REGTOK" in s
    assert "--labels self-hosted,macOS,ARM64 --unattended --replace" in s
    assert "sudo" not in s  # macOS launchd: sudo'suz
    assert "./svc.sh install && ./svc.sh start" in s


def test_setup_script_linux_uses_sudo():
    s = rn.build_setup_script(
        repo_url="https://github.com/o/r",
        download_url=_DOWNLOADS[1]["download_url"], filename=_DOWNLOADS[1]["filename"],
        token="T", labels="self-hosted,Linux,X64", os_name="linux")
    assert "sudo ./svc.sh install && sudo ./svc.sh start" in s
    assert "actions-runner-linux-x64" in s


def test_setup_script_contains_full_flow():
    s = rn.build_setup_script("https://github.com/o/r", "https://dl/x.tar.gz", "x.tar.gz",
                              "T", "self-hosted", "osx")
    # sıra: mkdir → curl → tar → config → svc
    idx = [s.index(p) for p in ("mkdir", "curl", "tar xzf", "./config.sh", "svc.sh")]
    assert idx == sorted(idx)


# ---- _owner_repo ----

def test_owner_repo_parsing():
    assert rn._owner_repo("https://github.com/o/r.git") == "o/r"
    assert rn._owner_repo("https://github.com/o/r") == "o/r"
    assert rn._owner_repo("https://gitlab.com/o/r") == ""


# ---- JIT runner (saf) ----

def test_build_jit_script_flow_order():
    s = rn.build_jit_script("https://dl/x.tar.gz", "x.tar.gz", "ENCODED123")
    idx = [s.index(p) for p in ("mkdir", "curl", "tar xzf", "./run.sh --jitconfig ENCODED123")]
    assert idx == sorted(idx)
    assert "config.sh" not in s  # JIT'te config.sh yok


def test_build_jit_docker_command():
    cmd = rn.build_jit_docker_command("ENC")
    assert cmd.startswith("docker run --rm ghcr.io/actions/actions-runner")
    assert "--jitconfig ENC" in cmd
