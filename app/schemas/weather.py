# API 응답 반환용 Pydantic 스키마 정의
from pydantic import BaseModel, Field

class ObservationStationInfo(BaseModel):
    """관측소 정보"""
    id: int = Field(description="관측소 고유 ID")
    latitude: float = Field(ge=-90, le=90, description="위도")
    longitude: float = Field(ge=-180, le=180, description="경도")
    station_name_ko: str = Field(description="관측소 한글명")


class WeatherData(BaseModel):
    """기상 데이터"""
    station_id: int = Field(description="관측소 고유 ID")
    latitude: float = Field(ge=-90, le=90, description="위도")
    longitude: float = Field(ge=-180, le=180, description="경도")
    min_temp: float = Field(description="최저기온 (°C)")
    max_temp: float = Field(description="최고기온 (°C)")
    avg_temp: float = Field(description="평균기온 (°C)")
    precipitation: float = Field(description="강수량 (mm)")