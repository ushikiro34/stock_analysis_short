import logging
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select
from ..db.session import AsyncSessionLocal
from ..db.models import TickData, OHLCV1m

logger = logging.getLogger(__name__)


class Aggregator:
    def __init__(self):
        self.current_candles = {}  # code -> {minute, open, high, low, close, volume}

    async def process_tick(self, raw_data_str: str):
        """KIS H0STCNT0 실시간 체결 데이터 파싱 및 저장"""
        try:
            # KIS 실시간 데이터: "0|H0STCNT0|001|005930^132000^..."
            # '|' 로 분리 → [암호화여부, tr_id, 건수, 데이터]
            parts = raw_data_str.split("|")
            if len(parts) < 4:
                return

            tr_id = parts[1]
            if tr_id != "H0STCNT0":
                return

            # 데이터부는 '^' 로 필드 분리 (KIS 스펙 기준)
            fields = parts[3].split("^")
            if len(fields) < 15:
                logger.warning(f"Unexpected field count: {len(fields)}")
                return

            # H0STCNT0 주요 필드 (한국투자증권 API 문서 기준)
            # [0] 종목코드, [1] 체결시간(HHMMSS), [2] 현재가
            # [9] 체결거래량, [12] 누적거래량
            code = fields[0]
            time_str = fields[1]       # "HHMMSS"
            price = Decimal(fields[2])
            volume = int(fields[9])    # 체결 거래량

            now = datetime.now()
            tick_time = now.replace(
                hour=int(time_str[:2]),
                minute=int(time_str[2:4]),
                second=int(time_str[4:6]),
                microsecond=0,
            )

            logger.info(f"[{code}] price={price} vol={volume} time={tick_time.strftime('%H:%M:%S')}")

            # DB 저장
            await self.update_ohlcv(code, price, volume, tick_time)

        except Exception as e:
            logger.error(f"Error parsing tick: {e}")

    async def update_ohlcv(self, code: str, price: Decimal, volume: int, time: datetime):
        minute = time.replace(second=0, microsecond=0)

        async with AsyncSessionLocal() as session:
            # 1. Save Tick Data
            tick = TickData(code=code, price=price, volume=volume, tick_time=time)
            session.add(tick)

            # 2. OHLCV 1분봉 업데이트 (upsert)
            result = await session.execute(
                select(OHLCV1m).filter_by(code=code, minute=minute)
            )
            candle = result.scalar_one_or_none()

            if candle is None:
                candle = OHLCV1m(
                    code=code,
                    minute=minute,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=volume,
                )
                session.add(candle)
            else:
                if price > candle.high:
                    candle.high = price
                if price < candle.low:
                    candle.low = price
                candle.close = price
                candle.volume = (candle.volume or 0) + volume

            await session.commit()
