"""Ortak yetkilendirme yardımcıları.

Admin kapısı YALNIZCA imzalı JWT'deki `is_admin` bayrağıyla açılır (C1 güvenlik
düzeltmesi). Bayrak login sırasında DB'deki `User.is_admin`'den gömülür; kayıt her
zaman False üretir, dolayısıyla kullanıcı forge edemez. E-posta string'iyle
KAPILAMAZ (kayıt açık olduğundan dikey yetki yükseltmeye yol açardı).
"""
from fastapi import Depends, HTTPException

from app.dependencies import get_current_user


async def require_admin(current_user: dict) -> None:
    """Handler gövdesi içinden çağrı için: admin değilse 403 fırlatır."""
    if current_user.get("is_admin") is not True:
        raise HTTPException(status_code=403, detail="Admin access required")


def require_admin_dep(current_user: dict = Depends(get_current_user)) -> dict:
    """Route bağımlılığı olarak kullanım için (`dependencies=[Depends(require_admin_dep)]`
    veya `current_user: dict = Depends(require_admin_dep)`). Admin JWT'yi doğrular,
    current_user sözlüğünü döndürür."""
    if current_user.get("is_admin") is not True:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
