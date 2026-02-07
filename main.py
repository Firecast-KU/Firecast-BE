# FastAPI 애플리케이션의 진입점 및 설정 파일 (앱 초기화, 미들웨어, 라우터 등록 등)
from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlmodel import SQLModel

from app.forecast.api.v1 import api_forecast
from app.globals.config.db_config import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시점에 DB 테이블 초기화를 수행한다."""
    # 시작 시: 데이터베이스 테이블 생성
    SQLModel.metadata.create_all(engine)
    yield
    # 종료 시: 정리 작업 (필요 시)


app = FastAPI(
    title="Firecast API",
    description="산불 예측 서비스 API",
    version="1.0.0",
    lifespan=lifespan
)

# API 라우터 등록
app.include_router(api_forecast.router, prefix="/api/v1", tags=["forecast"])


@app.get("/")
async def root():
    """기본 상태 확인용 루트 메시지를 반환한다."""
    return {"message": "Firecast API Server"}


@app.get("/health")
async def health_check():
    """헬스체크 결과를 반환한다."""
    return {"status": "healthy"}
