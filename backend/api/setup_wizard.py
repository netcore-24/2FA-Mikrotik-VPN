"""
API endpoints для мастера настройки (Setup Wizard).
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional
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
    except Exception as e:
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
        
        # Проверяем, что все обязательные шаги выполнены
        status_data = get_setup_wizard_status(db)
        if not status_data["is_completed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not all required steps are completed",
            )
        
        return {"message": t("setup_wizard.completed"), "status": status_data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e) or t("error.internal"),
        )


@router.post("/test/telegram", response_model=SetupWizardTestResponse)
async def test_telegram_connection_endpoint(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Протестировать подключение к Telegram API с токеном.
    """
    success, error_message = test_telegram_connection(token)
    
    if success:
        return SetupWizardTestResponse(
            success=True,
            message=t("mikrotik.config.test_success"),  # TODO: добавить отдельный перевод
        )
    else:
        return SetupWizardTestResponse(
            success=False,
            message=error_message or t("mikrotik.config.test_failed"),
        )


@router.post("/test/mikrotik", response_model=SetupWizardTestResponse)
async def test_mikrotik_connection_endpoint(
    config_id: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Протестировать подключение к MikroTik.
    Если config_id не указан, использует активную конфигурацию.
    """
    if not config_id:
        active_config = get_active_mikrotik_config(db)
        if not active_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t("mikrotik.config.not_found"),
            )
        config_id = active_config.id
    
    success, error_message = test_mikrotik_config_connection(db, config_id)
    
    if success:
        return SetupWizardTestResponse(
            success=True,
            message=t("mikrotik.config.test_success"),
        )
    else:
        return SetupWizardTestResponse(
            success=False,
            message=error_message or t("mikrotik.config.test_failed"),
        )
