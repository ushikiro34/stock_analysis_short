const BASE_URL = 'http://localhost:8000';

export type Market = 'KR' | 'US';

// ── Types ─────────────────────────────────────────────────────

export interface SurgeStock {
    code: string;
    name: string;
    price: number;
    change_rate: number;
    volume: number;
    change_price: number;
}

export interface StockScore {
    code: string;
    calculated_at?: string;
    value_score?: number;
    trend_score?: number;
    stability_score?: number;
    risk_penalty?: number;
    total_score?: number;
    fundamental?: {
        per: number;
        pbr: number;
        roe: number;
        eps: number;
        bps: number;
        net_loss?: boolean;
        high_debt?: boolean;
    };
    technical?: {
        rsi: number;
        ma20?: number;
        ma60?: number;
        volatility: number;
        return_60d: number;
    };
}

export interface OHLCV {
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
}

export interface EntrySignal {
    code: string;
    market: string;
    signal: string;
    strength: string;
    score: number;
    reasons: string[];
    timestamp: string;
    current_price?: number;
    breakdown?: { volume?: { score: number }; technical?: { score: number }; pattern?: { score: number } };
    stock_info?: { name?: string; price?: number; change_rate?: number };
}

export interface BacktestRequest {
    symbols: string[];
    market: string;
    days: number;
    initial_capital: number;
    entry_strategy: string;
    min_entry_score: number;
    stop_loss_ratio: number;
    max_holding_days: number;
}

export interface BacktestSummary {
    roi: number;
    total_trades: number;
    win_rate: number;
    max_drawdown: number;
    initial_capital: number;
    final_capital: number;
    net_profit: number;
    winning_trades: number;
    losing_trades: number;
    sharpe_ratio?: number;
    avg_win?: number;
    avg_loss?: number;
    average_profit_per_trade?: number;
}

export interface BacktestAdvancedMetrics {
    sortino_ratio?: number;
    calmar_ratio?: number;
    profit_factor?: number;
    expectancy?: number;
}

export interface BacktestTrade {
    symbol?: string;
    code?: string;
    entry_date?: string;
    entry_time?: string;
    exit_date?: string;
    exit_time?: string;
    entry_price: number;
    exit_price: number;
    profit_loss_pct: number;
    profit_loss: number;
}

export interface BacktestResult {
    summary: BacktestSummary;
    advanced_metrics?: BacktestAdvancedMetrics;
    trade_analysis?: Record<string, unknown>;
    trades?: BacktestTrade[];
    portfolio_history?: Record<string, unknown>[];
    best_trade?: Record<string, unknown>;
    worst_trade?: Record<string, unknown>;
    monthly_returns?: Record<string, unknown>[];
    config?: Record<string, unknown>;
}

export interface OptimizeRequest {
    symbols: string[];
    market: string;
    days: number;
    optimization_metric: string;
}

export interface OptimizeBestParams {
    stop_loss_ratio: number;
    take_profit_ratio: number;
    max_holding_days: number;
    min_entry_score: number;
    position_size_pct: number;
}

export interface OptimizeBestPerformance {
    roi: number;
    sharpe_ratio: number;
    win_rate: number;
    total_trades: number;
    mdd: number;
}

export interface OptimizeTopResult {
    params: OptimizeBestParams;
    performance: { roi: number; [key: string]: unknown };
}

export interface OptimizeResult {
    status: string;
    optimization_id?: string;
    optimization_metric?: string;
    execution_time_seconds?: number;
    total_combinations_tested?: number;
    best_params?: OptimizeBestParams;
    best_performance?: OptimizeBestPerformance;
    top_5_results?: OptimizeTopResult[];
    parameter_analysis?: Record<string, unknown>;
    full_results?: Record<string, unknown>[];
    message?: string;
}

// ── Paper Trading Types ────────────────────────────────────────

export interface PaperStartConfig {
    initial_capital: number;
    market: string;
    strategy: string;
    min_score: number;
    max_positions: number;
    position_size_pct: number;
}

export interface PaperStatus {
    is_running: boolean;
    started_at?: string | null;
    elapsed_seconds: number;
    total_value: number;
    cash: number;
    roi: number;
    open_count: number;
    closed_today: number;
    initial_capital: number;
    max_positions: number;
}

export interface PaperPosition {
    id?: number | null;
    code: string;
    name: string;
    entry_price: number;
    quantity: number;
    entry_score: number;
    holding_hours: number;
    unrealized_pnl: number | null;
    unrealized_pnl_pct: number | null;
}

export interface PaperTrade {
    id: number;
    code: string;
    name: string;
    profit_loss_pct: number;
    profit_loss: number;
    exit_reason: string | null;
    exit_time: string | null;
}

export interface PaperHistoryPoint {
    recorded_at: string;
    total_value: number;
}

// ── Helpers ───────────────────────────────────────────────────

async function get<T>(path: string): Promise<T> {
    const res = await fetch(`${BASE_URL}${path}`);
    if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
    return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${BASE_URL}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
    return res.json();
}

// ── Stocks ────────────────────────────────────────────────────

export const fetchSurgeStocks = (market: Market): Promise<SurgeStock[]> =>
    get(`/stocks/surge?market=${market}`);

export const fetchStockScore = (code: string, market: Market): Promise<StockScore> =>
    get(`/stocks/${code}/score?market=${market}`);

export const fetchDailyChart = (code: string, market: Market): Promise<OHLCV[]> =>
    get(`/stocks/${code}/daily?market=${market}`);

export const fetchWeeklyChart = (code: string, market: Market): Promise<OHLCV[]> =>
    get(`/stocks/${code}/weekly?market=${market}`);

export const fetchMinuteChart = (code: string, market: Market): Promise<OHLCV[]> =>
    get(`/stocks/${code}/minute?market=${market}`);

// ── Signals ───────────────────────────────────────────────────

export const scanSignals = (
    market: Market,
    strategy = 'combined',
    minScore = 60,
): Promise<EntrySignal[]> =>
    get(`/signals/scan?market=${market}&strategy=${strategy}&min_score=${minScore}`);

// ── Backtest ──────────────────────────────────────────────────

export const runBacktest = (req: BacktestRequest): Promise<BacktestResult> =>
    post('/backtest/run', req);

// ── Optimize ──────────────────────────────────────────────────

export const runQuickOptimize = (req: OptimizeRequest): Promise<OptimizeResult> =>
    post('/optimize/quick', req);

// ── Paper Trading ─────────────────────────────────────────────

export const paperTrading = {
    getStatus: (): Promise<PaperStatus> =>
        get('/paper/status'),
    getPositions: (): Promise<PaperPosition[]> =>
        get('/paper/positions'),
    getTrades: (limit = 30): Promise<PaperTrade[]> =>
        get(`/paper/trades?limit=${limit}`),
    getHistory: (limit = 200): Promise<PaperHistoryPoint[]> =>
        get(`/paper/history?limit=${limit}`),
    start: (config: PaperStartConfig): Promise<unknown> =>
        post('/paper/start', config),
    stop: (): Promise<unknown> =>
        post('/paper/stop', {}),
    reset: (): Promise<unknown> =>
        post('/paper/reset', {}),
};
