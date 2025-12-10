# API 응답에 사용되는 Pydantic 스키마 및 데이터 모델 정의
from pydantic import BaseModel, Field
from typing import Literal


class ForecastResponse(BaseModel):
    """산불 예측 응답 모델"""
    latitude: float = Field(..., description="위도")
    longitude: float = Field(..., description="경도")
    probability: float = Field(..., ge=0, le=100, description="산불 발생 확률 (%)")
    color: Literal["red", "orange", "yellow", "green"] = Field(..., description="위험도 색상")

    class Config:
        json_schema_extra = {
            "example": {
                "latitude": 37.54051940470045,
                "longitude": 127.07625231277218,
                "probability": 85.1,
                "color": "red"
            }
        }


def get_risk_color(probability: float) -> Literal["red", "orange", "yellow", "green"]:
    """
    산불 확률에 따른 위험도 색상 반환

    Args:
        probability: 산불 발생 확률 (0-100)

    Returns:
        위험도 색상 (red/orange/yellow/green)
    """
    if probability >= 80:
        return "red"
    elif probability >= 60:
        return "orange"
    elif probability >= 40:
        return "yellow"
    else:
        return "green"
