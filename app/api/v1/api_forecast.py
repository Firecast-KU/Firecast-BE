from fastapi import APIRouter, Depends
from sqlmodel import Session
from typing import Annotated

from app.db.db_config import get_session
from app.schemas.forecast_response import ForecastResponse
from app.services.forecast_ai_model import AIModelService
from app.services.forecast_service import ForecastService

router = APIRouter()

# Dependency 타입 어노테이션
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/forecast", response_model=list[ForecastResponse])
async def get_fire_forecast(session: SessionDep) -> list[ForecastResponse]:
    """
    산불 예측 데이터 조회

    - DB에 최신 데이터가 있으면 DB에서 가져옴
    - DB에 데이터가 없거나 오래되었으면 AI 모델로 예측 후 저장

    Returns:
        산불 예측 결과 리스트 (위도, 경도, 확률, 위험도 색상)
    """
    forecast_service = ForecastService()

    # DB에 최신 데이터가 있는지 확인
    if forecast_service.is_forecast_outdated(session):
        # AI 모델로 예측 수행
        ai_service = AIModelService()
        forecasts = ai_service.predict_fire_risk()

        # 새로운 예측 결과 저장
        forecast_service.save_forecasts(session, forecasts)

        return forecasts
    else:
        # DB에서 최신 데이터 조회
        return forecast_service.get_latest_forecasts(session)
