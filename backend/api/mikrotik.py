"""
API endpoints для работы с MikroTik роутером.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from backend.database import get_db
from backend.api.dependencies import get_current_admin, get_current_super_admin
from backend.api.i18n_dependencies import get_translate
from backend.api.schemas import (
    MikroTikConfigCreate,
    MikroTikConfigUpdate,
    MikroTikConfigResponse,
    MikroTikConfigListResponse,
    MikroTikConfigTestResponse,
    MikroTikUserListResponse,
    MikroTikUserResponse,
    MikroTikUserCreate,
    MikroTikFirewallRuleListResponse,
    MikroTikFirewallRuleResponse,
    MikroTikFirewallRuleBinding,
    MikroTikFirewallRuleAssignRequest,
    MikroTikSessionListResponse,
    MikroTikSessionResponse,
)
from backend.services.mikrotik_config_service import (
    get_mikrotik_config_by_id,
    get_all_mikrotik_configs,
    create_mikrotik_config,
    update_mikrotik_config,
    delete_mikrotik_config,
    test_mikrotik_config_connection,
)
from backend.services.mikrotik_service import (
    MikroTikConnectionError,
    get_mikrotik_users,
    get_mikrotik_users_with_info,
    create_mikrotik_user,
    delete_mikrotik_user,
    get_firewall_rules,
    enable_firewall_rule,
    disable_firewall_rule,
    find_firewall_rule_by_comment,
    get_user_manager_users,
    get_user_manager_sessions,
    enable_user_manager_user,
    disable_user_manager_user,
    terminate_active_sessions_for_username,
)
from backend.services.user_service import update_user_settings, get_user_settings
from backend.models.user_setting import UserSetting
from backend.models.user import User
from backend.models.mikrotik_config import ConnectionType
from backend.models.admin import Admin

router = APIRouter(prefix="/mikrotik", tags=["mikrotik"])


# ========== Конфигурации MikroTik ==========

@router.get("/configs", response_model=MikroTikConfigListResponse)
async def list_mikrotik_configs(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить список всех конфигураций MikroTik.
    """
    configs = get_all_mikrotik_configs(db)
    
    items = []
    for config in configs:
        items.append(MikroTikConfigResponse(
            id=config.id,
            name=config.name,
            host=config.host,
            port=config.port,
            username=config.username,
            ssh_key_path=config.ssh_key_path,
            connection_type=config.connection_type.value,
            is_active=config.is_active,
            last_connection_test=config.last_connection_test,
            created_at=config.created_at,
            updated_at=config.updated_at,
        ))
    
    return MikroTikConfigListResponse(
        items=items,
        total=len(items),
    )


