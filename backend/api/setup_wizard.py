"""
API endpoints для мастера настройки (Setup Wizard).
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, Body
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from backend.database import get_db
from backend.api.dependencies import get_current_admin, get_current_super_admin
from backend.api.i18n_dependencies import get_translate
from backend.api.schemas import (
    SetupWizardStatusResponse,
    SetupWizardStepResponse,
    SetupWizardStepsResponse,
    SetupWizardStepData,
    SetupWizardStepCompleteResponse,
    SetupWizardTestResponse,
)
from backend.services.setup_wizard_service import (
    get_setup_wizard_status,
    get_setup_wizard_steps,
    get_setup_wizard_step,
    complete_setup_wizard_step,
    restart_setup_wizard,
    test_telegram_connection,
)
from backend.services.mikrotik_config_service import test_mikrotik_config_connection
from backend.services.mikrotik_config_service import get_active_mikrotik_config
from backend.models.admin import Admin

router = APIRouter(prefix="/setup-wizard", tags=["setup-wizard"])


@router.get("/status", response_model=SetupWizardStatusResponse)
async def get_setup_wizard_status_endpoint(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Получить статус мастера настройки.
    Можно вызывать без аутентификации для проверки статуса настройки.
    """
    status_data = get_setup_wizard_status(db)
    return SetupWizardStatusResponse(**status_data)


@router.get("/steps", response_model=SetupWizardStepsResponse)
async def get_setup_wizard_steps_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить список всех шагов мастера настройки.
    """
    steps = get_setup_wizard_steps()
    step_responses = [SetupWizardStepResponse(**step) for step in steps]
    return SetupWizardStepsResponse(steps=step_responses)


@router.get("/step/{step_id}", response_model=SetupWizardStepResponse)
async def get_setup_wizard_step_endpoint(
    step_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить информацию о конкретном шаге мастера настройки.
    """
    step = get_setup_wizard_step(step_id)
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("error.not_found"),
        )
    return SetupWizardStepResponse(**step)


