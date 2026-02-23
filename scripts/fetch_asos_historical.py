"""
ASOS 역사 데이터 수집 스크립트
=================================

목적:
    모델 학습용 과거 기상 데이터 확보.
    기상청 ASOS(종관기상관측, Automated Synoptic Observing System) API를 호출해
    STN 104(인천)·105(수원) 두 관측소의 2020~2021년 전체 1시간 단위 관측 기록을
    산불 예측 모델 학습에 필요한 공통 Feature로 변환한 뒤 CSV 파일로 저장한다.

출력 파일 (data/ 폴더):
    data/asos_stn104_2020.csv  ← STN 104, 2020년 전체
    data/asos_stn105_2020.csv  ← STN 105, 2020년 전체
    data/asos_stn104_2021.csv  ← STN 104, 2021년 전체
    data/asos_stn105_2021.csv  ← STN 105, 2021년 전체

CSV 컬럼 (순서 고정):
    TM          관측시각 문자열 (YYYYMMDDHHMM, 예: 202001010100)
    STN         지점번호 정수 (104 또는 105)
    TA          기온 (°C, float)
    POP         강수확률 (0 또는 100, int)
    is_precip   강수발생여부 (0 또는 1, int)
    WD_sin      풍향 sin 값 (-1.0 ~ 1.0, float)
    WD_cos      풍향 cos 값 (-1.0 ~ 1.0, float)
    SKY         하늘상태 코드 ("DB01"~"DB04", str)

결측값 처리 정책:
    - TA(기온)가 결측이면 해당 레코드 전체를 제외한다.
    - RN(강수량)이 결측이면 POP=0, is_precip=0 으로 처리한다.
    - WD(풍향)가 결측이면 WD_sin=0.0, WD_cos=0.0 으로 처리한다.
    - CA_TOT(전운량)가 결측이면 SKY="DB04"(흐림) 으로 처리한다.

실행 방법:
    cd <프로젝트 루트>
    source .venv/bin/activate
    python scripts/fetch_asos_historical.py
"""
from __future__ import annotations

import csv
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# ──────────────────────────────────────────────────────────────────────────────
# sys.path 설정
#   이 스크립트는 scripts/ 하위에 위치하기 때문에 기본 sys.path 로는 app 패키지를
#   찾지 못한다. 프로젝트 루트(_PROJECT_ROOT)를 경로 맨 앞에 삽입해서
#   `from app.xxx import ...` 구문이 정상 동작하도록 한다.
# ──────────────────────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent  # scripts/ 의 상위 = 프로젝트 루트
sys.path.insert(0, str(_PROJECT_ROOT))

# settings: .env 파일에서 KMA_ASOS_RANGE_URL, KMA_API_KEY 등을 읽는다.
from app.globals.config.config import settings  # noqa: E402

# kma_common: 기상청 API 공통 유틸리티 (텍스트 파싱, 단위 변환 등)
from app.globals.weather.kma_common import (  # noqa: E402
    KMA_DATETIME_FORMAT,           # 기상청 시각 포맷 상수: "%Y%m%d%H%M"
    parse_kma_datetime,            # 문자열 → datetime 변환
    parse_kma_text_data,           # 기상청 텍스트 응답 → [[field, ...], ...] 파싱
    request_kma_text,              # HTTP GET 후 EUC-KR 디코딩된 본문 반환
    to_optional_float,             # 결측 마커("-9", "" 등) 처리 후 float 또는 None 반환
    to_sky_code_from_ca_tot,       # 전운량(0~10) → 하늘상태 코드 ("DB01"~"DB04")
    to_wind_unit_vector_from_36,   # 36방위 수치 → (sin, cos) 단위원 벡터
)


# ══════════════════════════════════════════════════════════════════════════════
# 상수 정의
# ══════════════════════════════════════════════════════════════════════════════

