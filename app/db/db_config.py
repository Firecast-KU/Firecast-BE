from sqlmodel import create_engine, Session

# TODO: 환경 변수로 DATABASE_URL 설정(현재는 로컬 SQLite 사용)
DATABASE_URL = "sqlite:///./firecast.db"

engine = create_engine(
    DATABASE_URL,
    echo=False, # 터미널에 쿼리 로그 표시 여부
    connect_args={"check_same_thread": False}
)


def get_session():
    """데이터베이스 세션 의존성"""
    with Session(engine) as session:
        yield session
