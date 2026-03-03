from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from ..core.score_service import calculate_scores_for_codes
from ..collector.aggregator import Aggregator
from ..collector.websocket_client import KISWebSocketClient
import asyncio
import logging

# Import routers
from .routers import (
    stocks_router,
    signals_router,
    backtest_router,
    optimize_router,
    sectors_router
)

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


# ── Background Tasks ──────────────────────────────────────────
collector_task: Optional[asyncio.Task] = None
scorer_task: Optional[asyncio.Task] = None

# Global caches for background tasks
_surge_cache: dict = {"data": [], "ts": 0}
_us_surge_cache: dict = {"data": [], "ts": 0}


async def run_collector():
    """KIS WebSocket 수집을 백그라운드로 계속 실행 (자동 재접속)"""
    codes = ["005930", "000660"]
    while True:
        try:
            agg = Aggregator()
            client = KISWebSocketClient(codes, agg)
            logger.info(f"Starting KIS collector for {codes}")
            await client.connect()
        except Exception as e:
            logger.error(f"Collector error: {e}, reconnecting in 5s...")
            await asyncio.sleep(5)


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


@app.on_event("startup")
async def on_startup():
    global collector_task, scorer_task
    collector_task = asyncio.create_task(run_collector())
    scorer_task = asyncio.create_task(run_scorer())
    logger.info(f"Background tasks started: collector={collector_task.get_name()}, scorer={scorer_task.get_name()}")


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