# 수집 대상 ASOS 지점 번호
#   104 = 인천  (서해안 영향권)
#   105 = 수원  (내륙 영향권)
TARGET_STATIONS: list[int] = [104, 105]

# 수집 연도별 시작·종료 시각
#   - 시작: 해당 연도 1월 1일 00:00
#   - 종료: 해당 연도 12월 31일 23:00 (ASOS는 정시 단위)
#   2020년은 윤년(366일 × 24 = 최대 8,784건)
#   2021년은 평년(365일 × 24 = 최대 8,760건)
DATE_RANGES: dict[int, tuple[datetime, datetime]] = {
    2020: (datetime(2020, 1, 1, 0, 0), datetime(2020, 12, 31, 23, 0)),
    2021: (datetime(2021, 1, 1, 0, 0), datetime(2021, 12, 31, 23, 0)),
}

# CSV 파일을 저장할 디렉토리 (프로젝트 루트/data/)
OUTPUT_DIR = _PROJECT_ROOT / "data"

# CSV 헤더 컬럼 순서 (이 순서대로 기록됨)
CSV_COLUMNS = ["TM", "STN", "TA", "POP", "is_precip", "WD_sin", "WD_cos", "SKY"]

# 월 청크 API 호출 사이의 대기 시간 (초)
#   기상청 Open API의 분당 호출 제한을 피하기 위해 청크마다 1초씩 쉰다.
CHUNK_DELAY_SECONDS: int = 1

# API 호출 실패 시 재시도 전 대기 시간 (초)
#   일시적인 네트워크 오류나 서버 과부하에 대비한 백오프(back-off) 시간이다.
RETRY_DELAY_SECONDS: int = 5


# ══════════════════════════════════════════════════════════════════════════════
# URL 빌더
# ══════════════════════════════════════════════════════════════════════════════

def build_asos_url(tm1: datetime, tm2: datetime, stn_id: int) -> str:
    """특정 지점·기간을 지정한 ASOS 기간 조회 URL을 생성한다.

    기존 asos_feature_service._build_asos_range_url() 로직과 동일하되,
    캐시 서비스는 전체 지점을 한꺼번에 받기 위해 stn="" 로 설정하는 반면,
    이 스크립트는 지점별 개별 수집을 위해 stn=str(stn_id) 로 고정한다.

    URL 구조 예시:
        https://apihub.kma.go.kr/api/typ01/url/kma_sfctm3.php
            ?tm1=202001010000
            &tm2=202002010000
            &stn=104
            &help=1
            &authKey=<API_KEY>

    Args:
        tm1: 조회 시작 시각 (해당 월 1일 00:00)
        tm2: 조회 종료 시각 (다음 달 1일 00:00, tm2 미만 또는 이하 기준은 API마다 다름)
        stn_id: 지점 번호 (104 또는 105)

    Returns:
        완성된 ASOS 기간 조회 URL 문자열
    """
    # .env 에서 읽은 기본 URL을 파싱해서 쿼리 파라미터만 덮어쓴다.
    parsed = urlparse(settings.KMA_ASOS_RANGE_URL)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))

    # tm1, tm2, stn, help 파라미터를 덮어쓴다.
    #   help=1 → 응답 맨 앞에 컬럼 설명 주석을 포함시켜 디버깅을 쉽게 한다.
    query.update(
        {
            "tm1": tm1.strftime(KMA_DATETIME_FORMAT),  # 예: "202001010000"
            "tm2": tm2.strftime(KMA_DATETIME_FORMAT),  # 예: "202002010000"
            "stn": str(stn_id),                        # 예: "104"
            "help": "1",
        }
    )

    # API 키가 .env 에 설정되어 있고 URL 기본값에 없을 때만 추가한다.
    if settings.KMA_API_KEY and "authKey" not in query:
        query["authKey"] = settings.KMA_API_KEY

    # 변경된 쿼리 파라미터로 URL을 재조립한다.
    return urlunparse(parsed._replace(query=urlencode(query)))


