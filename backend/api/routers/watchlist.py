"""관심종목 CRUD API — DB 저장으로 다기기 공유"""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...db.models import Watchlist

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistItemIn(BaseModel):
    code: str
    market: str
    name: Optional[str] = None


class WatchlistItemOut(BaseModel):
    id: int
    code: str
    market: str
    name: Optional[str]
    added_at: Optional[datetime]


@router.get("", response_model=List[WatchlistItemOut])
async def get_watchlist(db: AsyncSession = Depends(get_db)):
    """관심종목 전체 조회"""
    result = await db.execute(select(Watchlist).order_by(Watchlist.added_at))
    return result.scalars().all()


@router.post("", response_model=WatchlistItemOut, status_code=201)
async def add_watchlist(item: WatchlistItemIn, db: AsyncSession = Depends(get_db)):
    """관심종목 추가 (중복 시 기존 항목 반환)"""
    # 중복 체크
    result = await db.execute(
        select(Watchlist).where(Watchlist.code == item.code, Watchlist.market == item.market)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    row = Watchlist(code=item.code, market=item.market, name=item.name)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/{code}", status_code=204)
async def delete_watchlist(code: str, market: str, db: AsyncSession = Depends(get_db)):
    """관심종목 삭제"""
    result = await db.execute(
        delete(Watchlist).where(Watchlist.code == code, Watchlist.market == market)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다")
    await db.commit()
