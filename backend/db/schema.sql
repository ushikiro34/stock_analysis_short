-- Database Schema for Stock Analysis System
-- Version: 1.0

-- 1. stocks: Master table for stocks
CREATE TABLE IF NOT EXISTS stocks (
    code VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100),
    market VARCHAR(10) -- KOSPI, KOSDAQ, etc.
);

-- 2. tick_data: Raw tick data from WebSocket
CREATE TABLE IF NOT EXISTS tick_data (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(10),
    price NUMERIC,
    volume BIGINT,
    tick_time TIMESTAMP,
    FOREIGN KEY (code) REFERENCES stocks(code)
);

CREATE INDEX IF NOT EXISTS idx_tick_code_time
ON tick_data(code, tick_time DESC);

-- 3. ohlcv_1m: 1-minute candle data
CREATE TABLE IF NOT EXISTS ohlcv_1m (
    code VARCHAR(10),
    minute TIMESTAMP,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume BIGINT,
    PRIMARY KEY (code, minute),
    FOREIGN KEY (code) REFERENCES stocks(code)
);

-- 4. fundamentals: Financial data
CREATE TABLE IF NOT EXISTS fundamentals (
    code VARCHAR(10) PRIMARY KEY,
    per NUMERIC,
    pbr NUMERIC,
    roe NUMERIC,
    eps NUMERIC,
    bps NUMERIC,
    updated_at TIMESTAMP,
    FOREIGN KEY (code) REFERENCES stocks(code)
);

-- 5. score_snapshot: Periodically calculated scores
CREATE TABLE IF NOT EXISTS score_snapshot (
    code VARCHAR(10),
    calculated_at TIMESTAMP,
    value_score NUMERIC,
    trend_score NUMERIC,
    stability_score NUMERIC,
    risk_penalty NUMERIC,
    total_score NUMERIC,
    PRIMARY KEY (code, calculated_at),
    FOREIGN KEY (code) REFERENCES stocks(code)
);

-- Index for better query performance on snapshots
CREATE INDEX IF NOT EXISTS idx_score_snapshot_time ON score_snapshot(calculated_at DESC);
