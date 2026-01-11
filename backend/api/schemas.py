"""
Pydantic схемы для валидации данных API.
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, Any, Dict
from datetime import datetime


# Схемы для аутентификации
class Token(BaseModel):
    """Схема токена доступа."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    admin: Optional["AdminResponse"] = None


class TokenData(BaseModel):
    """Данные из токена."""
    username: Optional[str] = None
    admin_id: Optional[str] = None


class LoginRequest(BaseModel):
    """Схема запроса на вход."""
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    """Схема запроса на обновление токена."""
    refresh_token: str


# Схемы для администраторов
class AdminBase(BaseModel):
    """Базовая схема администратора."""
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    is_super_admin: bool = False


class AdminCreate(AdminBase):
    """Схема создания администратора."""
    password: str


class AdminResponse(AdminBase):
    """Схема ответа с данными администратора."""
    id: str
    created_at: datetime
    last_login: Optional[datetime] = None
    
    model_config = {"from_attributes": True}


# Схемы для пользователей
class UserBase(BaseModel):
    """Базовая схема пользователя."""
    telegram_id: int
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class UserCreate(UserBase):
    """Схема создания пользователя."""
    pass


class UserUpdate(BaseModel):
    """Схема обновления пользователя."""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[str] = None
    mikrotik_usernames: Optional[list[str]] = None


