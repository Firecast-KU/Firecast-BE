# 기상청 API 공통 유틸리티
from __future__ import annotations

from datetime import datetime
import math
from typing import Optional

import requests

KMA_DATETIME_FORMAT = "%Y%m%d%H%M"
REQUEST_TIMEOUT_SECONDS = 15
MISSING_VALUE_MARKERS = {"", "-", "-9", "-9.0", "-99", "-99.0", "-999", "-999.0"}

# 16방위 -> 각도(북쪽 0도, 시계방향 증가)
COMPASS_TO_DEGREE = {
    "N": 0.0,
    "NNE": 22.5,
    "NE": 45.0,
    "ENE": 67.5,
    "E": 90.0,
    "ESE": 112.5,
    "SE": 135.0,
    "SSE": 157.5,
    "S": 180.0,
    "SSW": 202.5,
    "SW": 225.0,
    "WSW": 247.5,
    "W": 270.0,
    "WNW": 292.5,
    "NW": 315.0,
    "NNW": 337.5,
}


def parse_kma_text_data(text_data: str) -> list[list[str]]:
    """기상청 텍스트 API 응답에서 데이터 행만 추출"""
    data_list: list[list[str]] = []
    lines = text_data.splitlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if parts:
            data_list.append(parts)

    return data_list


def request_kma_text(url: str) -> str:
    """기상청 텍스트 API를 호출해 EUC-KR 인코딩 본문을 반환한다."""
    response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    response.encoding = "euc-kr"
    return response.text


def parse_kma_datetime(value: str) -> datetime:
    """기상청 시각 포맷(`YYYYMMDDHHMM`) 문자열을 datetime으로 변환한다."""
    return datetime.strptime(value, KMA_DATETIME_FORMAT)


def to_precip_binary(prep_code: str) -> int:
    """예특보 강수코드(`PREP`)를 0/1 이진값으로 변환한다."""
    code = prep_code.strip().replace('"', "")
    return 0 if code == "0" else 1


def to_wind_unit_vector(w1: str, w2: str) -> tuple[float, float]:
    """16방위 풍향 코드를 단위원(sin, cos) 벡터로 변환한다."""
    # 풍향 feature는 최종 방향(w2)을 우선 사용하고, 없으면 w1로 대체
    direction_code = w2 if w2 in COMPASS_TO_DEGREE else w1
    degree = COMPASS_TO_DEGREE.get(direction_code)

    if degree is None:
        return 0.0, 0.0

    radian = math.radians(degree)
    return math.sin(radian), math.cos(radian)


def to_wind_unit_vector_from_36(wd: Optional[float]) -> tuple[float, float]:
    """36방위 수치 풍향을 단위원(sin, cos) 벡터로 변환한다."""
    if wd is None or wd < 0:
        return 0.0, 0.0

    # 36방위는 10도 단위(1=10도 ... 36=360도)
    degree = (wd % 36) * 10.0
    if degree == 360.0:
        degree = 0.0

    radian = math.radians(degree)
    return math.sin(radian), math.cos(radian)


def to_sky_code_from_ca_tot(ca_tot: Optional[float]) -> str:
    """ASOS 전운량(`CA_TOT`)을 예특보 하늘상태 코드(`DB01`~`DB04`)로 매핑한다."""
    if ca_tot is None:
        return "DB04"
    if ca_tot <= 2:
        return "DB01"
    if ca_tot <= 5:
        return "DB02"
    if ca_tot <= 8:
        return "DB03"
    return "DB04"


def to_optional_float(value: str) -> Optional[float]:
    """결측 마커를 처리해 숫자 문자열을 float 또는 None으로 변환한다."""
    text = value.strip()
    if text in MISSING_VALUE_MARKERS:
        return None

    try:
        return float(text)
    except ValueError:
        return None
