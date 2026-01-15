# 환경 변수를 로드하는 config 파일
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """환경 변수 설정 클래스"""
    # 기상청 API 키
    KMA_API_KEY: str
    # 기상청 ASOS 관측데이터 URL
    KMA_ASOS_URL: str
    # 지상관측 지점정보 URL
    KMA_STATION_INFO_URL: str

    class Config:
        env_file = ".env"


# 설정 인스턴스 생성 (이걸 다른 파일에서 import 해서 씁니다)
settings = Settings()