class UserResponse(BaseModel):
    """Схема ответа с данными пользователя."""
    id: str
    telegram_id: int
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    status: str
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None
    rejected_reason: Optional[str] = None
    mikrotik_usernames: list[str] = []
    # Настройки (для отображения в списках)
    require_confirmation: Optional[bool] = None
    firewall_rule_comment: Optional[str] = None
    
    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Схема ответа со списком пользователей."""
    items: list[UserResponse]
    total: int
    skip: int
    limit: int


# Схемы для запросов на регистрацию
class RegistrationRequestCreate(BaseModel):
    """Схема создания запроса на регистрацию."""
    telegram_id: int
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class RegistrationRequestResponse(BaseModel):
    """Схема ответа с данными запроса на регистрацию."""
    id: str
    user_id: str
    status: str
    requested_at: datetime
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    user: Optional[UserResponse] = None


class RegistrationRequestApprove(BaseModel):
    """Схема одобрения запроса на регистрацию."""
    pass


class RegistrationRequestReject(BaseModel):
    """Схема отклонения запроса на регистрацию."""
    rejection_reason: str


class RegistrationRequestListResponse(BaseModel):
    """Схема ответа со списком запросов на регистрацию."""
    items: list[RegistrationRequestResponse]
    total: int
    skip: int
    limit: int


# Схемы для интернационализации
class TranslationsResponse(BaseModel):
    """Схема ответа с переводами."""
    language: str
    translations: dict


class TranslateResponse(BaseModel):
    """Схема ответа с переводом конкретного ключа."""
    key: str
    translation: str
    language: str


class LanguagesResponse(BaseModel):
    """Схема ответа со списком поддерживаемых языков."""
    supported_languages: list[str]
    default_language: str


# Схемы для VPN сессий
class VPNSessionCreate(BaseModel):
    """Схема создания VPN сессии."""
    user_id: str
    mikrotik_username: str


class VPNSessionResponse(BaseModel):
    """Схема ответа с данными VPN сессии."""
    id: str
    user_id: str
    mikrotik_username: str
    mikrotik_session_id: Optional[str] = None
    mikrotik_last_seen_at: Optional[datetime] = None
    status: str
    connected_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    reminder_sent_at: Optional[datetime] = None
    firewall_rule_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    user: Optional[UserResponse] = None


class VPNSessionListResponse(BaseModel):
    """Схема ответа со списком VPN сессий."""
    items: list[VPNSessionResponse]
    total: int
    skip: int
    limit: int


class VPNSessionDisconnect(BaseModel):
    """Схема отключения VPN сессии."""
    pass


class VPNSessionExtend(BaseModel):
    """Схема продления VPN сессии."""
    hours: Optional[int] = None


# Схемы для настроек
class SettingBase(BaseModel):
    """Базовая схема настройки."""
    key: str
    value: Any
    category: str = "general"
    description: Optional[str] = None
    is_encrypted: bool = False


class SettingCreate(SettingBase):
    """Схема создания настройки."""
    pass


class SettingUpdate(BaseModel):
    """Схема обновления настройки."""
    value: Any
    category: Optional[str] = None
    description: Optional[str] = None
    is_encrypted: Optional[bool] = None


class SettingResponse(BaseModel):
    """Схема ответа с данными настройки."""
    id: str
    key: str
    value: Any
    category: str
    description: Optional[str] = None
    is_encrypted: bool
    created_at: datetime
    updated_at: datetime


class SettingListResponse(BaseModel):
    """Схема ответа со списком настроек."""
    items: list[SettingResponse]
    total: int
    categories: list[str]


class SettingsDictResponse(BaseModel):
    """Схема ответа с настройками в виде словаря."""
    settings: dict[str, Any]
    category: Optional[str] = None


# Схемы для MikroTik
class MikroTikConfigBase(BaseModel):
    """Базовая схема конфигурации MikroTik."""
    name: str
    host: str
    port: int = 22
    username: str
    password: Optional[str] = None
    ssh_key_path: Optional[str] = None
    connection_type: str = "ssh_password"
    is_active: bool = False


class MikroTikConfigCreate(MikroTikConfigBase):
    """Схема создания конфигурации MikroTik."""
    pass


class MikroTikConfigUpdate(BaseModel):
    """Схема обновления конфигурации MikroTik."""
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssh_key_path: Optional[str] = None
    connection_type: Optional[str] = None
    is_active: Optional[bool] = None


class MikroTikConfigResponse(BaseModel):
    """Схема ответа с данными конфигурации MikroTik (без пароля)."""
    id: str
    name: str
    host: str
    port: int
    username: str
    ssh_key_path: Optional[str] = None
    connection_type: str
    is_active: bool
    last_connection_test: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class MikroTikConfigListResponse(BaseModel):
    """Схема ответа со списком конфигураций MikroTik."""
    items: list[MikroTikConfigResponse]
    total: int


class MikroTikConfigTestResponse(BaseModel):
    """Схема ответа на тест подключения."""
    success: bool
    message: Optional[str] = None


class MikroTikUserResponse(BaseModel):
    """Схема ответа с пользователем MikroTik."""
    name: str
    profile: Optional[str] = None
    disabled: Optional[bool] = None
    number: Optional[int] = None
    data: Optional[dict[str, Any]] = None


class MikroTikUserListResponse(BaseModel):
    """Схема ответа со списком пользователей MikroTik."""
    users: list[MikroTikUserResponse]
    source: Optional[str] = None
    warning: Optional[str] = None


class MikroTikFirewallRuleResponse(BaseModel):
    """Схема ответа с правилом firewall MikroTik."""
    id: Optional[str] = None
    number: Optional[int] = None
    chain: Optional[str] = None
    action: Optional[str] = None
    comment: Optional[str] = None
    disabled: Optional[bool] = None
    data: Optional[dict[str, Any]] = None


class MikroTikFirewallRuleListResponse(BaseModel):
    """Схема ответа со списком правил firewall."""
    rules: list[MikroTikFirewallRuleResponse]


class MikroTikFirewallRuleBinding(BaseModel):
    """Связь firewall-правила (по comment) с пользователем системы."""
    user_id: str
    telegram_id: Optional[int] = None
    full_name: Optional[str] = None
    firewall_rule_comment: str


class MikroTikFirewallRuleAssignRequest(BaseModel):
    """Запрос на привязку firewall-правила к пользователю."""
    user_id: Optional[str] = None


class MikroTikUserCreate(BaseModel):
    """Схема создания пользователя MikroTik."""
    username: str
    password: str
    profile: Optional[str] = None


# Сессии MikroTik (User Manager / PPP active)
class MikroTikSessionResponse(BaseModel):
    """Нормализованная сессия MikroTik (UM session или PPP active)."""
    mikrotik_session_id: Optional[str] = None
    user: Optional[str] = None
    active: Optional[bool] = None
    source: Optional[str] = None  # user_manager_session | ppp_active | ...
    number: Optional[int] = None
    data: Optional[dict[str, Any]] = None


class MikroTikSessionListResponse(BaseModel):
    """Список сессий MikroTik."""
    sessions: list[MikroTikSessionResponse]
    total: int


# Схемы для аудита
class AuditLogResponse(BaseModel):
    """Схема ответа с записью журнала аудита."""
    id: str
    user_id: Optional[str] = None
    admin_id: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Схема ответа со списком записей аудита."""
    items: list[AuditLogResponse]
    total: int
    skip: int
    limit: int


# Схемы для статистики
class StatsOverviewResponse(BaseModel):
    """Схема ответа с общей статистикой."""
    total_users: int
    active_users: int
    pending_users: int
    total_sessions: int
    active_sessions: int
    total_registration_requests: int
    pending_registration_requests: int
    mikrotik_active_sessions: Optional[int] = None


class StatsUsersResponse(BaseModel):
    """Схема ответа со статистикой по пользователям."""
    total: int
    by_status: dict[str, int]
    approved: int
    rejected: int
    pending: int
    active: int
    inactive: int


