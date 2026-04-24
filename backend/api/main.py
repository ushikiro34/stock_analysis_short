from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

# .env를 프로젝트 루트에서 명시적으로 로드 (실행 위치 무관)
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=False)

from ..core.score_service import calculate_scores_for_codes
from ..collector.aggregator import Aggregator
from ..collector.websocket_client import KISWebSocketClient

# Import routers
from .routers import (
    stocks_router,
    signals_router,
    backtest_router,
    optimize_router,
    sectors_router,
    paper_router,
    monitor_router,
    live_router,
    briefing_router,
    insights_router,
)

# Install in-memory log buffer (captures all log output for /monitor/logs)
from ..core import log_buffer as _log_buffer
_log_buffer.install()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Stock Analysis API",
    description="단타매매용 주식 분석 시스템",
    version="2.0.0"
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(stocks_router)
app.include_router(signals_router)
app.include_router(backtest_router)
app.include_router(optimize_router)
app.include_router(sectors_router)
app.include_router(paper_router)
app.include_router(monitor_router)
app.include_router(live_router)
app.include_router(briefing_router)
app.include_router(insights_router)


# ── Background Tasks ──────────────────────────────────────────
collector_task: Optional[asyncio.Task] = None
scorer_task: Optional[asyncio.Task] = None
paper_task: Optional[asyncio.Task] = None

# Global caches for background tasks
_surge_cache: dict = {"data": [], "ts": 0}
_us_surge_cache: dict = {"data": [], "ts": 0}

# 스코어러가 고점수 신호 발견 시 페이퍼 엔진을 즉시 깨우는 이벤트
_paper_scan_event: asyncio.Event = asyncio.Event()


async def run_collector():
    """KIS WebSocket 수집을 백그라운드로 계속 실행 (자동 재접속)"""
    import websockets.exceptions
    codes = ["005930", "000660"]
    retry_delay = 5
    while True:
        try:
            agg = Aggregator()
            client = KISWebSocketClient(codes, agg)
            logger.info(f"Starting KIS collector for {codes}")
            await client.connect()
            retry_delay = 5  # 정상 종료 후 재접속 대기 초기화
        except websockets.exceptions.ConnectionClosedError as e:
            logger.warning(f"Collector: WebSocket 연결 끊김 (code={e.code}) — {retry_delay}s 후 재접속")
            await asyncio.sleep(retry_delay)
        except Exception as e:
            logger.error(f"Collector error: {type(e).__name__}: {e} — {retry_delay}s 후 재접속")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)  # 반복 실패 시 최대 60s까지 백오프


async def run_scorer():
    """급등주 리스트 기반 점수 사전 계산 — 5분 주기 (KR + US)"""
    await asyncio.sleep(15)  # 서버 시작 후 대기
    while True:
        try:
            # Import locally to avoid circular dependencies
            from .routers.stocks import _surge_cache as surge_kr
            from .routers.stocks import _us_surge_cache as surge_us

            kr_codes = [s["code"] for s in surge_kr.get("data", [])]
            if kr_codes:
                logger.info(f"Scorer: KR {len(kr_codes)} stocks...")
                kr_results = await calculate_scores_for_codes(kr_codes, market="KR")
                logger.info(f"Scorer: KR completed {len(kr_results)}/{len(kr_codes)}")
                # 고점수 신호 발견 시 페이퍼 엔진 즉시 트리거
                if any(r.get("total_score", 0) >= 50 for r in kr_results):
                    logger.info("Scorer: 고점수 신호 발견 → 페이퍼 엔진 즉시 트리거")
                    _paper_scan_event.set()

            us_codes = [s["code"] for s in surge_us.get("data", [])]
            if us_codes:
                logger.info(f"Scorer: US {len(us_codes)} stocks...")
                us_results = await calculate_scores_for_codes(us_codes, market="US")
                logger.info(f"Scorer: US completed {len(us_results)}/{len(us_codes)}")

            if not kr_codes and not us_codes:
                logger.info("Scorer: No surge stocks yet, waiting...")
                await asyncio.sleep(30)
                continue
        except Exception as e:
            logger.error(f"Scorer task error: {e}")

        await asyncio.sleep(300)


async def run_paper_trading():
    """스코어러 트리거 또는 최대 5분 주기 페이퍼 트레이딩 루프"""
    from ..core.paper_engine import paper_engine
    from ..db.session import AsyncSessionLocal
    await asyncio.sleep(20)   # 서버 시작 대기
    # DB에서 이전 상태 복원
    try:
        async with AsyncSessionLocal() as db:
            await paper_engine.load_from_db(db)
    except Exception as e:
        logger.error(f"Paper engine load error: {e}")
    while True:
        # 스코어러 트리거 대기 (최대 5분)
        try:
            await asyncio.wait_for(_paper_scan_event.wait(), timeout=300)
            logger.info("[Paper] 스코어러 트리거로 즉시 실행")
        except asyncio.TimeoutError:
            pass
        _paper_scan_event.clear()
        try:
            async with AsyncSessionLocal() as db:
                if paper_engine.is_running:
                    await paper_engine.tick(db)
        except Exception as e:
            logger.error(f"Paper trading tick error: {e}")


