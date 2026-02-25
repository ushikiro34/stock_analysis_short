import { useState, useEffect, useCallback, useRef } from 'react';
import CandleChart from './components/CandleChart';
import ScoreCard from './components/ScoreCard';
import RiskCard from './components/RiskCard';
import SurgeList from './components/SurgeList';
import { Loader2 } from 'lucide-react';
import { fetchStockScore, fetchDailyChart, fetchWeeklyChart, fetchMinuteChart, fetchSurgeStocks, type StockScore, type SurgeStock, type Market } from './lib/api';

type ChartMode = 'daily' | 'weekly' | 'minute';

function App() {
    const [market, setMarket] = useState<Market>('KR');
    const [stockCode, setStockCode] = useState<string | null>(null);
    const [candles, setCandles] = useState<any[]>([]);
    const [score, setScore] = useState<StockScore | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [chartMode, setChartMode] = useState<ChartMode>('daily');

    // Surge stocks state
    const [surgeStocks, setSurgeStocks] = useState<SurgeStock[]>([]);
    const [surgeLoading, setSurgeLoading] = useState(true);

    // Current surge stock info
    const surgeInfo = surgeStocks.find(s => s.code === stockCode);
    const stockName = surgeInfo?.name ?? stockCode ?? '';

    // Handle market switch
    const handleMarketChange = useCallback((m: Market) => {
        setMarket(m);
        setStockCode(null);
        setSurgeStocks([]);
        setCandles([]);
        setScore(null);
        setError(null);
        setSurgeLoading(true);
        setChartMode('daily');
    }, []);

    // Load surge stocks + poll every 30s
    useEffect(() => {
        const loadSurge = async () => {
            try {
                const data = await fetchSurgeStocks(market);
                setSurgeStocks(data);
            } catch { /* ignore */ }
            finally { setSurgeLoading(false); }
        };
        loadSurge();
        const interval = setInterval(loadSurge, 30_000);
        return () => clearInterval(interval);
    }, [market]);

    // Auto-select first surge stock
    useEffect(() => {
        if (surgeStocks.length > 0 && (!stockCode || !surgeStocks.find(s => s.code === stockCode))) {
            setStockCode(surgeStocks[0].code);
        }
    }, [surgeStocks]);

    // Reset to daily chart when stock changes
    const handleSelectStock = useCallback((code: string) => {
        setChartMode('daily');
        setStockCode(code);
    }, []);

    // Load chart and score for selected stock
    const chartModeRef = useRef(chartMode);
    chartModeRef.current = chartMode;
    const marketRef = useRef(market);
    marketRef.current = market;

    const loadStockData = useCallback(async (code: string, isPolling = false, mode?: ChartMode) => {
        const currentMode = mode ?? chartModeRef.current;
        const currentMarket = marketRef.current;
        if (!isPolling) {
            setLoading(true);
            setError(null);
        }
        try {
            const fetchChart = currentMode === 'minute' ? fetchMinuteChart : currentMode === 'weekly' ? fetchWeeklyChart : fetchDailyChart;
            const [chartData, scoreData] = await Promise.all([
                fetchChart(code, currentMarket),
                fetchStockScore(code, currentMarket),
            ]);

            const chartFormatted = chartData.map((c) => {
                if (currentMode === 'minute') {
                    // 분봉: ISO string → Unix timestamp
                    return {
                        time: Math.floor(new Date(c.time).getTime() / 1000),
                        open: c.open,
                        high: c.high,
                        low: c.low,
                        close: c.close,
                    };
                }
                // 일봉: "YYYY-MM-DD" string
                return {
                    time: c.time,
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close,
                };
            });
            setCandles(chartFormatted);
            setScore(scoreData);
        } catch (err: any) {
            if (!isPolling) setError(err?.message ?? '데이터를 불러오지 못했습니다.');
        } finally {
            if (!isPolling) setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (stockCode) loadStockData(stockCode, false, chartMode);
    }, [stockCode, chartMode, loadStockData]);

    // 10s auto-refresh for chart
    const stockCodeRef = useRef(stockCode);
    stockCodeRef.current = stockCode;
    useEffect(() => {
        const interval = setInterval(() => {
            if (stockCodeRef.current) loadStockData(stockCodeRef.current, true);
        }, 10_000);
        return () => clearInterval(interval);
    }, [loadStockData]);

    // Build warnings from score + fundamental/technical
    const warnings: string[] = [];
    if (score) {
        if (Number(score.risk_penalty) > 0) warnings.push(`리스크 감점: -${score.risk_penalty}점`);
        if (Number(score.stability_score) < 10) warnings.push('안정성 점수 낮음');
        if (Number(score.total_score) < 50) warnings.push('총점 50점 미만 — 주의 필요');
        if (score.fundamental?.net_loss) warnings.push('당기순손실 (EPS < 0)');
        if (score.fundamental?.high_debt) warnings.push('고부채 비율');
        if (score.technical?.rsi !== undefined) {
            if (score.technical.rsi > 70) warnings.push(`RSI ${score.technical.rsi.toFixed(0)} — 과매수 구간`);
            if (score.technical.rsi < 30) warnings.push(`RSI ${score.technical.rsi.toFixed(0)} — 과매도 구간`);
        }
    }

    const scoreProps = score ? {
        total: Number(score.total_score ?? 0),
        value: Number(score.value_score ?? 0),
        trend: Number(score.trend_score ?? 0),
        stability: Number(score.stability_score ?? 0),
        risk: Number(score.risk_penalty ?? 0),
    } : { total: 0, value: 0, trend: 0, stability: 0, risk: 0 };

    const fundamental = score?.fundamental;
    const technical = score?.technical;

    return (
        <div className="h-screen flex overflow-hidden">
            {/* Left Panel: Surge List */}
            <aside className="w-80 shrink-0 border-r border-slate-700 p-4 overflow-y-auto">
                {/* Market Toggle */}
                <div className="flex gap-1 mb-4 bg-slate-800 rounded-lg p-1">
                    <button
                        onClick={() => handleMarketChange('KR')}
                        className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                            market === 'KR' ? 'bg-primary text-white' : 'text-slate-400 hover:text-slate-200'
                        }`}
                    >
                        한국
                    </button>
                    <button
                        onClick={() => handleMarketChange('US')}
                        className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                            market === 'US' ? 'bg-primary text-white' : 'text-slate-400 hover:text-slate-200'
                        }`}
                    >
                        미국
                    </button>
                </div>

                <SurgeList
                    stocks={surgeStocks}
                    selectedCode={stockCode}
                    onSelect={handleSelectStock}
                    loading={surgeLoading}
                    market={market}
                />
            </aside>

            {/* Right Panel: Detail View */}
            <main className="flex-1 p-8 overflow-y-auto">
                {/* Header */}
                {stockCode && (
                    <header className="flex items-center justify-between mb-8">
                        <div>
                            <h1 className="text-3xl font-bold">{stockName}</h1>
                            <p className="text-slate-500">{stockCode}</p>
                        </div>
                        {surgeInfo && (
                            <div className="text-right">
                                <div className="text-2xl font-mono font-bold">
                                    {market === 'US' ? '$' : ''}{surgeInfo.price.toLocaleString()}{market === 'KR' ? '원' : ''}
                                </div>
                                <div className={`text-sm font-mono ${surgeInfo.change_rate > 0 ? 'text-danger' : 'text-blue-400'}`}>
                                    {surgeInfo.change_rate > 0 ? '+' : ''}{market === 'US' ? '$' : ''}{surgeInfo.change_price.toLocaleString()}{market === 'KR' ? '원' : ''} ({surgeInfo.change_rate > 0 ? '+' : ''}{surgeInfo.change_rate.toFixed(2)}%)
                                </div>
                            </div>
                        )}
                    </header>
                )}

                {/* Loading */}
                {loading && (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 className="animate-spin text-primary mr-3" size={28} />
                        <span className="text-slate-400 text-lg">데이터 로딩 중...</span>
                    </div>
                )}

                {error && !loading && (
                    <div className="text-center py-16 text-slate-500">
                        <p className="text-lg mb-2">{error}</p>
                    </div>
                )}

                {!stockCode && !loading && (
                    <div className="text-center py-20 text-slate-500">
                        <p className="text-lg">좌측 급등주 리스트에서 종목을 선택하세요.</p>
                    </div>
                )}

                {/* Main Content */}
                {stockCode && !loading && !error && (
                    <div className="space-y-6">
                        {/* Chart mode toggle */}
                        <div className="flex gap-2">
                            <button
                                onClick={() => setChartMode('daily')}
                                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                                    chartMode === 'daily'
                                        ? 'bg-primary text-white'
                                        : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                                }`}
                            >
                                일봉
                            </button>
                            <button
                                onClick={() => setChartMode('weekly')}
                                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                                    chartMode === 'weekly'
                                        ? 'bg-primary text-white'
                                        : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                                }`}
                            >
                                주봉
                            </button>
                            <button
                                onClick={() => setChartMode('minute')}
                                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                                    chartMode === 'minute'
                                        ? 'bg-primary text-white'
                                        : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                                }`}
                            >
                                분봉
                            </button>
                        </div>

                        {/* Chart - full width */}
                        {candles.length > 0 ? (
                            <CandleChart data={candles} />
                        ) : (
                            <div className="bg-surface p-12 rounded-xl border border-slate-700 text-center text-slate-500">
                                차트 데이터가 없습니다.
                            </div>
                        )}

                        {/* Info cards row */}
                        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                            <ScoreCard {...scoreProps} />
                            <RiskCard warnings={warnings} />

                            {/* 펀더멘털 */}
                            <div className="bg-surface p-5 rounded-xl border border-slate-700">
                                <h3 className="text-sm font-bold text-slate-300 mb-3">펀더멘털</h3>
                                {fundamental ? (
                                    <div className="space-y-2 text-sm">
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">PER</span>
                                            <span className={`font-mono ${fundamental.per < 20 ? 'text-green-400' : fundamental.per > 50 ? 'text-red-400' : 'text-slate-300'}`}>
                                                {fundamental.per.toFixed(1)}
                                            </span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">PBR</span>
                                            <span className={`font-mono ${fundamental.pbr < 1.5 ? 'text-green-400' : 'text-slate-300'}`}>
                                                {fundamental.pbr.toFixed(2)}
                                            </span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">ROE</span>
                                            <span className={`font-mono ${fundamental.roe > 10 ? 'text-green-400' : 'text-slate-300'}`}>
                                                {fundamental.roe.toFixed(1)}%
                                            </span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">EPS</span>
                                            <span className={`font-mono ${fundamental.eps > 0 ? 'text-slate-300' : 'text-red-400'}`}>
                                                {market === 'US' ? '$' : ''}{fundamental.eps.toLocaleString()}
                                            </span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">BPS</span>
                                            <span className="font-mono text-slate-300">
                                                {market === 'US' ? '$' : ''}{fundamental.bps.toLocaleString()}
                                            </span>
                                        </div>
                                    </div>
                                ) : (
                                    <p className="text-slate-600 text-xs">데이터 없음</p>
                                )}
                            </div>

                            {/* 기술적 지표 */}
                            <div className="bg-surface p-5 rounded-xl border border-slate-700">
                                <h3 className="text-sm font-bold text-slate-300 mb-3">기술적 지표</h3>
                                {technical ? (
                                    <div className="space-y-2 text-sm">
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">RSI(14)</span>
                                            <span className={`font-mono ${technical.rsi > 70 ? 'text-red-400' : technical.rsi < 30 ? 'text-blue-400' : 'text-slate-300'}`}>
                                                {technical.rsi.toFixed(1)}
                                            </span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">MA20</span>
                                            <span className="font-mono text-slate-300">{technical.ma20?.toLocaleString() ?? '-'}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">MA60</span>
                                            <span className="font-mono text-slate-300">{technical.ma60?.toLocaleString() ?? '-'}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">변동성</span>
                                            <span className="font-mono text-slate-300">{(technical.volatility * 100).toFixed(2)}%</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">60일 수익률</span>
                                            <span className={`font-mono ${technical.return_60d > 0 ? 'text-danger' : 'text-blue-400'}`}>
                                                {technical.return_60d > 0 ? '+' : ''}{technical.return_60d.toFixed(1)}%
                                            </span>
                                        </div>
                                    </div>
                                ) : (
                                    <p className="text-slate-600 text-xs">데이터 없음</p>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                <footer className="mt-12 text-center text-slate-600 text-sm">
                    <p>&copy; 2026 Personal Stock Analysis System. Not financial advice.</p>
                </footer>
            </main>
        </div>
    );
}

export default App;