# ══════════════════════════════════════════════════════════════════════════════
# 단일 청크 수집 및 Feature 변환
# ══════════════════════════════════════════════════════════════════════════════

def fetch_single_chunk(tm1: datetime, tm2: datetime, stn_id: int) -> list[dict]:
    """단일 월 청크의 ASOS 원문을 가져와 공통 Feature 레코드 목록으로 변환한다.

    처리 순서:
        1. build_asos_url() 로 URL 생성
        2. request_kma_text() 로 기상청 텍스트 API 호출 (EUC-KR 디코딩)
        3. parse_kma_text_data() 로 주석·헤더 제거 후 행·열 목록으로 파싱
        4. 각 행을 Feature 딕셔너리로 변환 (결측 처리 포함)

    ASOS 텍스트 응답의 주요 컬럼 인덱스 (parts[i]):
        0  → TM       관측시각 (YYYYMMDDHHMM)
        1  → STN      지점번호
        2  → WD       풍향 (36방위 수치, 1=10°, ..., 36=360°)
        11 → TA       기온 (°C)
        15 → RN       강수량 (mm)
        25 → CA_TOT   전운량 (0~10)

    결측 처리 규칙:
        - TA가 결측(None)이면 해당 레코드 전체 제외 (학습 불가 데이터)
        - RN이 결측이면 POP=0, is_precip=0 (강수 없음으로 간주)
        - WD가 결측이면 WD_sin=0.0, WD_cos=0.0 (무풍으로 간주)
        - CA_TOT가 결측이면 SKY="DB04" (흐림으로 간주)

    Args:
        tm1:    청크 시작 시각
        tm2:    청크 종료 시각 (API 파라미터용, 실제 데이터 필터링은 caller 담당)
        stn_id: 지점 번호

    Returns:
        Feature 딕셔너리 목록. 키: TM, STN, TA, POP, is_precip, WD_sin, WD_cos, SKY
    """
    # 1단계: 기상청 API 호출
    url = build_asos_url(tm1, tm2, stn_id)
    text_data = request_kma_text(url)  # EUC-KR 디코딩 후 str 반환

    # 2단계: 텍스트를 행 단위 [[field, ...], ...] 로 파싱
    #         '#' 으로 시작하는 주석 행과 빈 행은 자동으로 제외됨
    raw_rows = parse_kma_text_data(text_data)

    records: list[dict] = []

    for parts in raw_rows:
        # 컬럼이 26개 미만이면 파싱 불가(불완전한 행) → 건너뜀
        #   공통 Feature에 필요한 최소 인덱스: 0, 2, 11, 15, 25 → 26번째 인덱스까지 필요
        if len(parts) < 26:
            continue

        # 관측시각(TM) 파싱 → 형식이 맞지 않으면 비정상 행으로 건너뜀
        try:
            parse_kma_datetime(parts[0])  # 형식 검증용 (반환값은 필터링에 사용 안 함)
        except ValueError:
            continue  # YYYYMMDDHHMM 형식이 아닌 헤더·잔류 주석 행 제거

        # ── 기온 (TA) ─────────────────────────────────────────────────────────
        # parts[11]: TA (기온, °C)
        # 결측 마커("-9", "" 등)는 to_optional_float() 내부에서 None 으로 처리됨
        ta = to_optional_float(parts[11])
        if ta is None:
            # TA 결측 레코드는 학습에 사용 불가하므로 전체 제외
            continue

        # ── 강수량 (RN) → 강수확률(POP) · 강수발생여부(is_precip) ────────────
        # parts[15]: RN (1시간 강수량, mm)
        # RN > 0 이면 강수 있음 → POP=100, is_precip=1
        # RN == 0 또는 결측이면 강수 없음 → POP=0, is_precip=0
        rn = to_optional_float(parts[15])
        pop      = 100 if rn is not None and rn > 0 else 0
        is_precip = 1  if rn is not None and rn > 0 else 0

        # ── 풍향 (WD) → sin·cos 벡터 ─────────────────────────────────────────
        # parts[2]: WD (풍향, 36방위 정수값. 1=10°, 9=90°, 36=360° 등)
        # 풍향을 삼각함수 벡터로 변환하면 360°↔0° 경계 불연속성 문제를 해결할 수 있다.
        # WD 결측(None) 또는 음수이면 to_wind_unit_vector_from_36() 내부에서 (0.0, 0.0) 반환
        wd = to_optional_float(parts[2])
        wd_sin, wd_cos = to_wind_unit_vector_from_36(wd)

        # ── 전운량 (CA_TOT) → 하늘상태 코드 (SKY) ────────────────────────────
        # parts[25]: CA_TOT (전운량, 0~10 옥타 단위)
        #   0~2 → DB01(맑음)   3~5 → DB02(구름조금)
        #   6~8 → DB03(구름많음)  9~10 또는 결측 → DB04(흐림)
        ca_tot = to_optional_float(parts[25])
        sky = to_sky_code_from_ca_tot(ca_tot)

        # ── 레코드 딕셔너리 조립 ──────────────────────────────────────────────
        records.append(
            {
                # TM: 원본 문자열 그대로 저장 (datetime 변환 없이 12자리 숫자 문자열)
                #     예: "202001010100" → 2020-01-01 01:00
                "TM": parts[0],
                # STN: 지점번호 (int). API 응답의 parts[1] 대신 파라미터로 받은 값을 씀.
                #      이렇게 하면 다중 지점 응답이 섞여 들어와도 올바른 지점 정보를 유지함.
                "STN": stn_id,
                "TA": ta,
                "POP": pop,
                "is_precip": is_precip,
                "WD_sin": wd_sin,
                "WD_cos": wd_cos,
                "SKY": sky,
            }
        )

    return records


