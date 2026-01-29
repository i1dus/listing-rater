from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MatchConfig
from app.schemas.match_config import MatchConfigResponse, MatchConfigCreate, MatchConfigUpdate

router = APIRouter(prefix="/api/admin/match-config", tags=["admin"])


@router.get("", response_model=MatchConfigResponse)
def get_match_config(db: Session = Depends(get_db)):
    """Получить активную конфигурацию метчинга"""
    config = db.query(MatchConfig).filter(MatchConfig.is_active == True).first()
    
    if not config:
        from app.config import get_settings
        settings = get_settings()
        
        config = MatchConfig(
            is_active=True,
            weights=settings.property_match_weights,
            strict_attributes=settings.property_match_strict_attributes,
            threshold=str(settings.property_match_threshold)
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    
    return config


@router.get("/all", response_model=List[MatchConfigResponse])
def get_all_match_configs(db: Session = Depends(get_db)):
    """Получить все конфигурации метчинга"""
    configs = db.query(MatchConfig).order_by(MatchConfig.created_at.desc()).all()
    return configs


@router.post("", response_model=MatchConfigResponse)
def create_match_config(config_data: MatchConfigCreate, db: Session = Depends(get_db)):
    """Создать новую конфигурацию метчинга"""
    if config_data.is_active:
        db.query(MatchConfig).filter(MatchConfig.is_active == True).update({"is_active": False})
    
    config = MatchConfig(
        is_active=config_data.is_active,
        weights=config_data.weights,
        strict_attributes=config_data.strict_attributes,
        threshold=str(config_data.threshold)
    )
    
    db.add(config)
    db.commit()
    db.refresh(config)
    
    return config


@router.put("/{config_id}", response_model=MatchConfigResponse)
def update_match_config(
    config_id: int,
    config_update: MatchConfigUpdate,
    db: Session = Depends(get_db)
):
    """Обновить конфигурацию метчинга"""
    config = db.query(MatchConfig).filter(MatchConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Конфигурация не найдена")
    
    update_data = config_update.model_dump(exclude_unset=True)
    
    if update_data.get('is_active') is True:
        db.query(MatchConfig).filter(
            MatchConfig.is_active == True,
            MatchConfig.id != config_id
        ).update({"is_active": False})
    
    for key, value in update_data.items():
        if key == 'threshold' and value is not None:
            setattr(config, key, str(value))
        else:
            setattr(config, key, value)
    
    db.commit()
    db.refresh(config)
    
    return config


@router.delete("/{config_id}")
def delete_match_config(config_id: int, db: Session = Depends(get_db)):
    """Удалить конфигурацию метчинга"""
    config = db.query(MatchConfig).filter(MatchConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Конфигурация не найдена")
    
    if config.is_active:
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить активную конфигурацию. Сначала деактивируйте её или активируйте другую."
        )
    
    db.delete(config)
    db.commit()
    
    return {"message": "Конфигурация удалена", "id": config_id}
