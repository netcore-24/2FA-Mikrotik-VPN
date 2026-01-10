"""
Сервис для аутентификации администраторов.
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from config.settings import settings
from backend.models.admin import Admin

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Хеширование пароля."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создание JWT токена для доступа."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Создание refresh токена."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    """Проверка и декодирование JWT токена."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != token_type:
            return None
        return payload
    except JWTError:
        return None


def authenticate_admin(db: Session, username: str, password: str) -> Optional[Admin]:
    """Аутентификация администратора по логину и паролю."""
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin:
        return None
    if not admin.is_active:
        return None
    if not verify_password(password, admin.password_hash):
        return None
    # Обновляем время последнего входа
    admin.last_login = datetime.utcnow()
    db.commit()
    return admin


def get_admin_by_username(db: Session, username: str) -> Optional[Admin]:
    """Получение администратора по имени пользователя."""
    return db.query(Admin).filter(Admin.username == username).first()


def get_admin_by_id(db: Session, admin_id: str) -> Optional[Admin]:
    """Получение администратора по ID."""
    return db.query(Admin).filter(Admin.id == admin_id).first()


def create_admin(
    db: Session,
    username: str,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    is_super_admin: bool = False,
) -> Admin:
    """Создание нового администратора."""
    admin = Admin(
        username=username,
        email=email,
        password_hash=get_password_hash(password),
        full_name=full_name,
        is_super_admin=is_super_admin,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
