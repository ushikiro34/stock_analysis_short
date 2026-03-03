import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import CandleChart from '../components/CandleChart';
import ScoreCard from '../components/ScoreCard';
import RiskCard from '../components/RiskCard';
import SurgeList from '../components/SurgeList';
import { Loader2, TrendingUp, TrendingDown } from 'lucide-react';
import { fetchStockScore, fetchDailyChart, fetchWeeklyChart, fetchMinuteChart, fetchSurgeStocks, type StockScore, type SurgeStock, type Market } from '../lib/api';
import type { StockFilter } from '../App';

type ChartMode = 'daily' | 'weekly' | 'minute';

interface StocksDashboardProps {
    market: Market;
    filter: StockFilter;
}

export default function StocksDashboard({ market, filter }: StocksDashboardProps) {
    const [stockCode, setStockCode] = useState<string | null>(null);
    const [candles, setCandles] = useState<any[]>([]);
    const [score, setScore] = useState<StockScore | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [chartMode, setChartMode] = useState<ChartMode>('daily');

    // Surge stocks state
    const [surgeStocks, setSurgeStocks] = useState<SurgeStock[]>([]);
    const [surgeLoading, setSurgeLoading] = useState(true);

    // Apply filters to surge stocks
    const filteredStocks = useMemo(() => {
        let filtered = [...surgeStocks];

        // Price filter
        if (filter.priceFilter === 'penny') {
            filtered = filtered.filter(s => s.price < 1);
        } else if (filter.priceFilter === 'range') {
            if (filter.priceFrom !== undefined) {
                filtered = filtered.filter(s => s.price >= filter.priceFrom!);
            }
            if (filter.priceTo !== undefined) {
                filtered = filtered.filter(s => s.price <= filter.priceTo!);
            }
        }

        // Stock name filter
        if (filter.stockName.trim()) {
            const searchTerm = filter.stockName.toLowerCase();
            filtered = filtered.filter(s =>
                s.code.toLowerCase().includes(searchTerm) ||
                s.name.toLowerCase().includes(searchTerm)
            );
        }

        return filtered;
    }, [surgeStocks, filter]);

    // Current surge stock info
    const surgeInfo = filteredStocks.find(s => s.code === stockCode);
    const stockName = surgeInfo?.name ?? stockCode ?? '';

    // Load surge stocks + poll every 30s
    useEffect(() => {
        setSurgeStocks([]);
        setStockCode(null);
        setCandles([]);
        setScore(null);
        setError(null);
        setSurgeLoading(true);
        setChartMode('daily');

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

    // Auto-select first filtered stock
    useEffect(() => {
        if (filteredStocks.length > 0 && (!stockCode || !filteredStocks.find(s => s.code === stockCode))) {
            setStockCode(filteredStocks[0].code);
        }
    }, [filteredStocks, stockCode]);

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
                    return {
                        time: Math.floor(new Date(c.time).getTime() / 1000),
                        open: c.open,
                        high: c.high,
                        low: c.low,
                        close: c.close,
                    };
                }
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

    // Build warnings from score
    const warnings: string[] = [];
    if (score) {
        if (Number(score.risk_penalty) > 0) warnings.push(`리스크 감점: -${score.risk_penalty}점`);
        if (Number(score.stability_score) < 10) warnings.push('안정성 점수 낮음');
        if (Number(score.total_score) < 50) warnings.push('총점 50점 미만 — 주의 필요');
        if (score.fundamental?.net_loss) warnings.push('당기순손실 (EPS < 0)');
        if (score.fundamental?.high_debt) warnings.push('고부채 비율');
        if (score.technical?.rsi !== undefined) {
            if (score.technical.rsi > 70) warnings.push(`RSI ${score.technical.rsi.toFixed(0)} — 과매수`);
            if (score.technical.rsi < 30) warnings.push(`RSI ${score.technical.rsi.toFixed(0)} — 과매도`);
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
        <div className="h-full grid grid-cols-[280px_1fr_320px] gap-4">
            {/* LEFT PANEL: Surge Stock List */}
            <aside className="overflow-y-auto">
                <SurgeList
                    stocks={filteredStocks}
                    selectedCode={stockCode}
                    onSelect={handleSelectStock}
                    loading={surgeLoading}
                    market={market}
                />
                {!surgeLoading && filteredStocks.length === 0 && surgeStocks.length > 0 && (
                    <div className="mt-4 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-sm text-yellow-300">
                        필터 조건에 맞는 종목이 없습니다
                    </div>
                )}
            </aside>

            {/* CENTER PANEL: Stock Info + Chart */}
            <main className="flex flex-col overflow-hidden">
                {!stockCode && !loading && (
                    <div className="flex items-center justify-center h-full text-slate-500">
                        <p className="text-lg">좌측에서 종목을 선택하세요</p>
                    </div>
                )}

                {loading && (
                    <div className="flex items-center justify-center h-full">
                        <Loader2 className="animate-spin text-primary mr-3" size={28} />
                        <span className="text-slate-400">로딩 중...</span>
                    </div>
                )}

                {error && !loading && (
                    <div className="flex items-center justify-center h-full text-red-400">
                        <p>{error}</p>
                    </div>
                )}

                {stockCode && !loading && !error && (
                    <>
                        {/* Stock Header */}
                        <div className="bg-surface rounded-xl border border-slate-700 p-4 mb-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <h2 className="text-2xl font-bold mb-1">{stockName}</h2>
                                    <p className="text-sm text-slate-400">{stockCode}</p>
                                </div>
                                {surgeInfo && (
                                    <div className="text-right">
                                        <div className="text-3xl font-mono font-bold mb-1">
                                            {market === 'US' ? '$' : ''}{surgeInfo.price.toLocaleString()}{market === 'KR' ? '원' : ''}
                                        </div>
                                        <div className={`flex items-center justify-end gap-1 text-sm font-mono ${
                                            surgeInfo.change_rate > 0 ? 'text-red-400' : 'text-blue-400'
                                        }`}>
                                            {surgeInfo.change_rate > 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                                            <span>
                                                {surgeInfo.change_rate > 0 ? '+' : ''}{market === 'US' ? '$' : ''}
                                                {surgeInfo.change_price.toLocaleString()}{market === 'KR' ? '원' : ''}
                                            </span>
                                            <span>
                                                ({surgeInfo.change_rate > 0 ? '+' : ''}{surgeInfo.change_rate.toFixed(2)}%)
                                            </span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Chart Mode Toggle */}
                        <div className="flex gap-2 mb-3">
                            <button
                                onClick={() => setChartMode('daily')}
                                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                                    chartMode === 'daily'
                                        ? 'bg-primary text-white'
                                        : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                                }`}
                            >
                                일봉
                            </button>
                            <button
                                onClick={() => setChartMode('weekly')}
                                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                                    chartMode === 'weekly'
                                        ? 'bg-primary text-white'
                                        : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                                }`}
                            >
                                주봉
                            </button>
                            <button
                                onClick={() => setChartMode('minute')}
                                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                                    chartMode === 'minute'
                                        ? 'bg-primary text-white'
                                        : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                                }`}
                            >
                                분봉
                            </button>
                        </div>

                        {/* Chart - Reduced Size */}
                        <div className="flex-1 min-h-0">
                            {candles.length > 0 ? (
                                <CandleChart data={candles} />
                            ) : (
                                <div className="bg-surface rounded-xl border border-slate-700 h-full flex items-center justify-center text-slate-500">
                                    차트 데이터 없음
                                </div>
                            )}
                        </div>
                    </>
                )}
            </main>

            {/* RIGHT PANEL: Info Cards */}
            <aside className="overflow-y-auto space-y-3">
                {stockCode && !loading && !error && (
                    <>
                        {/* Score Card */}
                        <div className="bg-surface rounded-xl border border-slate-700 p-4">
                            <h3 className="text-sm font-bold text-slate-300 mb-3">종합 점수</h3>
                            <div className="text-center mb-4">
                                <div className="text-4xl font-bold text-primary mb-1">
                                    {scoreProps.total.toFixed(0)}
                                </div>
                                <div className="text-xs text-slate-400">/ 100점</div>
                            </div>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between items-center">
                                    <span className="text-slate-400">가치</span>
                                    <div className="flex items-center gap-2">
                                        <div className="w-20 h-2 bg-slate-800 rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-green-500"
                                                style={{ width: `${(scoreProps.value / 40) * 100}%` }}
                                            />
                                        </div>
                                        <span className="font-mono text-slate-300 w-8 text-right">
                                            {scoreProps.value.toFixed(0)}
                                        </span>
                                    </div>
                                </div>
                                <div className="flex justify-between items-center">
                                    <span className="text-slate-400">추세</span>
                                    <div className="flex items-center gap-2">
                                        <div className="w-20 h-2 bg-slate-800 rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-blue-500"
                                                style={{ width: `${(scoreProps.trend / 30) * 100}%` }}
                                            />
                                        </div>
                                        <span className="font-mono text-slate-300 w-8 text-right">
                                            {scoreProps.trend.toFixed(0)}
                                        </span>
                                    </div>
                                </div>
                                <div className="flex justify-between items-center">
                                    <span className="text-slate-400">안정성</span>
                                    <div className="flex items-center gap-2">
                                        <div className="w-20 h-2 bg-slate-800 rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-purple-500"
                                                style={{ width: `${(scoreProps.stability / 20) * 100}%` }}
                                            />
                                        </div>
                                        <span className="font-mono text-slate-300 w-8 text-right">
                                            {scoreProps.stability.toFixed(0)}
                                        </span>
                                    </div>
                                </div>
                                {scoreProps.risk > 0 && (
                                    <div className="flex justify-between items-center pt-2 border-t border-slate-700">
                                        <span className="text-red-400">리스크 감점</span>
                                        <span className="font-mono text-red-400">-{scoreProps.risk.toFixed(0)}</span>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Risk Warnings */}
                        {warnings.length > 0 && (
                            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
                                <h3 className="text-sm font-bold text-red-400 mb-2">⚠️ 리스크 경고</h3>
                                <ul className="space-y-1">
                                    {warnings.map((warning, idx) => (
                                        <li key={idx} className="text-xs text-red-300 flex items-start gap-1">
                                            <span className="text-red-400 mt-0.5">•</span>
                                            <span>{warning}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {/* Fundamental Data */}
                        <div className="bg-surface rounded-xl border border-slate-700 p-4">
                            <h3 className="text-sm font-bold text-slate-300 mb-3">📊 펀더멘털</h3>
                            {fundamental ? (
                                <div className="space-y-2 text-sm">
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">PER</span>
                                        <span className={`font-mono ${
                                            fundamental.per < 20 ? 'text-green-400' :
                                            fundamental.per > 50 ? 'text-red-400' : 'text-slate-300'
                                        }`}>
                                            {fundamental.per.toFixed(1)}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">PBR</span>
                                        <span className={`font-mono ${
                                            fundamental.pbr < 1.5 ? 'text-green-400' : 'text-slate-300'
                                        }`}>
                                            {fundamental.pbr.toFixed(2)}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">ROE</span>
                                        <span className={`font-mono ${
                                            fundamental.roe > 10 ? 'text-green-400' : 'text-slate-300'
                                        }`}>
                                            {fundamental.roe.toFixed(1)}%
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">EPS</span>
                                        <span className={`font-mono ${
                                            fundamental.eps > 0 ? 'text-slate-300' : 'text-red-400'
                                        }`}>
                                            {market === 'US' ? '$' : ''}{fundamental.eps.toLocaleString()}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">BPS</span>
                                        <span className="font-mono text-slate-300">
                                            {market === 'US' ? '$' : ''}{fundamental.bps.toLocaleString()}
                                        </span>
                                    </div>
                                </div>
                            ) : (
                                <p className="text-slate-500 text-xs">데이터 없음</p>
                            )}
                        </div>

                        {/* Technical Indicators */}
                        <div className="bg-surface rounded-xl border border-slate-700 p-4">
                            <h3 className="text-sm font-bold text-slate-300 mb-3">📈 기술적 지표</h3>
                            {technical ? (
                                <div className="space-y-2 text-sm">
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">RSI(14)</span>
                                        <span className={`font-mono ${
                                            technical.rsi > 70 ? 'text-red-400' :
                                            technical.rsi < 30 ? 'text-blue-400' : 'text-slate-300'
                                        }`}>
                                            {technical.rsi.toFixed(1)}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">MA20</span>
                                        <span className="font-mono text-slate-300">
                                            {technical.ma20?.toLocaleString() ?? '-'}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">MA60</span>
                                        <span className="font-mono text-slate-300">
                                            {technical.ma60?.toLocaleString() ?? '-'}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">변동성</span>
                                        <span className="font-mono text-slate-300">
                                            {(technical.volatility * 100).toFixed(2)}%
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">60일 수익률</span>
                                        <span className={`font-mono ${
                                            technical.return_60d > 0 ? 'text-red-400' : 'text-blue-400'
                                        }`}>
                                            {technical.return_60d > 0 ? '+' : ''}{technical.return_60d.toFixed(1)}%
                                        </span>
                                    </div>
                                </div>
                            ) : (
                                <p className="text-slate-500 text-xs">데이터 없음</p>
                            )}
                        </div>
                    </>
                )}
            </aside>
        </div>
    );
}