# ══════════════════════════════════════════════════════════════════════════════
# 월별 청크 목록 생성
# ══════════════════════════════════════════════════════════════════════════════

def generate_monthly_chunks(
    start_dt: datetime,
    end_dt: datetime,
) -> list[tuple[datetime, datetime]]:
    """연도 전체를 월 단위 (chunk_start, chunk_end) 쌍의 목록으로 분할한다.

    연도 전체를 한 번에 요청하면 응답 데이터가 너무 커서 타임아웃이나
    API 거절이 발생할 수 있다. 따라서 월 단위로 나누어 12번 요청한다.

    chunk_end 의 의미:
        API 파라미터 tm2 로 사용되는 값이며 "다음 달 1일 00:00" 이다.
        실제 유효 레코드가 end_dt 를 초과하지 않도록 하는 필터링은
        fetch_year_station() 에서 별도로 수행한다.

    예시 (2020년):
        청크 01: (2020-01-01, 2020-02-01)  ← 1월 수집용
        청크 02: (2020-02-01, 2020-03-01)  ← 2월 수집용
        ...
        청크 12: (2020-12-01, 2021-01-01)  ← 12월 수집용 (API tm2 는 2021년이어도 됨)

    Args:
        start_dt: 수집 시작 시각 (해당 연도 1월 1일 00:00)
        end_dt:   수집 종료 시각 (해당 연도 12월 31일 23:00)

    Returns:
        (chunk_start, chunk_end) 튜플 목록 (시간순 정렬)
    """
    chunks: list[tuple[datetime, datetime]] = []

    # 항상 해당 월의 1일 00:00 부터 시작하도록 정규화한다.
    current = start_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # end_dt 의 달(month) 까지 포함해서 반복한다.
    while current.year < end_dt.year or (
        current.year == end_dt.year and current.month <= end_dt.month
    ):
        # 다음 달 1일 계산: 12월이면 내년 1월로 넘어간다.
        if current.month == 12:
            next_month = datetime(current.year + 1, 1, 1, 0, 0)
        else:
            next_month = datetime(current.year, current.month + 1, 1, 0, 0)

        chunks.append((current, next_month))
        current = next_month  # 한 달씩 앞으로 이동

    return chunks


