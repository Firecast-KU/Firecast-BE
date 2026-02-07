# 환경 변수를 로드하는 config 파일
from typing import Optional
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """환경 변수 설정 클래스"""
    # 기상청 API 키
    KMA_API_KEY: Optional[str] = None
    # 단기예보 육상 조회 URL
    KMA_FORECAST_URL: str
    # 단기예보구역 조회 URL
    KMA_FORECAST_REGION_URL: str
    # 기상청 ASOS 기간 관측 데이터 URL(최근 30일, 파리미터 직접 설정해야 함)
    # 파라미터: tm1 : 시작일(YYYYMMDD), tm2 : 종료일(YYYYMMDD), stn="", authKey=KMA_API_KEY
    KMA_ASOS_RANGE_URL: str
    # 지상관측 지점정보 URL
    KMA_STATION_INFO_URL: str

    class Config:
        env_file = ".env"


# 설정 인스턴스 생성 (이걸 다른 파일에서 import 해서 씁니다)
settings = Settings()