async def run_morning_briefing():
    """08:20~09:00 KST 창에 장전 브리핑 자동 생성 (5분 주기 체크)"""
    from ..core.morning_briefing import maybe_generate_today_briefing
    from ..db.session import AsyncSessionLocal
    await asyncio.sleep(30)
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await maybe_generate_today_briefing(db)
        except Exception as e:
            logger.error(f"Morning briefing error: {e}")
        await asyncio.sleep(300)


async def run_live_trading():
    """5분 주기 실전 매매 루프 + 장 마감 후 일일 리포트 자동 생성"""
    from ..core.live_engine import live_engine
    from ..core.live_daily_report import maybe_generate_today_report
    from ..db.session import AsyncSessionLocal
    await asyncio.sleep(25)   # 서버 시작 대기
    while True:
        try:
            async with AsyncSessionLocal() as db:
                if live_engine.is_running:
                    await live_engine.tick(db)
                # 15:30 KST 이후라면 오늘 리포트 자동 생성 (이미 있으면 skip)
                await maybe_generate_today_report(db)
        except RuntimeError:
            pass  # LIVE_TRADING_ENABLED=false 시 무시
        except Exception as e:
            logger.error(f"Live trading tick error: {e}")
        await asyncio.sleep(300)


@app.on_event("startup")
async def on_startup():
    import os
    logger.info(f".env 경로: {_ENV_PATH} (존재: {_ENV_PATH.exists()})")
    logger.info(f"KIS_APP_KEY: {'SET' if os.getenv('KIS_APP_KEY') else 'NOT SET'}")
    logger.info(f"KIS_APP_SECRET: {'SET' if os.getenv('KIS_APP_SECRET') else 'NOT SET'}")
    logger.info(f"DATABASE_URL: {'SET' if os.getenv('DATABASE_URL') else 'NOT SET'}")

    # DB 테이블 자동 생성 (없는 경우에만, 기존 테이블은 유지)
    try:
        from ..db.session import engine, Base
        from ..db import models as _db_models  # noqa: ORM 클래스를 Base.metadata에 등록
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("DB tables created/verified")
    except Exception as e:
        logger.error(f"DB table creation failed: {e}")

    global collector_task, scorer_task, paper_task
    collector_task = asyncio.create_task(run_collector())
    scorer_task = asyncio.create_task(run_scorer())
    paper_task = asyncio.create_task(run_paper_trading())
    asyncio.create_task(run_live_trading())
    asyncio.create_task(run_morning_briefing())
    logger.info(f"Background tasks started: collector, scorer, paper_trading, live_trading, morning_briefing")


# ── WebSocket ────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@app.websocket("/ws/{code}")
async def websocket_endpoint(websocket: WebSocket, code: str):
    await manager.connect(websocket)
    logger.info(f"WebSocket connected for code: {code}")
    try:
        while True:
            await websocket.receive_text()
            # TODO: Handle incoming websocket data
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket disconnected for code: {code}")


# ── Root Endpoint ────────────────────────────────────────────
@app.get("/")
async def root():
    """API 정보 및 사용 가능한 엔드포인트"""
    return {
        "name": "Stock Analysis API",
        "version": "2.0.0",
        "description": "단타매매용 주식 분석 시스템",
        "categories": {
            "📊 Stocks": {
                "description": "주식 데이터 조회",
                "endpoints": [
                    "GET /stocks/surge",
                    "GET /stocks/penny-stocks",
                    "GET /stocks/{code}/score",
                    "GET /stocks/{code}/daily",
                    "GET /stocks/{code}/weekly",
                    "GET /stocks/{code}/minute"
                ]
            },
            "🚦 Signals": {
                "description": "매매 신호 생성",
                "endpoints": [
                    "GET /signals/entry/{code}",
                    "GET /signals/scan",
                    "POST /signals/exit"
                ]
            },
            "📈 Backtest": {
                "description": "전략 백테스팅",
                "endpoints": [
                    "POST /backtest/run",
                    "POST /backtest/compare"
                ]
            },
            "🔧 Optimize": {
                "description": "파라미터 최적화",
                "endpoints": [
                    "POST /optimize/grid-search",
                    "POST /optimize/quick",
                    "GET /optimize/metrics",
                    "GET /optimize/param-ranges"
                ]
            },
            "📊 Sectors": {
                "description": "섹터별 실시간 분석",
                "endpoints": [
                    "GET /sectors/list",
                    "GET /sectors/{sector}/analyze",
                    "GET /sectors/compare",
                    "GET /sectors/{sector}/signals"
                ]
            }
        },
        "docs": "/docs",
        "redoc": "/redoc"
    }
