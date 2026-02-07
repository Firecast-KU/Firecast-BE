# 예특보 공통 Feature 스키마 정의
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ForecastRegionInfo(BaseModel):
    """단기예보구역 정보"""

    reg_id: str = Field(description="예보구역코드")
    reg_name_ko: str = Field(description="예보구역 한글명")
    reg_sp: Optional[str] = Field(default=None, description="예보구역 특성 코드")


class ForecastCommonFeature(BaseModel):
    """예측 공통 Feature"""

    reg_id: str = Field(description="예보구역코드")
    region_name_ko: str = Field(description="예보구역 한글명")
    tm_fc: datetime = Field(description="발표시각(KST)")
    tm_ef: datetime = Field(description="발효시각(KST)")
    TA: float = Field(description="기온")
    POP: int = Field(description="강수확률(%)")
    is_precip: int = Field(ge=0, le=1, description="강수발생여부 (0/1)")
    WD_sin: float = Field(description="풍향 sin")
    WD_cos: float = Field(description="풍향 cos")
    SKY: str = Field(description="하늘상태코드")
