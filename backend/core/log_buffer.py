"""
In-memory circular log buffer.
서버 로그를 메모리에 최대 500건 유지하여 /monitor/logs API로 조회 가능.
"""
import logging
from collections import deque
from datetime import datetime


class InMemoryLogHandler(logging.Handler):
    def __init__(self, capacity: int = 500):
        super().__init__()
        self._buffer: deque = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord):
        try:
            self._buffer.append({
                "ts": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name.split(".")[-1],
                "msg": self.format(record),
            })
        except Exception:
            pass

    def get_logs(self, min_level: str = "DEBUG", limit: int = 200) -> list:
        level_no = getattr(logging, min_level.upper(), logging.DEBUG)
        logs = [
            entry for entry in self._buffer
            if getattr(logging, entry["level"], 0) >= level_no
        ]
        return list(logs)[-limit:]

    def clear(self):
        self._buffer.clear()


# 앱 전역 싱글턴
_handler = InMemoryLogHandler(capacity=500)


def get_log_handler() -> InMemoryLogHandler:
    return _handler


def install(level: int = logging.DEBUG):
    """루트 로거에 핸들러 등록 — main.py 시작 시 1회 호출"""
    handler = get_log_handler()
    handler.setLevel(level)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)
