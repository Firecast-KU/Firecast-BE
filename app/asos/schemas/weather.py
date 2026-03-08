# 종관(ASOS) 공통 Feature 스키마 정의
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AsosStationInfo(BaseModel):
    """지상관측 지점 정보"""

    stn: str = Field(description="지점번호")
    stn_name_ko: str = Field(description="지점명(한글)")
    stn_sp: Optional[str] = Field(default=None, description="지점 특성코드")
    lat: Optional[float] = Field(default=None, description="위도(degree)")
    lon: Optional[float] = Field(default=None, description="경도(degree)")
    fct_id: Optional[str] = Field(default=None, description="예보구역코드")


class AsosCommonFeature(BaseModel):
    """종관(ASOS) 기반 공통 Feature"""

    stn: str = Field(description="지점번호")
    stn_name_ko: str = Field(description="지점명(한글)")
    tm: datetime = Field(description="관측시각(KST)")
    TA: float = Field(description="기온")
    POP: int = Field(description="강수확률(0 또는 100)")
    is_precip: int = Field(ge=0, le=1, description="강수발생여부 (0/1)")
    WD_sin: float = Field(description="풍향 sin")
    WD_cos: float = Field(description="풍향 cos")
    SKY: str = Field(description="하늘상태코드")
