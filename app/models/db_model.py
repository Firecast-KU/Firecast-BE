from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel
from sqlalchemy import DECIMAL


class FirePrediction(SQLModel, table=True):
    """산불 예측 메타 정보"""
    __tablename__ = "fire_prediction"

    id: Optional[int] = Field(default=None, primary_key=True)
    predicted_at: datetime = Field(default_factory=datetime.now)


class FireProbability(SQLModel, table=True):
    """지점별 산불 확률 데이터"""
    __tablename__ = "fire_probability"

    id: Optional[int] = Field(default=None, primary_key=True)
    prediction_id: Optional[int] = Field(default=None, foreign_key="fire_prediction.id")
    latitude: float = Field(sa_type=DECIMAL(9, 6))
    longitude: float = Field(sa_type=DECIMAL(9, 6))
    probability: float = Field(sa_type=DECIMAL(5, 4))

