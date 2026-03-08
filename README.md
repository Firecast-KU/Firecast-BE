# Firecast-BE
Firecast 서비스의 FastAPI 기반 백엔드 서버입니다.

## 요구사항
- Python 3.10 이상 권장
- `pip`

## 설치 및 실행
1. 가상환경 활성화
```bash
# macOS/Linux
source .venv/bin/activate

# Windows
.venv\\Scripts\\activate
```

2. 의존성 설치
```bash
pip install -r requirements.txt
```

3. 서버 실행
```bash
# 개발 모드
uvicorn main:app --reload

# 기본 실행
uvicorn main:app
```

서버 기본 주소: `http://127.0.0.1:8000`

## 두 가지 데이터 흐름

이 프로젝트에는 **실시간 예측**과 **모델 재학습**, 두 가지 독립된 데이터 흐름이 있습니다.

### 흐름 1: 실시간 예측 (예특보 → AI 모델 → 응답)
```
GET /api/v1/forecast
    ↓
DB 캐시 확인 (3시간 이내 데이터 있으면 바로 반환)
    ↓ (없거나 오래됨)
기상청 예특보(단기예보) 조회 → 구역별 공통 Feature 생성
    ↓  (TA, POP, is_precip, WD_sin, WD_cos, SKY)
관측소 지점정보에서 예보구역 → 좌표 매핑 (fct_id 기준)
    ↓
hgb_v1.joblib 모델 추론 (predict_proba)
    ↓
DB 저장 + ForecastResponse 반환
```
- **데이터 원천:** 기상청 예특보 — 미래 기상 예보
- **모델:** `model/hgb_v1.joblib` (HistGradientBoostingClassifier)
- **커버리지:** 약 88개 구역 (관측소 좌표와 매핑되는 예보구역)

### 흐름 2: 모델 재학습 (ASOS 종관 수집) — TODO 미완성
```
[TODO] 월 1회 스케줄러
    ↓
ASOS 종관 30일 관측 데이터 수집 (n-32일 ~ n-2일)
    ↓
[TODO] 학습 데이터 구성 + 모델 재학습
    ↓
[TODO] model/hgb_v1.joblib 교체
```
- **데이터 원천:** 기상청 ASOS — 과거 관측 데이터
- **현재 상태:** 데이터 수집까지 구현. 재학습 파이프라인/스케줄러/모델 교체 미구현.
- **코드 위치:** `asos_feature_service.py` → `refresh_asos_common_features_if_needed()`

## 환경 변수
`.env`에 아래 값을 설정합니다. **모든 URL은 base URL만 저장하고, `authKey`와 동적 파라미터는 코드에서 자동 주입합니다.**

| 변수 | 필수 | 설명 |
|------|------|------|
| `KMA_API_KEY` | ✅ | 기상청 API 인증키 (모든 API 호출에 authKey로 자동 주입) |
| `KMA_FORECAST_URL` | ✅ | 단기예보 육상 base URL |
| `KMA_FORECAST_REGION_URL` | ✅ | 단기예보구역 base URL |
| `KMA_ASOS_RANGE_URL` | ✅ | 종관(ASOS) 기간 조회 base URL |
| `KMA_STATION_INFO_URL` | ✅ | 지상관측 지점정보 base URL |
| `DATABASE_URL` | ❌ | 미설정 시 `sqlite:///:memory:` (서버 재시작 시 초기화) |

`.env` 예시:
```
KMA_API_KEY=YOUR_API_KEY
KMA_FORECAST_URL=https://apihub.kma.go.kr/api/typ01/url/fct_afs_dl.php
KMA_FORECAST_REGION_URL=https://apihub.kma.go.kr/api/typ01/url/fct_shrt_reg.php
KMA_ASOS_RANGE_URL=https://apihub.kma.go.kr/api/typ01/url/kma_sfctm3.php
KMA_STATION_INFO_URL=https://apihub.kma.go.kr/api/typ01/url/stn_inf.php
```

## API 문서
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## API 엔드포인트
### `GET /api/v1/forecast`
산불 예측 데이터 조회

- 최근 예측이 3시간 이내면 DB의 최신 결과 반환
- 없거나 오래되면 예특보 기반 AI 모델 예측 수행 후 DB 저장/반환

응답 모델: `ForecastResponse[]`
```json
[
  {
    "latitude": 128.56473,
    "longitude": 38.25085,
    "station_name_ko": "속초",
    "probability": 72.8,
    "color": "orange"
  }
]
```

위험도 색상 기준:
- `red`: 80 이상
- `orange`: 60 이상 80 미만
- `yellow`: 40 이상 60 미만
- `green`: 40 미만

### `GET /api/v1/weather/asos/test`
종관(ASOS) 30일 수집/파싱 테스트용 임시 API (재학습 파이프라인용)

쿼리:
- `force_refresh` (기본 `true`): 즉시 재수집 / 30일 캐시 유효 시 캐시 반환

## 현재 프로젝트 구조
```text
Firecast-BE/
├── app/
│   ├── asos/                          # ASOS 종관 (재학습 전용)
│   │   ├── schemas/
│   │   │   └── weather.py             #   AsosStationInfo, AsosCommonFeature
│   │   └── services/
│   │       └── asos_feature_service.py#   ASOS 수집/캐시, 지점정보 조회
│   ├── forecast/                      # 실시간 예측
│   │   ├── api/v1/
│   │   │   └── api_forecast.py        #   GET /api/v1/forecast
│   │   ├── models/
│   │   │   └── db_model.py            #   FirePrediction, FireProbability
│   │   ├── schemas/
│   │   │   ├── forecast_response.py   #   ForecastResponse, get_risk_color
│   │   │   └── weather.py             #   ForecastCommonFeature
│   │   └── services/
│   │       ├── ai_model_service.py    #   모델 로드/추론
│   │       ├── forecast_feature_service.py  # 예특보 → 공통 Feature
│   │       └── forecast_service.py    #   DB 저장/조회, 3시간 캐싱
│   └── globals/
│       ├── config/
│       │   ├── config.py              #   환경 변수 (KMA_API_KEY 등)
│       │   └── db_config.py           #   DB 엔진/세션
│       └── weather/
│           └── kma_common.py          #   기상청 API 공통 (build_kma_url 등)
├── model/
│   ├── hgb_v1.joblib                  # AI 모델 (HistGradientBoosting)
│   └── hgb_v1_meta.json              # 모델 메타정보
├── scripts/
│   └── fetch_asos_historical.py       # ASOS 역사 데이터 수집 스크립트
├── main.py
├── requirements.txt
└── README.md
```

## 기술 스택
- FastAPI, Uvicorn
- SQLModel, SQLite (기본)
- scikit-learn (HistGradientBoostingClassifier)
- joblib, numpy, pandas