# ══════════════════════════════════════════════════════════════════════════════
# 연도·지점 전체 수집
# ══════════════════════════════════════════════════════════════════════════════

def fetch_year_station(
    year: int,
    stn_id: int,
    start_dt: datetime,
    end_dt: datetime,
) -> list[dict]:
    """연도·지점 전체 데이터를 월별 청크로 순회하며 수집하고 정제한다.

    흐름:
        generate_monthly_chunks() 로 12개 청크를 생성한 후 순서대로 호출.
        각 청크 호출 실패 시 1회 재시도(5초 대기).
        모든 청크 수집 완료 후:
            1. [start_dt, end_dt] 범위 밖 레코드 제거
               (마지막 청크의 tm2 가 다음 연도를 가리키는 경우 12월 31일 23:00 이후 데이터 제거)
            2. TM 기준 중복 제거 (API 중복 응답 방어)
            3. TM 기준 오름차순 정렬

    Args:
        year:     수집 연도 (로그 출력용)
        stn_id:   지점 번호 (104 또는 105)
        start_dt: 해당 연도 시작 시각
        end_dt:   해당 연도 종료 시각

    Returns:
        정제된 Feature 딕셔너리 목록 (시간순 정렬, TM 중복 없음)
    """
    chunks = generate_monthly_chunks(start_dt, end_dt)
    all_records: list[dict] = []

    for i, (chunk_start, chunk_end) in enumerate(chunks):
        # 진행 상황 출력: [01/12] STN=104 2020-01 수집 중...
        label = chunk_start.strftime("%Y-%m")
        print(f"  [{i + 1:02d}/{len(chunks)}] STN={stn_id} {label} 수집 중...", end=" ")

        try:
            # 1차 시도: 월 단위 ASOS 데이터 수집 및 Feature 변환
            records = fetch_single_chunk(chunk_start, chunk_end, stn_id)
            print(f"{len(records)}건")
        except Exception as exc:
            # 1차 실패 → 일시적 오류일 수 있으므로 5초 대기 후 재시도
            print(f"\n  ⚠️  1차 실패: {exc}")
            print(f"       → {RETRY_DELAY_SECONDS}초 후 재시도...")
            time.sleep(RETRY_DELAY_SECONDS)

            try:
                # 2차 시도 (1회 재시도)
                records = fetch_single_chunk(chunk_start, chunk_end, stn_id)
                print(f"  ♻️  재시도 성공: {len(records)}건")
            except Exception as exc2:
                # 재시도도 실패하면 해당 청크를 건너뛰고 계속 진행
                #   → 연속 실패 시 전체 중단 대신 최대한 다른 달 데이터를 확보한다.
                print(f"  ❌ 재시도 실패 (청크 건너뜀): {exc2}")
                records = []

        all_records.extend(records)

        # 마지막 청크가 아니면 다음 청크 호출 전 1초 대기 (API 과부하 방지)
        if i < len(chunks) - 1:
            time.sleep(CHUNK_DELAY_SECONDS)

    # ── 후처리 1: 연도 범위 필터 ──────────────────────────────────────────────
    # 마지막 청크의 tm2 가 다음 연도 1월 1일이기 때문에,
    # API 응답에 다음 연도 데이터가 포함될 수 있다. end_dt 기준으로 자른다.
    def _parse_tm(tm_str: str) -> datetime:
        """TM 문자열(YYYYMMDDHHMM)을 datetime 으로 변환하는 내부 헬퍼."""
        return datetime.strptime(tm_str, KMA_DATETIME_FORMAT)

    filtered = [
        r for r in all_records
        if start_dt <= _parse_tm(r["TM"]) <= end_dt
    ]

    # ── 후처리 2: TM 기준 중복 제거 ──────────────────────────────────────────
    # 청크 경계에서 동일 TM 이 두 번 포함될 수 있으므로 set 으로 중복을 제거한다.
    # 먼저 등장한 레코드를 우선 사용(순서 유지 = 입력 순서 기반 첫 번째 값 채택).
    seen: set[str] = set()
    unique: list[dict] = []
    for rec in filtered:
        if rec["TM"] not in seen:
            seen.add(rec["TM"])
            unique.append(rec)

    # ── 후처리 3: 시간순 정렬 ────────────────────────────────────────────────
    # TM 문자열이 YYYYMMDDHHMM 형식이므로 문자열 사전순 정렬 = 시간순 정렬과 동일하다.
    unique.sort(key=lambda r: r["TM"])

    return unique


