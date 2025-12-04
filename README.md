# Firecast-BE
### Firecast 서비스의 FastAPI 기반 백엔드 서버입니다.

## 요구사항

- Python 3.8 이상
- pip

## 설치 및 실행

### 1. 가상환경 활성화

```bash
# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 서버 실행

```bash
# 개발 모드 (자동 리로드)
uvicorn main:app --reload

# 기본 실행
uvicorn main:app
```

서버가 실행되면 http://127.0.0.1:8000 에서 접근 가능합니다.

## API 문서

서버 실행 후 자동 생성되는 API 문서:

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## API 엔드포인트

### GET /api/v1/forecast
산불 예측 데이터 조회

- DB에 최신 데이터(3시간 이내)가 있으면 DB에서 반환
- 없으면 AI 모델로 예측 후 DB에 저장하고 반환

**응답 예시:**
```json
[
  {
    "latitude": 37.54051940470045,
    "longitude": 127.07625231277218,
    "probability": 85.1,
    "color": "red"
  },
  {
    "latitude": 37.49572170161351,
    "longitude": 127.02816889762878,
    "probability": 72.5,
    "color": "orange"
  }
]
```

**위험도 색상 기준:**
- `red`: 확률 80% 이상
- `orange`: 확률 60-80%
- `yellow`: 확률 40-60%
- `green`: 확률 40% 미만

## 프로젝트 구조

```
Firecast-BE/
├── app/
│   ├── api/v1/
│   │   └── api_forecast.py      # Forecast API 엔드포인트
│   ├── models/
│   │   └── db_model.py          # SQLModel 데이터베이스 모델 (FirePrediction, FireProbability)
│   ├── schemas/
│   │   └── forecast_response.py # Pydantic 응답 스키마
│   ├── services/
│   │   ├── forecast_ai_model.py # AI 모델 서비스
│   │   └── forecast_service.py    # 예측 데이터 관리 서비스
│   └── db/
│       └── db_config.py          # 데이터베이스 설정
├── main.py                  # FastAPI 앱 진입점
├── requirements.txt         # 의존성 목록
└── README.md
```

## 개발

### 포트 변경

```bash
uvicorn main:app --reload --port 8080
```

### 호스트 변경 (외부 접근 허용)

```bash
uvicorn main:app --reload --host 0.0.0.0
```

## 기술 스택

- **FastAPI 0.115.13**: 최신 Python 웹 프레임워크
- **SQLModel 0.0.22**: SQLAlchemy + Pydantic 통합 ORM
- **Uvicorn**: ASGI 서버
- **SQLite**: 개발용 데이터베이스 (프로덕션에서는 PostgreSQL 권장)