"""SSRF koruması — kullanıcı-kontrollü URL'lere giden çıkış isteklerini kapılar.

Kullanıcının verdiği bir URL'yi (OIDC discovery, Slack/Discord webhook, Google
token_uri) sunucu tarafından fetch etmeden önce doğrula: yalnız https, host DNS'i
özel/loopback/link-local/metadata aralığına çözülüyorsa reddet. `allowed_hosts`
verilirse yalnız o host'lara izin verir (bilinen SaaS uçları için daha katı).

Not (artık risk): DNS-rebinding'e karşı tam koruma değildir — doğrulama anındaki
çözüm ile httpx'in yeniden çözümü arasında TOCTOU vardır. Düşük-frekanslı
config/webhook akışları için makul; tam koruma çözülen IP'yi pinlemeyi gerektirir.
"""
import ipaddress
import socket
from urllib.parse import urlparse


class SSRFError(ValueError):
    """URL SSRF politikasını ihlal ediyor."""


def _ip_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # çözülemeyen -> engelle
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
        or ip.is_multicast or ip.is_unspecified
        or ip_str == "169.254.169.254"  # cloud metadata
    )


def check_external_url(url: str, allowed_hosts: set[str] | None = None) -> str:
    """URL güvenliyse döndürür, değilse SSRFError fırlatır."""
    if not url or not isinstance(url, str):
        raise SSRFError("URL boş")
    try:
        p = urlparse(url)
    except Exception:
        raise SSRFError("Geçersiz URL")
    if p.scheme != "https":
        raise SSRFError("Yalnız https URL kabul edilir")
    host = p.hostname
    if not host:
        raise SSRFError("URL host'u yok")
    if allowed_hosts is not None and host.lower() not in {h.lower() for h in allowed_hosts}:
        raise SSRFError(f"İzin verilmeyen host: {host}")
    try:
        infos = socket.getaddrinfo(host, p.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise SSRFError("Host çözülemedi")
    for info in infos:
        if _ip_blocked(info[4][0]):
            raise SSRFError("Dahili/özel adrese istek engellendi")
    return url


def is_safe_external_url(url: str, allowed_hosts: set[str] | None = None) -> bool:
    """HTTP-dışı bağlamlar (arka plan worker) için bool sürüm."""
    try:
        check_external_url(url, allowed_hosts)
        return True
    except SSRFError:
        return False


# Bilinen SaaS webhook/token host'ları (host-allowlist)
SLACK_WEBHOOK_HOSTS = {"hooks.slack.com"}
DISCORD_WEBHOOK_HOSTS = {"discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com"}
GOOGLE_TOKEN_HOSTS = {"oauth2.googleapis.com", "accounts.google.com", "www.googleapis.com"}