# ══════════════════════════════════════════════════════════════════════════════
# CSV 출력
# ══════════════════════════════════════════════════════════════════════════════

def write_csv(records: list[dict], output_path: Path) -> None:
    """Feature 레코드 목록을 지정된 경로에 CSV 파일로 저장한다.

    - 파일이 없으면 새로 생성, 있으면 덮어쓴다.
    - 부모 디렉토리(data/)가 없으면 자동 생성한다.
    - 인코딩: UTF-8 (BOM 없음)
    - 줄바꿈: 플랫폼 독립적 (\r\n 방지를 위해 newline="" 지정)
    - 헤더: CSV_COLUMNS 순서 고정

    컬럼별 저장 포맷:
        TM        → 문자열 그대로   예: 202001010100
        STN       → 정수            예: 104
        TA        → float           예: -2.4
        POP       → 정수 0 또는 100 예: 0
        is_precip → 정수 0 또는 1   예: 0
        WD_sin    → float           예: 0.7071
        WD_cos    → float           예: 0.7071
        SKY       → 문자열          예: DB02

    Args:
        records:     write_csv() 에 전달할 Feature 딕셔너리 목록
        output_path: 저장할 CSV 파일 경로
    """
    # 부모 디렉토리(data/)가 없으면 재귀적으로 생성한다.
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        # CSV_COLUMNS 순서를 강제하는 DictWriter 사용
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()     # 첫 번째 행: TM,STN,TA,POP,is_precip,WD_sin,WD_cos,SKY
        writer.writerows(records)  # 나머지 행: 각 레코드 딕셔너리를 컬럼 순서에 맞게 기록


# ══════════════════════════════════════════════════════════════════════════════
# 진입점
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """스크립트 진입점. DATE_RANGES × TARGET_STATIONS 조합으로 CSV 4개를 생성한다.

    실행 순서:
        2020년 STN 104 → 2020년 STN 105 → 2021년 STN 104 → 2021년 STN 105
    총 API 호출 횟수: 2연도 × 2지점 × 12청크 = 48회
    예상 소요 시간: 약 2~5분 (네트워크 상태에 따라 다름)
    """
    # data/ 디렉토리가 없으면 생성한다.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 연도 반복 (2020, 2021)
    for year, (start, end) in DATE_RANGES.items():

        # 지점 반복 (104, 105)
        for stn in TARGET_STATIONS:
            print(f"\n🔄 STN={stn}, {year}년 수집 시작 ({start.date()} ~ {end.date()})")

            # 해당 연도·지점의 전체 데이터 수집 및 정제
            records = fetch_year_station(year, stn, start, end)

            # 출력 파일 경로: data/asos_stn<STN>_<YEAR>.csv
            output = OUTPUT_DIR / f"asos_stn{stn}_{year}.csv"

            # CSV 저장
            write_csv(records, output)

            # 저장 결과 요약 출력
            print(f"✅ {output.relative_to(_PROJECT_ROOT)} → {len(records):,}건 저장 완료")

    print("\n🎉 전체 수집 완료")


# 스크립트로 직접 실행할 때만 main() 을 호출한다.
# (`import` 로 불러올 때는 실행되지 않음)
if __name__ == "__main__":
    main()
