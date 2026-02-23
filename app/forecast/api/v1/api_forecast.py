# 산불 예측 관련 API 엔드포인트 정의 (요청 처리 및 응답 반환)
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlmodel import Session
from typing import Annotated

from app.asos.services.asos_feature_service import (
    get_asos_common_feature_cache_summary,
    refresh_asos_common_features_if_needed,
)
from app.forecast.schemas.forecast_response import ForecastResponse
from app.forecast.services.ai_model_service import AIModelService
from app.forecast.services.forecast_feature_service import fetch_common_forecast_features
from app.forecast.services.forecast_service import ForecastService
from app.globals.config.db_config import get_session

router = APIRouter()


def _build_debug_weather_payload(
    *, force_refresh: bool, max_asos_records_per_station: int
) -> dict[str, object]:
    """디버깅용: 예특보/종관 공통 Feature 파싱 결과를 JSON 직렬화 구조로 생성한다."""
    asos_features_by_station = refresh_asos_common_features_if_needed(
        force_refresh=force_refresh,
    )
    feature_map = fetch_common_forecast_features()

    if max_asos_records_per_station > 0:
        asos_records = {
            stn: [
                feature.model_dump(mode="json")
                for feature in features[:max_asos_records_per_station]
            ]
            for stn, features in asos_features_by_station.items()
        }
    else:
        asos_records = {
            stn: [feature.model_dump(mode="json") for feature in features]
            for stn, features in asos_features_by_station.items()
        }

    # 디버깅용: 전체/샘플 구조를 함께 담아 디버그 시 확인하기 쉽게 함
    asos_summary = get_asos_common_feature_cache_summary(
        sample_station_limit=0,
        sample_per_station_limit=0,
    )

    return {
        "generated_at": datetime.now().isoformat(),
        "asos": {
            "requested": {
                "force_refresh": force_refresh,
                "max_asos_records_per_station": max_asos_records_per_station,
                "station_count": len(asos_records),
            },
            "records": asos_records,
            "summary": asos_summary,
        },
        "forecast": {
            "requested": {
                "region_count": len(feature_map),
            },
            "samples": {
                reg_id: feature.model_dump(mode="json")
                for reg_id, feature in feature_map.items()
            },
        },
    }

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


@router.get("/weather/asos/test")
async def test_asos_collection(force_refresh: bool = True) -> dict[str, object]:
    """
    종관(ASOS) 30일 수집/파싱 테스트용 임시 API

    Args:
        force_refresh: True면 즉시 재수집, False면 30일 주기 캐시 사용
    """
    refresh_asos_common_features_if_needed(force_refresh=force_refresh)
    return get_asos_common_feature_cache_summary()


def _dump_debug_weather_to_json(payload: dict[str, object]) -> str:
    """디버깅용: 파싱된 Feature를 디렉토리에 JSON 파일로 저장한다."""
    base_dir = Path("debug") / "weather"
    base_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = base_dir / f"parsed_features_{ts}.json"
    file_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return str(file_path)


@router.get("/weather/debug-json")
async def debug_weather_json(
    force_refresh: bool = True,
    max_asos_records_per_station: int = 0,
) -> dict[str, object]:
    """
    디버깅용: 예특보/종관 파싱 결과를 JSON 파일로 생성하고 저장 경로를 반환한다.

    Args:
        force_refresh: True면 종관 캐시를 즉시 갱신하고 파싱 결과를 저장
        max_asos_records_per_station: 0이면 전체 저장, 1 이상이면 해당 수만큼만 샘플링
    """
    payload = _build_debug_weather_payload(
        force_refresh=force_refresh,
        max_asos_records_per_station=max_asos_records_per_station,
    )

    file_path = _dump_debug_weather_to_json(payload)

    return {
        "status": "ok",
        "output_path": file_path,
        "payload": payload,
    }
