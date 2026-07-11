"""Event payload'larındaki sırların şifrelenmesi (M2 güvenlik bulgusu).

Credential'lar RabbitMQ'ya düz metin gitmesin: gateway sırları tek bir
`enc_credentials` alanına Fernet ile paketler; tüketici servis (store-deploy)
aynı SECRET_KEY/FERNET_SALT türetimiyle çözer. Düz-metin alanlar payload'a
konmaz — broker compromise/mgmt-UI yüzeyi kapanır.
"""
import json

from app.crypto import encrypt


def pack_secrets(payload: dict, secrets: dict) -> dict:
    """Sır alanlarını payload'dan ayırıp şifreli tek alana koy.

    None değerler de paketlenir (tüketici eksik-credential hatasını kendisi verir).
    """
    payload = dict(payload)
    payload["enc_credentials"] = encrypt(json.dumps(secrets))
    return payload
