"""API Routers"""
from .stocks import router as stocks_router
from .signals import router as signals_router
from .backtest import router as backtest_router
from .optimize import router as optimize_router
from .sectors import router as sectors_router
from .paper_trading import router as paper_router
from .monitor import router as monitor_router
from .live_trading import router as live_router

__all__ = [
    "stocks_router",
    "signals_router",
    "backtest_router",
    "optimize_router",
    "sectors_router",
    "paper_router",
    "monitor_router",
    "live_router",
]
