# SQLModel을 사용한 데이터베이스 테이블(엔티티) 정의 파일
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel
from sqlalchemy import DECIMAL, BigInteger


class FirePrediction(SQLModel, table=True):
    """산불 예측 메타 정보"""
    __tablename__ = "fire_prediction"

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )# 예측 ID(auto increment)
    predicted_at: datetime = Field(default_factory=datetime.now) # 예측 시각


class FireProbability(SQLModel, table=True):
    """지점별 산불 확률 데이터"""
    __tablename__ = "fire_probability"

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )# 예측 ID(auto increment)
    prediction_id: Optional[int] = Field(
        default=None,
        foreign_key="fire_prediction.id",
    )# 산불 예측 메타 정보와 연동되는 FK
    station_name_ko: Optional[str] = Field(default=None, max_length=100) # 관측소 이름
    latitude: float = Field(sa_type=DECIMAL(9, 6)) # 위도
    longitude: float = Field(sa_type=DECIMAL(9, 6)) # 경도
    probability: float = Field(sa_type=DECIMAL(5, 4)) # 산불 발생 확률 (0.0000 ~ 100.0000)