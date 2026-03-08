# 종관(ASOS) 기반 공통 Feature 수집/캐시 서비스
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock
from typing import Optional
from app.asos.schemas.weather import AsosCommonFeature, AsosStationInfo
from app.globals.weather.kma_common import (
    KMA_DATETIME_FORMAT,
    build_kma_url,
    parse_kma_datetime,
    parse_kma_text_data,
    request_kma_text,
    to_optional_float,
    to_sky_code_from_ca_tot,
    to_wind_unit_vector_from_36,
)
from app.globals.config.config import settings

ASOS_REFRESH_INTERVAL_DAYS = 30
ASOS_SOURCE_WINDOW_START_OFFSET_DAYS = 32
ASOS_SOURCE_WINDOW_END_OFFSET_DAYS = 2


@dataclass
class _AsosCacheState:
    fetched_at: Optional[datetime] = None
    tm1: Optional[datetime] = None
    tm2: Optional[datetime] = None
    features_by_station: dict[str, list[AsosCommonFeature]] = field(default_factory=dict)
    station_info_by_id: dict[str, AsosStationInfo] = field(default_factory=dict)
    total_records: int = 0


_asos_cache = _AsosCacheState()
_asos_cache_lock = Lock()


def _resolve_asos_collection_window(
    reference_time: Optional[datetime] = None,
) -> tuple[datetime, datetime]:
    """
    종관 수집 기간 계산
    - 안정성 확보를 위해 n-32일부터 n-2일까지 조회
    """
    now = reference_time or datetime.now()
    base_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tm1 = base_day - timedelta(days=ASOS_SOURCE_WINDOW_START_OFFSET_DAYS)
    tm2 = base_day - timedelta(days=ASOS_SOURCE_WINDOW_END_OFFSET_DAYS)
    return tm1, tm2


def _build_asos_range_url(tm1: datetime, tm2: datetime) -> str:
    """기준 기간(`tm1`~`tm2`)을 반영한 ASOS 조회 URL을 생성한다."""
    return build_kma_url(
        settings.KMA_ASOS_RANGE_URL,
        tm1=tm1.strftime(KMA_DATETIME_FORMAT),
        tm2=tm2.strftime(KMA_DATETIME_FORMAT),
        stn="",
        help="1",
    )


def _parse_asos_common_features(
    text_data: str,
    station_info_by_id: dict[str, AsosStationInfo],
) -> tuple[dict[str, list[AsosCommonFeature]], int]:
    """ASOS 원천 텍스트를 지점별 공통 Feature 목록으로 파싱한다."""
    raw_rows = parse_kma_text_data(text_data)
    features_by_station: dict[str, list[AsosCommonFeature]] = defaultdict(list)
    total_records = 0

    for parts in raw_rows:
        # 46개 필드 중 공통 Feature에 필요한 최소 인덱스(0,1,2,11,15,25) 확인
        if len(parts) < 26:
            continue

        try:
            tm = parse_kma_datetime(parts[0])
        except ValueError:
            continue

        stn = parts[1]
        ta = to_optional_float(parts[11])
        if ta is None:
            continue

        rn = to_optional_float(parts[15])
        wd = to_optional_float(parts[2])
        ca_tot = to_optional_float(parts[25])

        pop = 100 if rn is not None and rn > 0 else 0
        is_precip = 1 if rn is not None and rn > 0 else 0
        wd_sin, wd_cos = to_wind_unit_vector_from_36(wd)
        sky = to_sky_code_from_ca_tot(ca_tot)
        station_name_ko = (
            station_info_by_id[stn].stn_name_ko
            if stn in station_info_by_id
            else stn
        )

        features_by_station[stn].append(
            AsosCommonFeature(
                stn=stn,
                stn_name_ko=station_name_ko,
                tm=tm,
                TA=ta,
                POP=pop,
                is_precip=is_precip,
                WD_sin=wd_sin,
                WD_cos=wd_cos,
                SKY=sky,
            )
        )
        total_records += 1

    for station_rows in features_by_station.values():
        station_rows.sort(key=lambda feature: feature.tm)

    return dict(features_by_station), total_records


