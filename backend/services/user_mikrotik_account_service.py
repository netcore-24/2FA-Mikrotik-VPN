"""
Сервис для управления привязками MikroTik-аккаунтов к пользователям системы.
"""

from __future__ import annotations

from typing import List
from sqlalchemy.orm import Session

from backend.models.user import User
from backend.models.user_mikrotik_account import UserMikrotikAccount
from backend.services.mikrotik_service import get_mikrotik_users_with_info, MikroTikConnectionError


def get_user_mikrotik_usernames(db: Session, user_id: str) -> List[str]:
    accounts = (
        db.query(UserMikrotikAccount)
        .filter(UserMikrotikAccount.user_id == user_id, UserMikrotikAccount.is_active == True)  # noqa: E712
        .order_by(UserMikrotikAccount.created_at.asc())
        .all()
    )
    return [a.mikrotik_username for a in accounts]


def set_user_mikrotik_usernames(db: Session, user_id: str, usernames: List[str]) -> List[str]:
    """
    Установить список MikroTik usernames для пользователя.
    Ограничение: максимум 2.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    cleaned: List[str] = []
    for u in usernames or []:
        if u is None:
            continue
        u = str(u).strip()
        if not u:
            continue
        if u not in cleaned:
            cleaned.append(u)

    if len(cleaned) > 2:
        raise ValueError("Можно привязать максимум 2 учетные записи MikroTik к одному пользователю Telegram")

    # Проверяем, что такие пользователи существуют на MikroTik (UM или PPP),
    # чтобы бот мог гарантированно включать/выключать нужную учётку.
    if cleaned:
        try:
            mikrotik_users, _source, _warning = get_mikrotik_users_with_info(db)
            existing_names = {
                (u.get("name") or u.get("username") or u.get("user"))
                for u in mikrotik_users
                if isinstance(u, dict)
            }
            missing = [u for u in cleaned if u not in existing_names]
            if missing:
                raise ValueError(
                    "На MikroTik не найдены пользователи: " + ", ".join(missing)
                )
        except MikroTikConnectionError as e:
            raise ValueError(f"Не удалось проверить пользователей на MikroTik: {str(e)}") from e

    # Проверяем, что username не привязан к другому пользователю
    for u in cleaned:
        existing = (
            db.query(UserMikrotikAccount)
            .filter(UserMikrotikAccount.mikrotik_username == u, UserMikrotikAccount.user_id != user_id)
            .first()
        )
        if existing:
            raise ValueError(f"MikroTik user '{u}' уже привязан к другому пользователю")

    # Текущее состояние
    current = (
        db.query(UserMikrotikAccount)
        .filter(UserMikrotikAccount.user_id == user_id)
        .all()
    )
    current_usernames = {a.mikrotik_username for a in current if a.is_active}
    desired = set(cleaned)

    # Деактивируем лишние
    for acc in current:
        if acc.mikrotik_username not in desired:
            db.delete(acc)

    # Добавляем недостающие
    for u in cleaned:
        if u not in current_usernames:
            db.add(UserMikrotikAccount(user_id=user_id, mikrotik_username=u, is_active=True))

    db.commit()
    return cleaned