@router.get("/configs/{config_id}", response_model=MikroTikConfigResponse)
async def get_mikrotik_config(
    config_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить конфигурацию MikroTik по ID (без пароля).
    """
    config = get_mikrotik_config_by_id(db, config_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("mikrotik.config.not_found"),
        )
    
    return MikroTikConfigResponse(
        id=config.id,
        name=config.name,
        host=config.host,
        port=config.port,
        username=config.username,
        ssh_key_path=config.ssh_key_path,
        connection_type=config.connection_type.value,
        is_active=config.is_active,
        last_connection_test=config.last_connection_test,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.post("/configs", response_model=MikroTikConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_mikrotik_config_endpoint(
    config_data: MikroTikConfigCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Создать новую конфигурацию MikroTik. Требуются права супер-администратора.
    """
    try:
        connection_type_enum = ConnectionType(config_data.connection_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("validation.invalid_format"),
        )
    
    config = create_mikrotik_config(
        db=db,
        name=config_data.name,
        host=config_data.host,
        port=config_data.port,
        username=config_data.username,
        password=config_data.password,
        ssh_key_path=config_data.ssh_key_path,
        connection_type=connection_type_enum,
        is_active=config_data.is_active,
    )
    
    return MikroTikConfigResponse(
        id=config.id,
        name=config.name,
        host=config.host,
        port=config.port,
        username=config.username,
        ssh_key_path=config.ssh_key_path,
        connection_type=config.connection_type.value,
        is_active=config.is_active,
        last_connection_test=config.last_connection_test,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.put("/configs/{config_id}", response_model=MikroTikConfigResponse)
async def update_mikrotik_config_endpoint(
    config_id: str,
    config_update: MikroTikConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Обновить конфигурацию MikroTik. Требуются права супер-администратора.
    """
    config = get_mikrotik_config_by_id(db, config_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("mikrotik.config.not_found"),
        )
    
    connection_type_enum = None
    if config_update.connection_type:
        try:
            connection_type_enum = ConnectionType(config_update.connection_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=t("validation.invalid_format"),
            )
    
    updated_config = update_mikrotik_config(
        db=db,
        config_id=config_id,
        name=config_update.name,
        host=config_update.host,
        port=config_update.port,
        username=config_update.username,
        password=config_update.password,
        ssh_key_path=config_update.ssh_key_path,
        connection_type=connection_type_enum,
        is_active=config_update.is_active,
    )
    
    if not updated_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("mikrotik.config.not_found"),
        )
    
    return MikroTikConfigResponse(
        id=updated_config.id,
        name=updated_config.name,
        host=updated_config.host,
        port=updated_config.port,
        username=updated_config.username,
        ssh_key_path=updated_config.ssh_key_path,
        connection_type=updated_config.connection_type.value,
        is_active=updated_config.is_active,
        last_connection_test=updated_config.last_connection_test,
        created_at=updated_config.created_at,
        updated_at=updated_config.updated_at,
    )


@router.delete("/configs/{config_id}")
async def delete_mikrotik_config_endpoint(
    config_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Удалить конфигурацию MikroTik. Требуются права супер-администратора.
    """
    config = get_mikrotik_config_by_id(db, config_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("mikrotik.config.not_found"),
        )
    
    success = delete_mikrotik_config(db, config_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("mikrotik.config.not_found"),
        )
    
    return {"message": t("mikrotik.config.deleted")}


@router.post("/configs/{config_id}/test", response_model=MikroTikConfigTestResponse)
async def test_mikrotik_config_endpoint(
    config_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Протестировать подключение к MikroTik для указанной конфигурации.
    """
    success, error_message = test_mikrotik_config_connection(db, config_id)
    
    if success:
        return MikroTikConfigTestResponse(
            success=True,
            message=t("mikrotik.config.test_success"),
        )
    else:
        return MikroTikConfigTestResponse(
            success=False,
            message=error_message or t("mikrotik.config.test_failed"),
        )


# ========== Пользователи MikroTik ==========

@router.get("/users", response_model=MikroTikUserListResponse)
async def list_mikrotik_users(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить список пользователей из MikroTik User Manager.
    """
    try:
        users, source, warning = get_mikrotik_users_with_info(db)
        
        user_responses = []
        for user in users:
            name = user.get("name") or user.get("username") or user.get("user") or ""
            # RouterOS User Manager часто использует ключ actual-profile вместо profile
            profile = (
                user.get("profile")
                or user.get("actual-profile")
                or user.get("actual_profile")
                or user.get("group")
            )
            user_responses.append(MikroTikUserResponse(
                name=name,
                profile=profile,
                disabled=user.get("disabled"),
                number=user.get("number"),
                data=user,
            ))
        
        return MikroTikUserListResponse(users=user_responses, source=source, warning=warning)
    except MikroTikConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e) or t("mikrotik.connection.failed"),
        )


@router.post("/users", response_model=dict)
async def create_mikrotik_user_endpoint(
    user_data: MikroTikUserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Создать пользователя в MikroTik User Manager.
    """
    try:
        result = create_mikrotik_user(
            db=db,
            username=user_data.username,
            password=user_data.password,
            profile=user_data.profile,
        )
        return {"message": t("mikrotik.user.created"), "data": result}
    except MikroTikConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e) or t("mikrotik.connection.failed"),
        )


@router.delete("/users/{username}")
async def delete_mikrotik_user_endpoint(
    username: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Удалить пользователя из MikroTik User Manager.
    """
    try:
        delete_mikrotik_user(db, username)
        return {"message": t("mikrotik.user.deleted")}
    except MikroTikConnectionError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t("mikrotik.user.not_found"),
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_msg or t("mikrotik.connection.failed"),
        )


# ========== Firewall правила ==========

@router.get("/firewall-rules", response_model=MikroTikFirewallRuleListResponse)
async def list_firewall_rules(
    request: Request,
    chain: Optional[str] = Query(None),
    comment: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить список правил firewall из MikroTik.
    """
    try:
        rules = get_firewall_rules(db, chain=chain, comment=comment)
        
        rule_responses = []
        for rule in rules:
            rule_responses.append(MikroTikFirewallRuleResponse(
                id=rule.get(".id") or rule.get("id"),
                number=rule.get("number"),
                chain=rule.get("chain"),
                action=rule.get("action"),
                comment=rule.get("comment"),
                disabled=rule.get("disabled"),
                data=rule,
            ))
        
        return MikroTikFirewallRuleListResponse(rules=rule_responses)
    except MikroTikConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e) or t("mikrotik.connection.failed"),
        )


@router.get("/firewall-rules/bindings", response_model=list[MikroTikFirewallRuleBinding])
async def list_firewall_rule_bindings(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """
    Получить привязки firewall-правил (по comment) к пользователям.
    Используется UI для отображения "какое правило за кем закреплено".
    """
    rows = (
        db.query(UserSetting, User)
        .join(User, User.id == UserSetting.user_id)
        .filter(UserSetting.firewall_rule_comment.isnot(None))
        .all()
    )
    result: list[MikroTikFirewallRuleBinding] = []
    for us, u in rows:
        comment = (us.firewall_rule_comment or "").strip()
        if not comment:
            continue
        result.append(
            MikroTikFirewallRuleBinding(
                user_id=u.id,
                telegram_id=u.telegram_id,
                full_name=u.full_name,
                firewall_rule_comment=comment,
            )
        )
    return result


@router.post("/firewall-rules/{rule_id}/assign", response_model=dict)
async def assign_firewall_rule_to_user(
    rule_id: str,
    body: MikroTikFirewallRuleAssignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Привязать firewall-правило (по MikroTik .id) к пользователю системы.

    Храним привязку в `user_settings.firewall_rule_comment`:
    - это позволяет включать правило при подтверждении VPN-подключения
    - и не требует миграции схемы БД
    """
    try:
        # Находим правило по .id (если есть) или по номеру (numbers=NN для SSH),
        # среди правил, отфильтрованных по RouterOS.
        rules = get_firewall_rules(db)
        found = None
        for r in rules:
            rid = r.get(".id") or r.get("id")
            if rid == rule_id:
                found = r
                break
            # fallback: match by number
            if r.get("number") is not None and str(r.get("number")) == str(rule_id):
                found = r
                break
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t("mikrotik.firewall.rule_not_found"))

        comment = (found.get("comment") or "").strip()
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя привязать правило без comment (добавьте comment с '2FA ...' на MikroTik).",
            )

        # Если user_id не задан — снимаем привязку со всех пользователей у которых этот comment
        if not body.user_id:
            updated = (
                db.query(UserSetting)
                .filter(UserSetting.firewall_rule_comment == comment)
                .update({UserSetting.firewall_rule_comment: None})
            )
            db.commit()
            return {"message": "Привязка снята", "updated": int(updated)}

        # 1) Снимаем этот comment с других пользователей (одно правило — один пользователь)
        db.query(UserSetting).filter(
            UserSetting.user_id != body.user_id,
            UserSetting.firewall_rule_comment == comment,
        ).update({UserSetting.firewall_rule_comment: None})
        db.commit()

        # 2) Обновляем настройки целевого пользователя (создадутся если нет)
        update_user_settings(db, body.user_id, firewall_rule_comment=comment)

        return {"message": "Правило привязано", "user_id": body.user_id, "comment": comment, "rule_id": rule_id}
    except MikroTikConnectionError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e) or t("mikrotik.connection.failed"))


