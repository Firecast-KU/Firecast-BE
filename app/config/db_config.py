# 데이터베이스 연결 설정 및 세션 관리 (환경 변수 로드, DB 엔진 생성)
import os
from dotenv import load_dotenv
from sqlmodel import create_engine, Session

# .env 파일 로드
load_dotenv()

# 환경 변수에서 DATABASE_URL 가져오기, 없으면 In-Memory SQLite 사용
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///:memory:")

if DATABASE_URL == "sqlite:///:memory:":
    print("WARNING: Using In-Memory Database (No DATABASE_URL found)")

engine = create_engine(
    DATABASE_URL,
    echo=False, # 터미널에 쿼리 로그 표시 여부
    connect_args={"check_same_thread": False}
)


def get_session():
    """데이터베이스 세션 의존성"""
    with Session(engine) as session:
        yield session