@router.post("/step/{step_id}/complete", response_model=SetupWizardStepCompleteResponse)
async def complete_setup_wizard_step_endpoint(
    step_id: str,
    step_data: SetupWizardStepData,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Завершить шаг мастера настройки и сохранить данные.
    Требуются права супер-администратора.
    """
    # Преобразуем Pydantic модель в словарь
    data_dict = step_data.model_dump(exclude_unset=True, exclude_none=True)
    
    try:
        result = complete_setup_wizard_step(db, step_id, data_dict)
        return SetupWizardStepCompleteResponse(**result)
    except ValueError as e:
        # Ошибки валидации (например, не удалось создать/обновить администратора)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e) or t("error.validation_failed"),
        )
    except Exception as e:
        # Общие ошибки
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e) or t("error.internal"),
        )


@router.post("/restart")
async def restart_setup_wizard_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Перезапустить мастер настройки (сбросить все шаги).
    Требуются права супер-администратора.
    """
    restart_setup_wizard(db)
    return {"message": t("setup_wizard.welcome")}


@router.post("/complete")
async def complete_setup_wizard_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Завершить мастер настройки (финальный шаг).
    Требуются права супер-администратора.
    """
    try:
        result = complete_setup_wizard_step(db, "review", {})
        
        # Проверяем результат завершения шага review
        if not result.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "Not all required steps are completed"),
            )
        
        # Получаем обновленный статус
        status_data = get_setup_wizard_status(db)
        
        return {"message": t("setup_wizard.completed") or "Setup wizard completed successfully", "status": status_data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e) or t("error.internal"),
        )


@router.post("/test/telegram", response_model=SetupWizardTestResponse)
async def test_telegram_connection_endpoint(
    request: Request,
    token: Optional[str] = Query(None, description="Telegram bot token to test"),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Протестировать подключение к Telegram API с токеном.
    Если токен не указан в query параметре, использует сохраненный токен из настроек.
    Также можно передать токен в теле запроса как JSON: {"token": "..."}
    """
    # Проверяем, есть ли токен в query параметре
    if not token:
        # Пробуем получить из body запроса
        try:
            body = await request.json()
            token = body.get("token")
        except:
            pass
    
    # Если токен все еще не найден, получаем из настроек БД
    if not token:
        from backend.services.settings_service import get_setting_value
        token = get_setting_value(db, "telegram_bot_token")
        if not token:
            return SetupWizardTestResponse(
                success=False,
                message=t("setup_wizard.telegram.token_not_set") or "Telegram bot token not configured. Please provide token.",
            )
    
    if not token or not token.strip():
        return SetupWizardTestResponse(
            success=False,
            message=t("validation.required") or "Token is required",
        )
    
    success, error_message = test_telegram_connection(token.strip())
    
    if success:
        return SetupWizardTestResponse(
            success=True,
            message=t("setup_wizard.test.telegram_success") or "Telegram bot connection successful",
        )
    else:
        return SetupWizardTestResponse(
            success=False,
            message=error_message or (t("setup_wizard.test.telegram_failed") or "Telegram bot connection failed"),
        )


@router.post("/test/mikrotik", response_model=SetupWizardTestResponse)
async def test_mikrotik_connection_endpoint(
    request: Request,
    config_id: Optional[str] = Query(None),
    test_params: Optional[Dict[str, Any]] = Body(None),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Протестировать подключение к MikroTik.
    Может принимать параметры подключения из тела запроса для тестирования перед сохранением.
    Если параметры не переданы, использует сохраненную конфигурацию.
    """
    # Пробуем получить параметры подключения из тела запроса (для тестирования перед сохранением)
    body = test_params
    if not body:
        try:
            body = await request.json()
        except:
            body = None
    
    # Если в body есть параметры подключения, тестируем с ними
    if body and ("host" in body or "mikrotik_host" in body):
        # Тестируем с временными параметрами из формы мастера настройки
        host = body.get("host") or body.get("mikrotik_host")
        port = body.get("port") or body.get("mikrotik_port", 22)
        username = body.get("username") or body.get("mikrotik_username")
        password = body.get("password") or body.get("mikrotik_password") or ""
        connection_type = body.get("connection_type", "ssh_password")
        
        if not host or not username:
            return SetupWizardTestResponse(
                success=False,
                message="Необходимо указать хост и имя пользователя",
            )
        
        # Тестируем подключение напрямую
        try:
            # Нормализуем тип подключения
            if connection_type in ["api", "rest_api"]:
                import requests
                from requests.auth import HTTPDigestAuth
                from requests.packages.urllib3.exceptions import InsecureRequestWarning
                import urllib3
                urllib3.disable_warnings(InsecureRequestWarning)
                
                url = f"http://{host}:{port}/rest/system/identity"
                response = requests.get(
                    url, 
                    auth=HTTPDigestAuth(username, password), 
                    timeout=10, 
                    verify=False
                )
                success = response.status_code == 200
                error_message = None if success else f"HTTP {response.status_code}: {response.text[:200]}"
            else:
                # SSH подключение
                import paramiko
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                try:
                    ssh.connect(
                        hostname=host, 
                        port=int(port), 
                        username=username, 
                        password=password, 
                        timeout=10,
                        look_for_keys=False,
                        allow_agent=False
                    )
                    ssh.close()
                    success = True
                    error_message = None
                except paramiko.AuthenticationException:
                    success = False
                    error_message = "Ошибка аутентификации. Проверьте имя пользователя и пароль."
                except paramiko.SSHException as e:
                    success = False
                    error_message = f"Ошибка SSH подключения: {str(e)}"
                except Exception as e:
                    success = False
                    error_message = f"Ошибка подключения: {str(e)}"
            
            if success:
                return SetupWizardTestResponse(
                    success=True,
                    message=t("mikrotik.config.test_success") or "Подключение к MikroTik успешно!",
                )
            else:
                return SetupWizardTestResponse(
                    success=False,
                    message=error_message or t("mikrotik.config.test_failed") or "Не удалось подключиться к MikroTik",
                )
        except Exception as e:
            return SetupWizardTestResponse(
                success=False,
                message=f"Ошибка подключения: {str(e)}",
            )
    
    # Стандартная логика - тестирование сохраненной конфигурации
    if not config_id:
        active_config = get_active_mikrotik_config(db)
        if not active_config:
            return SetupWizardTestResponse(
                success=False,
                message="Конфигурация MikroTik не найдена. Сохраните настройки сначала.",
            )
        config_id = active_config.id
    
    success, error_message = test_mikrotik_config_connection(db, config_id)
    
    if success:
        return SetupWizardTestResponse(
            success=True,
            message=t("mikrotik.config.test_success") or "Подключение к MikroTik успешно!",
        )
    else:
        return SetupWizardTestResponse(
            success=False,
            message=error_message or t("mikrotik.config.test_failed") or "Не удалось подключиться к MikroTik",
        )