@router.post("/firewall-rules/{rule_id}/enable")
async def enable_firewall_rule_endpoint(
    rule_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Включить правило firewall в MikroTik.
    """
    try:
        enable_firewall_rule(db, rule_id)
        return {"message": t("mikrotik.firewall.rule_enabled")}
    except MikroTikConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e) or t("mikrotik.connection.failed"),
        )


@router.post("/firewall-rules/{rule_id}/disable")
async def disable_firewall_rule_endpoint(
    rule_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Выключить правило firewall в MikroTik.
    """
    try:
        disable_firewall_rule(db, rule_id)
        return {"message": t("mikrotik.firewall.rule_disabled")}
    except MikroTikConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e) or t("mikrotik.connection.failed"),
        )


@router.get("/firewall-rules/by-comment/{comment}")
async def find_firewall_rule_by_comment_endpoint(
    comment: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Найти правило firewall по комментарию.
    """
    try:
        rule = find_firewall_rule_by_comment(db, comment)
        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t("mikrotik.firewall.rule_not_found"),
            )
        
        return MikroTikFirewallRuleResponse(
            id=rule.get(".id") or rule.get("id"),
            chain=rule.get("chain"),
            action=rule.get("action"),
            comment=rule.get("comment"),
            disabled=rule.get("disabled"),
            data=rule,
        )
    except MikroTikConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e) or t("mikrotik.connection.failed"),
        )


# ========== User Manager ==========

@router.get("/user-manager/users")
async def get_user_manager_users_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить список пользователей из MikroTik User Manager.
    """
    try:
        result = get_user_manager_users(db)
        return result
    except MikroTikConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e) or t("mikrotik.connection.failed"),
        )


