from app.schemas.forecast_response import ForecastResponse, get_risk_color


class AIModelService:
    """AI 모델을 사용한 산불 예측 서비스"""

    def predict_fire_risk(self) -> list[ForecastResponse]:
        """
        AI 모델을 사용하여 산불 위험도 예측

        Returns:
            산불 예측 결과 리스트 - list[ForecastResponse]

        TODO: 실제 AI 모델 연동
        - 모델 로드 및 추론 로직 구현
        - 위도/경도 기반 예측 수행
        - 기상 데이터, 지형 데이터 등 입력 처리
        """
        # TODO: 실제 AI 모델 호출로 대체
        # 현재는 임시 더미 데이터 반환
        mock_predictions = [
            {"latitude": 37.54051940470045, "longitude": 127.07625231277218, "probability": 85.1},
            {"latitude": 37.49572170161351, "longitude": 127.02816889762878, "probability": 72.5},
            {"latitude": 37.57481539038239, "longitude": 127.11940234884572, "probability": 91.3},
            {"latitude": 37.45623178492856, "longitude": 127.15678934521347, "probability": 58.7},
            {"latitude": 37.51234567890123, "longitude": 127.05432109876543, "probability": 68.9},
        ]

        # 확률에 따라 색상 자동 계산
        results = []
        for pred in mock_predictions:
            results.append(
                ForecastResponse(
                    latitude=pred["latitude"],
                    longitude=pred["longitude"],
                    probability=pred["probability"],
                    color=get_risk_color(pred["probability"])
                )
            )

        return results
