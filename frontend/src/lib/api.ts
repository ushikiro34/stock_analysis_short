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

export interface StockAnalysis {
    code: string;
    name: string;
    market: string;
    current_price: number;
    open: number;
    high: number;
    low: number;
    change_pct: number;
    volume: number;
    vol_ma20: number;
    vol_ratio: number;
    ma5: number;
    ma20: number;
    ma60: number;
    ma120: number;
    vs_ma5_pct: number;
    vs_ma20_pct: number;
    vs_ma60_pct: number;
    high52w: number;
    low52w: number;
    high20d: number;
    is_52w_high: boolean;
    is_20d_high: boolean;
    signal: string;
    score: number;
    chase_blocked: boolean;
    signal_reasons: string[];
    updated_at: string;
    error?: string;
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
    cup_handle_confirmed?: boolean;
    cup_handle?: { score: number; reasons: string[]; cup_depth_pct?: number; handle_days?: number; breakout_status?: string };
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
    market: string;
    entry_time: string | null;
    entry_price: number;
    exit_time: string | null;
    exit_price: number | null;
    exit_reason: string | null;
    quantity: number;
    profit_loss: number;
    profit_loss_pct: number;
}

export interface PaperHistoryPoint {
    recorded_at: string;
    total_value: number;
}

export interface JournalResponse {
    trades: PaperTrade[];
    total: number;
    total_pnl: number;
    profit_count: number;
    profit_amount: number;
    loss_count: number;
    loss_amount: number;
}

export interface JournalFilter {
    date_from?: string;
    date_to?: string;
    code?: string;
    profit_type: 'all' | 'profit' | 'loss';
}

// ── Helpers ───────────────────────────────────────────────────

function extractDetail(text: string, fallback: string): string {
    try { return JSON.parse(text)?.detail ?? fallback; } catch { return fallback; }
}

async function get<T>(path: string): Promise<T> {
    const res = await fetch(`${BASE_URL}${path}`);
    if (!res.ok) {
        const text = await res.text();
        throw new Error(extractDetail(text, `HTTP ${res.status}`));
    }
    return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${BASE_URL}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        const text = await res.text();
        throw new Error(extractDetail(text, `HTTP ${res.status}`));
    }
    return res.json();
}

// ── Stocks ────────────────────────────────────────────────────

export const fetchSurgeStocks = (market: Market): Promise<SurgeStock[]> =>
    get(`/stocks/surge?market=${market}`);

export const fetchStockScore = (code: string, market: Market): Promise<StockScore> =>
    get(`/stocks/${code}/score?market=${market}`);

export const fetchStockAnalyze = (code: string, market: Market): Promise<StockAnalysis> =>
    get(`/stocks/${code}/analyze?market=${market}`);

export const fetchDailyChart = (code: string, market: Market): Promise<OHLCV[]> =>
    get(`/stocks/${code}/daily?market=${market}`);

export const fetchWeeklyChart = (code: string, market: Market): Promise<OHLCV[]> =>
    get(`/stocks/${code}/weekly?market=${market}`);

export const fetchMinuteChart = (code: string, market: Market): Promise<OHLCV[]> =>
    get(`/stocks/${code}/minute?market=${market}`);

// ── Signals ───────────────────────────────────────────────────

export const fetchEntrySignal = (code: string, market: Market, strategy = 'pattern'): Promise<EntrySignal> =>
    get(`/signals/entry/${code}?market=${market}&strategy=${strategy}`);

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

// ── Monitor ───────────────────────────────────────────────────

export interface LogEntry {
    ts: string;
    level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
    logger: string;
    msg: string;
}

export interface MonitorStatus {
    uptime_seconds: number;
    tasks: {
        collector: string;
        scorer: string;
        paper: string;
    };
}

export const monitor = {
    getStatus: (): Promise<MonitorStatus> =>
        get('/monitor/status'),
    getLogs: (level = 'DEBUG', limit = 200): Promise<LogEntry[]> =>
        get(`/monitor/logs?level=${level}&limit=${limit}`),
    clearLogs: (): Promise<{ cleared: boolean }> =>
        fetch(`${BASE_URL}/monitor/logs`, { method: 'DELETE' }).then(r => r.json()),
};

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
    closeAllPositions: (): Promise<unknown> =>
        post('/paper/positions/close-all', {}),
    closePosition: (code: string): Promise<unknown> =>
        post(`/paper/positions/${code}/close`, {}),
    addPosition: (data: { code: string; name?: string; entry_price: number; quantity?: number }): Promise<unknown> =>
        post('/paper/positions', data),
    getJournal: (filter: JournalFilter, limit = 200, offset = 0): Promise<JournalResponse> => {
        const p = new URLSearchParams();
        if (filter.date_from) p.set('date_from', filter.date_from);
        if (filter.date_to) p.set('date_to', filter.date_to);
        if (filter.code) p.set('code', filter.code);
        p.set('profit_type', filter.profit_type);
        p.set('limit', String(limit));
        p.set('offset', String(offset));
        return get(`/paper/journal?${p.toString()}`);
    },
};
