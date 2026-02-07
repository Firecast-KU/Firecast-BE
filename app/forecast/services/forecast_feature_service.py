# 예특보(단기예보) 기반 공통 Feature 생성 서비스
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.forecast.schemas.weather import ForecastCommonFeature, ForecastRegionInfo
from app.globals.weather.kma_common import (
    KMA_DATETIME_FORMAT,
    parse_kma_datetime,
    parse_kma_text_data,
    request_kma_text,
    to_precip_binary,
    to_wind_unit_vector,
)
from app.globals.config.config import settings


@dataclass
class _ForecastRawRow:
    reg_id: str
    tm_fc: datetime
    tm_ef: datetime
    w1: str
    trend: str
    w2: str
    ta: float
    pop: int
    sky: str
    prep: str


def _resolve_prediction_cycle(reference_time: Optional[datetime] = None) -> datetime:
    """
    예측 사이클 시각 계산 (06시, 18시 기준)
    - 00:00~05:59 -> 전일 18:00
    - 06:00~17:59 -> 당일 06:00
    - 18:00~23:59 -> 당일 18:00
    """
    now = reference_time or datetime.now()
    base = now.replace(minute=0, second=0, microsecond=0)

    if base.hour >= 18:
        return base.replace(hour=18)
    if base.hour >= 6:
        return base.replace(hour=6)
    return (base - timedelta(days=1)).replace(hour=18)


def _resolve_target_effective_time(cycle_time: datetime) -> datetime:
    """
    예측 시각별 목표 발효시각 계산
    - 18:00 예측 -> 익일 00:00 feature 사용
    - 06:00 예측 -> 익일 12:00 feature 사용
    """
    if cycle_time.hour == 18:
        return cycle_time + timedelta(hours=6)
    return cycle_time + timedelta(hours=30)


def _select_effective_row(
    rows: list[_ForecastRawRow],
    target_time: datetime,
) -> Optional[_ForecastRawRow]:
    """목표 발효시각과 같은 시각대를 만족하는 가장 적절한 행을 선택한다."""
    # 요구사항: 날짜는 달라도 되나 시각(hour/minute)은 동일해야 함.
    same_clock_future = [
        row
        for row in rows
        if row.tm_ef >= target_time
        and row.tm_ef.hour == target_time.hour
        and row.tm_ef.minute == target_time.minute
    ]
    if same_clock_future:
        return min(same_clock_future, key=lambda row: row.tm_ef)

    # 예외적으로 미래 데이터가 비어있으면 동일 시각 중 최신값으로 대체
    same_clock_any = [
        row
        for row in rows
        if row.tm_ef.hour == target_time.hour and row.tm_ef.minute == target_time.minute
    ]
    if same_clock_any:
        return max(same_clock_any, key=lambda row: row.tm_ef)

    return None


def fetch_forecast_region_info() -> dict[str, ForecastRegionInfo]:
    """단기예보구역 데이터 조회 및 REG_ID -> 구역 정보 매핑"""
    try:
        text_data = request_kma_text(settings.KMA_FORECAST_REGION_URL)
    except Exception as exc:
        print(f"Exception occurred in fetch_forecast_region_info: {exc}")
        return {}

    region_map: dict[str, ForecastRegionInfo] = {}
    raw_rows = parse_kma_text_data(text_data)

    for parts in raw_rows:
        if len(parts) < 5:
            continue

        reg_id = parts[0]
        reg_sp = parts[3]
        reg_name = " ".join(parts[4:])

        region_map[reg_id] = ForecastRegionInfo(
            reg_id=reg_id,
            reg_name_ko=reg_name,
            reg_sp=reg_sp,
        )

    print(f"✅ 예보구역 파싱 성공: {len(region_map)}개")
    return region_map


def _fetch_forecast_rows() -> list[_ForecastRawRow]:
    """예특보 원천을 조회해 `(REG_ID, TM_EF)` 기준 최신 발표행으로 정규화한다."""
    try:
        text_data = request_kma_text(settings.KMA_FORECAST_URL)
    except Exception as exc:
        print(f"Exception occurred in _fetch_forecast_rows: {exc}")
        return []

    raw_rows = parse_kma_text_data(text_data)
    latest_by_reg_and_tm_ef: dict[tuple[str, datetime], _ForecastRawRow] = {}

    for parts in raw_rows:
        if len(parts) < 16:
            continue

        try:
            row = _ForecastRawRow(
                reg_id=parts[0],
                tm_fc=parse_kma_datetime(parts[1]),
                tm_ef=parse_kma_datetime(parts[2]),
                w1=parts[9],
                trend=parts[10],
                w2=parts[11],
                ta=float(parts[12]),
                pop=int(float(parts[13])),
                sky=parts[14],
                prep=parts[15],
            )
        except (ValueError, IndexError):
            continue

        key = (row.reg_id, row.tm_ef)
        current = latest_by_reg_and_tm_ef.get(key)
        if current is None or row.tm_fc > current.tm_fc:
            latest_by_reg_and_tm_ef[key] = row

    return list(latest_by_reg_and_tm_ef.values())


def fetch_common_forecast_features(
    reference_time: Optional[datetime] = None,
) -> dict[str, ForecastCommonFeature]:
    """
    단기예보 육상 + 예보구역 데이터를 합쳐 공통 Feature 생성

    Returns:
        dict[str, ForecastCommonFeature]:
            key(str)는 예보구역코드 `REG_ID`, value는 해당 구역의 공통 Feature.
    """
    region_map = fetch_forecast_region_info()
    forecast_rows = _fetch_forecast_rows()

    if not forecast_rows:
        return {}

    cycle_time = _resolve_prediction_cycle(reference_time)
    target_time = _resolve_target_effective_time(cycle_time)

    rows_by_region: dict[str, list[_ForecastRawRow]] = defaultdict(list)
    for row in forecast_rows:
        rows_by_region[row.reg_id].append(row)

    features: dict[str, ForecastCommonFeature] = {}

    for reg_id, rows in rows_by_region.items():
        selected = _select_effective_row(rows, target_time)
        if selected is None:
            continue

        wd_sin, wd_cos = to_wind_unit_vector(selected.w1, selected.w2)
        region_name = region_map.get(reg_id).reg_name_ko if reg_id in region_map else reg_id

        features[reg_id] = ForecastCommonFeature(
            reg_id=reg_id,
            region_name_ko=region_name,
            tm_fc=selected.tm_fc,
            tm_ef=selected.tm_ef,
            TA=selected.ta,
            POP=selected.pop,
            is_precip=to_precip_binary(selected.prep),
            WD_sin=wd_sin,
            WD_cos=wd_cos,
            SKY=selected.sky,
        )

    print(
        "✅ 공통 Feature 생성 완료: "
        f"{len(features)}개 (cycle={cycle_time.strftime(KMA_DATETIME_FORMAT)}, "
        f"target={target_time.strftime(KMA_DATETIME_FORMAT)})"
    )
    return features