class StatsSessionsResponse(BaseModel):
    """Схема ответа со статистикой по сессиям."""
    total: int
    by_status: dict[str, int]
    active: int
    connected: int
    confirmed: int
    disconnected: int
    expired: int


# Схемы для управления базой данных
class DatabaseInfoResponse(BaseModel):
    """Схема ответа с информацией о базе данных."""
    path: str
    exists: bool
    size: int
    size_human: str
    sqlite_version: Optional[str] = None
    tables: Optional[dict[str, int]] = None
    total_tables: Optional[int] = None
    last_modified: Optional[str] = None


class DatabaseIntegrityResponse(BaseModel):
    """Схема ответа на проверку целостности базы данных."""
    success: bool
    message: Optional[str] = None


class DatabaseBackupResponse(BaseModel):
    """Схема ответа на создание резервной копии."""
    success: bool
    backup_path: Optional[str] = None
    backup_filename: Optional[str] = None
    message: Optional[str] = None


class DatabaseRestoreResponse(BaseModel):
    """Схема ответа на восстановление базы данных."""
    success: bool
    message: Optional[str] = None


class DatabaseOptimizeResponse(BaseModel):
    """Схема ответа на оптимизацию базы данных."""
    success: bool
    size_before: Optional[int] = None
    size_after: Optional[int] = None
    size_saved: Optional[int] = None
    size_saved_human: Optional[str] = None
    error: Optional[str] = None


class BackupListResponse(BaseModel):
    """Схема ответа со списком резервных копий."""
    backups: list[dict[str, Any]]


# Схемы для мастера настройки
class SetupWizardStatusResponse(BaseModel):
    """Схема ответа со статусом мастера настройки."""
    is_completed: bool
    current_step: str
    completed_steps: list[str]
    total_steps: int
    can_restart: Optional[bool] = True  # Всегда можно перезапустить
    was_completed_before: Optional[bool] = False  # Был ли мастер завершен ранее


class SetupWizardStepResponse(BaseModel):
    """Схема ответа с информацией о шаге мастера настройки."""
    id: str
    name: str
    description: str
    required: bool


class SetupWizardStepsResponse(BaseModel):
    """Схема ответа со списком шагов мастера настройки."""
    steps: list[SetupWizardStepResponse]


class SetupWizardStepData(BaseModel):
    """Схема данных для завершения шага мастера настройки."""
    app_name: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    admin_email: Optional[str] = None
    secret_key: Optional[str] = None
    jwt_access_token_expire_minutes: Optional[int] = None
    jwt_refresh_token_expire_days: Optional[int] = None
    admin_username: Optional[str] = None
    admin_password: Optional[str] = None
    admin_full_name: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_bot_name: Optional[str] = None
    telegram_admin_chat_id: Optional[str] = None
    mikrotik_name: Optional[str] = None
    mikrotik_host: Optional[str] = None
    mikrotik_port: Optional[int] = None
    mikrotik_username: Optional[str] = None
    mikrotik_password: Optional[str] = None
    mikrotik_ssh_key_path: Optional[str] = None
    connection_type: Optional[str] = None
    notification_method: Optional[str] = None
    notification_email: Optional[str] = None
    telegram_other_token: Optional[str] = None
    telegram_other_chat_id: Optional[str] = None
    domain_name: Optional[str] = None
    backup_enabled: Optional[bool] = None
    backup_interval_hours: Optional[int] = None
    log_level: Optional[str] = None
    connection_type: Optional[str] = None
    mikrotik_user_prefix: Optional[str] = None
    mikrotik_firewall_comment_template: Optional[str] = None
    notification_types: Optional[list[str]] = None
    ui_theme: Optional[str] = None
    log_level: Optional[str] = None
    backup_enabled: Optional[bool] = None
    backup_interval_hours: Optional[int] = None


class SetupWizardStepCompleteResponse(BaseModel):
    """Схема ответа на завершение шага мастера настройки."""
    success: bool
    message: str


class SetupWizardTestResponse(BaseModel):
    """Схема ответа на тест подключения."""
    success: bool
    message: Optional[str] = None


# Схемы для сопоставления пользователей
class UserMappingBase(BaseModel):
    """Базовая схема сопоставления пользователя."""
    telegram_user_id: str
    mikrotik_username: str


class UserMappingCreate(UserMappingBase):
    """Схема создания сопоставления пользователя."""
    pass


class UserMappingResponse(UserMappingBase):
    """Схема ответа с данными сопоставления."""
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    telegram_user_full_name: Optional[str] = None
    telegram_user_email: Optional[str] = None
    telegram_user_phone: Optional[str] = None
    
    model_config = {"from_attributes": True}


class UserMappingListResponse(BaseModel):
    """Схема ответа со списком сопоставлений."""
    items: list[UserMappingResponse]
    total: int
    skip: int
    limit: int