# ========== Сессии / операции над пользователями ==========

@router.get("/sessions", response_model=MikroTikSessionListResponse)
async def list_mikrotik_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить подключения с MikroTik (User Manager sessions + PPP active).
    Полезно для отладки: "видит ли система факт подключения".
    """
    try:
        sessions = get_user_manager_sessions(db) or []
        items: list[MikroTikSessionResponse] = []
        for s in sessions:
            if not isinstance(s, dict):
                continue
            items.append(
                MikroTikSessionResponse(
                    mikrotik_session_id=(
                        s.get("mikrotik_session_id")
                        or s.get("acct-session-id")
                        or s.get("session-id")
                        or s.get(".id")
                        or s.get("id")
                    ),
                    user=s.get("user") or s.get("name") or s.get("username"),
                    active=s.get("active"),
                    source=s.get("source"),
                    number=s.get("number"),
                    data=s,
                )
            )
        return MikroTikSessionListResponse(sessions=items, total=len(items))
    except MikroTikConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e) or t("mikrotik.connection.failed"),
        )


@router.post("/users/{username}/enable", response_model=dict)
async def enable_mikrotik_user_endpoint(
    username: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """Включить пользователя на MikroTik (disabled=no)."""
    try:
        enable_user_manager_user(db, username)
        return {"message": "OK", "username": username, "disabled": False}
    except MikroTikConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e) or t("mikrotik.connection.failed"),
        )


@router.post("/users/{username}/disable", response_model=dict)
async def disable_mikrotik_user_endpoint(
    username: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """Отключить пользователя на MikroTik (disabled=yes)."""
    try:
        disable_user_manager_user(db, username)
        return {"message": "OK", "username": username, "disabled": True}
    except MikroTikConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e) or t("mikrotik.connection.failed"),
        )


@router.post("/users/{username}/disconnect", response_model=dict)
async def disconnect_mikrotik_user_sessions_endpoint(
    username: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Best-effort: принудительно завершить активные сессии пользователя на MikroTik.
    Не меняет disabled-флаг пользователя.
    """
    try:
        terminate_active_sessions_for_username(db, username)
        return {"message": "OK", "username": username}
    except MikroTikConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e) or t("mikrotik.connection.failed"),
        )