def fetch_asos_station_info() -> dict[str, AsosStationInfo]:
    """지상관측 지점정보를 조회해 `STN_ID -> 지점 메타정보` 매핑을 만든다."""
    try:
        # tm을 현재 시각 기준으로 동적 설정 (운영 중인 관측소 목록 조회)
        now_str = datetime.now().strftime(KMA_DATETIME_FORMAT)
        url = build_kma_url(
            settings.KMA_STATION_INFO_URL,
            inf="SFC",
            stn="",
            tm=now_str,
            help="1",
        )
        text_data = request_kma_text(url)
    except Exception as exc:
        print(f"Exception occurred in fetch_asos_station_info: {exc}")
        return {}

    raw_rows = parse_kma_text_data(text_data)
    station_info_by_id: dict[str, AsosStationInfo] = {}

    for parts in raw_rows:
        # STN_ID(0), LON(1), LAT(2), STN_SP(3), STN_KO(10), FCT_ID(12) 필요
        if len(parts) < 13:
            continue

        stn = parts[0].strip()
        if not stn:
            continue

        stn_sp = parts[3].strip() if len(parts) > 3 else None
        stn_name_ko = parts[10].strip()
        if not stn_name_ko or stn_name_ko == "----":
            stn_name_ko = stn

        # 좌표 파싱 (LON=parts[1], LAT=parts[2])
        try:
            lon = float(parts[1])
            lat = float(parts[2])
        except (ValueError, IndexError):
            lon, lat = None, None

        # 예보구역코드 파싱 (FCT_ID=parts[12])
        fct_id = parts[12].strip() if len(parts) > 12 else None
        if fct_id == "----":
            fct_id = None

        station_info_by_id[stn] = AsosStationInfo(
            stn=stn,
            stn_name_ko=stn_name_ko,
            stn_sp=stn_sp if stn_sp and stn_sp != "----" else None,
            lat=lat,
            lon=lon,
            fct_id=fct_id,
        )

    print(f"✅ 지상관측 지점정보 파싱 성공: {len(station_info_by_id)}개")
    return station_info_by_id


def refresh_asos_common_features_if_needed(
    reference_time: Optional[datetime] = None,
    force_refresh: bool = False,
) -> dict[str, list[AsosCommonFeature]]:
    """
    ASOS 공통 Feature 캐시를 30일 주기로 갱신하고 결과를 반환한다.

    [재학습 파이프라인 전용] 실시간 예측에서는 사용하지 않음.
    TODO: 월 1회 자동 재학습 스케줄러 구현 시 이 함수를 호출하도록 연결
    TODO: 재학습 완료 후 model/ 디렉토리의 모델 파일 교체 로직 구현
    """
    now = reference_time or datetime.now()

    with _asos_cache_lock:
        if (
            not force_refresh
            and _asos_cache.fetched_at is not None
            and now - _asos_cache.fetched_at < timedelta(days=ASOS_REFRESH_INTERVAL_DAYS)
        ):
            return _asos_cache.features_by_station

    tm1, tm2 = _resolve_asos_collection_window(now)
    asos_url = _build_asos_range_url(tm1, tm2)

    try:
        station_info_by_id = fetch_asos_station_info()
        text_data = request_kma_text(asos_url)
        features_by_station, total_records = _parse_asos_common_features(
            text_data,
            station_info_by_id,
        )
    except Exception as exc:
        print(f"Exception occurred in refresh_asos_common_features_if_needed: {exc}")
        with _asos_cache_lock:
            return _asos_cache.features_by_station

    with _asos_cache_lock:
        _asos_cache.fetched_at = now
        _asos_cache.tm1 = tm1
        _asos_cache.tm2 = tm2
        _asos_cache.features_by_station = features_by_station
        _asos_cache.station_info_by_id = station_info_by_id
        _asos_cache.total_records = total_records

    print(
        "✅ 종관(ASOS) 공통 Feature 파싱 완료: "
        f"{total_records}건, 지점 {len(features_by_station)}개 "
        f"(tm1={tm1.strftime(KMA_DATETIME_FORMAT)}, tm2={tm2.strftime(KMA_DATETIME_FORMAT)})"
    )
    return features_by_station


def get_cached_station_info() -> dict[str, AsosStationInfo]:
    """캐시에 저장된 지점정보를 반환한다. 캐시가 비어있으면 빈 dict."""
    with _asos_cache_lock:
        return dict(_asos_cache.station_info_by_id)


def get_asos_common_feature_cache_summary(
    sample_station_limit: int = 3,
    sample_per_station_limit: int = 2,
) -> dict[str, object]:
    """ASOS 캐시 상태와 샘플 데이터 요약을 조회한다."""
    with _asos_cache_lock:
        station_ids = sorted(_asos_cache.features_by_station.keys())[:sample_station_limit]
        sample: dict[str, list[dict[str, object]]] = {}

        for stn in station_ids:
            sample[stn] = [
                feature.model_dump(mode="json")
                for feature in _asos_cache.features_by_station[stn][:sample_per_station_limit]
            ]

        return {
            "fetched_at": _asos_cache.fetched_at.isoformat() if _asos_cache.fetched_at else None,
            "tm1": _asos_cache.tm1.strftime(KMA_DATETIME_FORMAT) if _asos_cache.tm1 else None,
            "tm2": _asos_cache.tm2.strftime(KMA_DATETIME_FORMAT) if _asos_cache.tm2 else None,
            "total_records": _asos_cache.total_records,
            "station_count": len(_asos_cache.features_by_station),
            "station_info_count": len(_asos_cache.station_info_by_id),
            "sample": sample,
        }
