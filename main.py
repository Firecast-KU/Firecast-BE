# FastAPI 애플리케이션의 진입점 및 설정 파일 (앱 초기화, 미들웨어, 라우터 등록 등)
from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlmodel import SQLModel

from app.api.v1 import api_forecast
from app.db.db_config import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 실행되는 이벤트"""
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
    return {"message": "Firecast API Server"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
