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

## 환경 변수
`.env`에 아래 값을 설정합니다.

- `KMA_FORECAST_URL`: 단기예보 육상 조회 URL(인증키 포함 가능)
- `KMA_FORECAST_REGION_URL`: 단기예보 구역정보 조회 URL(인증키 포함 가능)
- `KMA_ASOS_RANGE_URL`: 종관(ASOS) 기간 조회 URL(베이스 URL)
- `KMA_STATION_INFO_URL`: 지상관측 지점정보 조회 URL(지점번호/지점명 매핑용)
- `KMA_API_KEY`: `KMA_ASOS_RANGE_URL`에 `authKey`가 없을 때 쿼리에 자동 주입
- `DATABASE_URL`: 미설정 시 `sqlite:///:memory:` 사용

참고: `DATABASE_URL`이 없으면 인메모리 DB를 사용하므로 서버 재시작 시 데이터가 초기화됩니다.

## API 문서
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## API 엔드포인트
### `GET /api/v1/forecast`
산불 예측 데이터 조회

- 최근 예측이 3시간 이내면 DB의 최신 결과 반환
- 없거나 오래되면 새 예측 수행 후 DB 저장/반환
- 예측 수행 시:
  - 종관(ASOS) 공통 Feature를 30일 주기로 메모리 갱신
  - 지상관측 지점정보(`STN_ID -> STN_KO`)를 함께 조회해 지점명 매핑
  - 예특보 공통 Feature를 조회해 더미 예측(190개 구역) 생성

응답 모델: `ForecastResponse[]`
```json
[
  {
    "latitude": 36.59428571,
    "longitude": 127.21857143,
    "station_name_ko": "보성",
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
종관(ASOS) 30일 수집/파싱 테스트용 임시 API

쿼리:
- `force_refresh` (기본 `true`)
  - `true`: 즉시 재수집
  - `false`: 30일 캐시 유효 시 캐시 반환

응답 예시:
```json
{
  "fetched_at": "2026-02-07T11:15:11.066338",
  "tm1": "202601060000",
  "tm2": "202602050000",
  "total_records": 69664,
  "station_count": 97,
  "station_info_count": 97,
  "sample": {
    "100": [
      {
        "stn": "100",
        "stn_name_ko": "대관령",
        "tm": "2026-01-06T00:00:00",
        "TA": -8.8,
        "POP": 0,
        "is_precip": 0,
        "WD_sin": -0.1736481776669304,
        "WD_cos": -0.984807753012208,
        "SKY": "DB01"
      }
    ]
  }
}
```

## 현재 프로젝트 구조
```text
Firecast-BE/
├── app/
│   ├── asos/
│   │   ├── schemas/
│   │   │   └── weather.py
│   │   └── services/
│   │       └── asos_feature_service.py
│   ├── forecast/
│   │   ├── api/v1/
│   │   │   └── api_forecast.py
│   │   ├── models/
│   │   │   └── db_model.py
│   │   ├── schemas/
│   │   │   ├── forecast_response.py
│   │   │   └── weather.py
│   │   └── services/
│   │       ├── ai_model_service.py
│   │       ├── forecast_feature_service.py
│   │       └── forecast_service.py
│   └── globals/
│       ├── config/
│       │   ├── config.py
│       │   └── db_config.py
│       └── weather/
│           └── kma_common.py
├── main.py
├── requirements.txt
├── data.md
└── README.md
```

## 기술 스택
- FastAPI
- SQLModel
- Uvicorn
- SQLite (기본)
