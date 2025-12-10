# 산불 예측 데이터의 DB 저장, 조회 및 만료 여부 확인 등 비즈니스 로직 처리
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.models.db_model import FirePrediction, FireProbability
from app.schemas.forecast_response import ForecastResponse, get_risk_color

class ForecastService:
    """산불 예측 데이터 관리 서비스"""

    def is_forecast_outdated(self, session: Session, hours: int = 3) -> bool:
        """
        DB에 저장된 예측 데이터가 오래되었는지 확인

        Args:
            session: 데이터베이스 세션
            hours: 만료 기준 시간 (기본 3시간)

        Returns:
            True if 데이터가 없거나 오래됨, False otherwise
        """
        statement = select(FirePrediction).order_by(FirePrediction.predicted_at.desc())
        latest_prediction = session.exec(statement).first()

        if not latest_prediction:
            return True

        time_diff = datetime.now() - latest_prediction.predicted_at
        return time_diff > timedelta(hours=hours)

    def save_forecasts(self, session: Session, forecasts: list[ForecastResponse]) -> None:
        """
        예측 결과를 데이터베이스에 저장

        Args:
            session: 데이터베이스 세션
            forecasts: 저장할 예측 결과 리스트
        """
        # 1. 예측 메타 정보 저장
        prediction = FirePrediction()
        session.add(prediction)
        session.commit()
        session.refresh(prediction)

        # 2. 지점별 확률 데이터 저장
        for forecast in forecasts:
            fire_prob = FireProbability(
                prediction_id=prediction.id,
                latitude=forecast.latitude,
                longitude=forecast.longitude,
                probability=forecast.probability
            )
            session.add(fire_prob)

        session.commit()

    def get_latest_forecasts(self, session: Session) -> list[ForecastResponse]:
        """
        데이터베이스에서 최신 예측 데이터 조회

        Args:
            session: 데이터베이스 세션

        Returns:
            예측 결과 리스트
        """
        # 최신 예측 ID 조회
        statement = select(FirePrediction).order_by(FirePrediction.predicted_at.desc())
        latest_prediction = session.exec(statement).first()

        if not latest_prediction:
            return []

        # 해당 예측의 상세 데이터 조회
        prob_statement = select(FireProbability).where(FireProbability.prediction_id == latest_prediction.id)
        probabilities = session.exec(prob_statement).all()

        return [
            ForecastResponse(
                latitude=float(p.latitude),
                longitude=float(p.longitude),
                probability=float(p.probability),
                color=get_risk_color(float(p.probability))
            )
            for p in probabilities
        ]
