# AI 모델 연동 및 산불 위험도 예측 로직을 담당하는 서비스 클래스
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.asos.services.asos_feature_service import (
    fetch_asos_station_info,
    get_cached_station_info,
)
from app.forecast.schemas.forecast_response import ForecastResponse, get_risk_color
from app.forecast.services.forecast_feature_service import (
    fetch_common_forecast_features,
)

# 모델 파일 경로
MODEL_DIR = Path(__file__).resolve().parents[3] / "model"
MODEL_PATH = MODEL_DIR / "hgb_v1.joblib"

# SKY 코드 → 정수 매핑 (학습 시 사용된 인코딩과 동일)
SKY_MAP = {"DB01": 1, "DB02": 2, "DB03": 3, "DB04": 4}

# 모델 feature 순서 (hgb_v1_meta.json 기준)
FEATURE_COLUMNS = ["TA", "POP", "is_precip", "WD_sin", "WD_cos", "SKY"]

# 모델 싱글턴 캐시
_model_cache = None


def _load_model():
    """hgb_v1.joblib 모델을 로드한다. 한 번만 로드 후 캐시."""
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {MODEL_PATH}")

    _model_cache = joblib.load(MODEL_PATH)
    print(f"✅ AI 모델 로드 완료: {MODEL_PATH.name}")
    return _model_cache


def _build_feature_row(feature) -> list:
    """
    ForecastCommonFeature → 모델 입력 배열 1행으로 변환

    Args:
        feature: ForecastCommonFeature 또는 동일 필드를 가진 객체

    Returns:
        [TA, POP, is_precip, WD_sin, WD_cos, SKY(int)] 리스트
    """
    return [
        feature.TA,
        feature.POP,
        feature.is_precip,
        feature.WD_sin,
        feature.WD_cos,
        SKY_MAP.get(feature.SKY, 1),
    ]


def _build_station_coordinate_map() -> dict[str, dict]:
    """
    관측소 지점정보를 조회하여 {fct_id: {lat, lon, stn_name_ko}} 매핑 생성.
    동일 예보구역에 여러 관측소가 있으면 첫 번째(대표) 관측소를 사용한다.
    """
    # ASOS 캐시에 지점정보가 있으면 재사용, 없으면 직접 조회
    station_info = get_cached_station_info() or fetch_asos_station_info()
    coord_map: dict[str, dict] = {}

    for stn_info in station_info.values():
        fct_id = stn_info.fct_id
        if not fct_id or fct_id in coord_map:
            continue
        if stn_info.lat is None or stn_info.lon is None:
            continue

        coord_map[fct_id] = {
            "lat": stn_info.lat,
            "lon": stn_info.lon,
            "stn_name_ko": stn_info.stn_name_ko,
        }

    return coord_map


class AIModelService:
    """AI 모델을 사용한 산불 예측 서비스"""

    def predict_fire_risk(self) -> list[ForecastResponse]:
        """
        AI 모델(HistGradientBoostingClassifier)을 사용하여
        예보구역별 산불 위험도를 예측한다.

        [실시간 예측 흐름] 예특보(단기예보) 기반
          1. 단기예보 공통 Feature 조회 (예보구역별)
          2. 관측소 지점정보에서 예보구역 → 좌표 매핑 (fct_id 기반)
          3. SKY 인코딩 + Feature 행렬 구성
          4. hgb_v1.joblib predict_proba() → 산불 확률
          5. ForecastResponse 리스트 반환

        Returns:
            산불 예측 결과 리스트 - list[ForecastResponse]
        """
        # 예보구역별 공통 Feature 조회 (예특보 기반 실시간 예측)
        feature_map = fetch_common_forecast_features()
        if not feature_map:
            print("⚠️ 예보 Feature가 비어있어 예측을 수행할 수 없습니다.")
            return []

        # 관측소 지점정보에서 예보구역코드 → 좌표 매핑
        coord_map = _build_station_coordinate_map()

        # 좌표가 매핑되는 구역만 필터링
        matched_regions = []
        for reg_id, feature in feature_map.items():
            coord = coord_map.get(reg_id)
            if coord:
                matched_regions.append((reg_id, feature, coord))

        if not matched_regions:
            print("⚠️ 예보구역과 관측소 좌표를 매핑할 수 없습니다.")
            return []

        # 모델 로드
        model = _load_model()

        # Feature 행렬 구성 (DataFrame으로 생성하여 feature name 경고 방지)
        X = pd.DataFrame(
            [_build_feature_row(feat) for _, feat, _ in matched_regions],
            columns=FEATURE_COLUMNS,
        )

        # 모델 예측 (predict_proba → 양성 클래스 확률)
        probabilities = model.predict_proba(X)[:, 1]

        # 확률값을 백분율(0~100)로 변환하고 ForecastResponse 생성
        results = []
        for i, (reg_id, feature, coord) in enumerate(matched_regions):
            prob_pct = round(float(probabilities[i]) * 100, 1)
            results.append(
                ForecastResponse(
                    latitude=coord["lat"],
                    longitude=coord["lon"],
                    probability=prob_pct,
                    color=get_risk_color(prob_pct),
                    station_name_ko=coord["stn_name_ko"],
                )
            )

        print(f"✅ AI 모델 예측 완료: {len(results)}개 구역")
        return results
