# AI 모델 연동 및 산불 위험도 예측 로직을 담당하는 서비스 클래스
import random

from app.schemas.forecast_response import ForecastResponse, get_risk_color

# 대한민국 본토 좌표 범위 (섬 제외)
# 최북단: 38° 36' N (고성군) → 38.60
# 최남단: 34° 17' N (해남군) → 34.28
# 최동단: 129° 35' E (포항시) → 129.58
# 최서단: 126° 06' E (태안군) → 126.10
KOREA_LAT_MIN = 34.28
KOREA_LAT_MAX = 38.60
KOREA_LON_MIN = 126.10
KOREA_LON_MAX = 129.58


def generate_korea_grid_predictions(num_regions: int = 190) -> list[dict]:
    """
    대한민국 본토를 격자로 나눠 더미 예측 데이터 생성

    Args:
        num_regions: 생성할 구역 수 (기본값: 190)

    Returns:
        격자 중심점 좌표와 랜덤 확률값을 포함한 예측 데이터 리스트
    """
    # 격자 크기 계산 (대략 14x14 = 196개에서 190개 선택)
    lat_range = KOREA_LAT_MAX - KOREA_LAT_MIN
    lon_range = KOREA_LON_MAX - KOREA_LON_MIN

    # 14행 x 14열 격자로 분할
    rows = 14
    cols = 14
    lat_step = lat_range / rows
    lon_step = lon_range / cols

    predictions = []

    for row in range(rows):
        for col in range(cols):
            # 각 셀의 중심점 계산
            center_lat = KOREA_LAT_MIN + (row + 0.5) * lat_step
            center_lon = KOREA_LON_MIN + (col + 0.5) * lon_step

            # 10~90 사이의 랜덤 확률값 (소수점 1자리)
            probability = round(random.uniform(10.0, 90.0), 1)

            predictions.append({
                "latitude": round(center_lat, 8),
                "longitude": round(center_lon, 8),
                "probability": probability
            })

    # 196개 중 190개만 선택 (랜덤하게 6개 제외)
    if len(predictions) > num_regions:
        predictions = random.sample(predictions, num_regions)

    return predictions


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
        # 대한민국 본토를 190개 구역으로 나눈 더미 데이터 생성
        mock_predictions = generate_korea_grid_predictions(190)

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
