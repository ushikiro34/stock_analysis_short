import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import CandleChart from '../components/CandleChart';
import ScoreCard from '../components/ScoreCard';
import RiskCard from '../components/RiskCard';
import SurgeList from '../components/SurgeList';
import { Loader2, TrendingUp, TrendingDown, Star } from 'lucide-react';
import { fetchStockScore, fetchDailyChart, fetchWeeklyChart, fetchMinuteChart, fetchSurgeStocks, fetchEntrySignal, fetchStockAnalyze, scanPullback, type StockScore, type StockAnalysis, type SurgeStock, type Market, type EntrySignal, type PullbackCandidate } from '../lib/api';
import type { StockFilter } from '../App';

// WatchlistDashboard 와 동일한 키/구조 사용 → 두 탭 간 관심종목 동기화
const WATCHLIST_KEY = 'watchlist_v1';

interface WatchItem {
    code: string;
    market: Market;
    addedAt: string;
    name?: string;   // 종목명 (선택)
}

function loadWatchlist(): WatchItem[] {
    try { return JSON.parse(localStorage.getItem(WATCHLIST_KEY) ?? '[]'); }
    catch { return []; }
}
function saveWatchlist(list: WatchItem[]) {
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(list));
}

type ChartMode = 'daily' | 'weekly' | 'minute';

interface StocksDashboardProps {
    market: Market;
    filter: StockFilter;
    focusCode?: string;
    onFocusDone?: () => void;
}

export default function StocksDashboard({ market, filter, focusCode, onFocusDone }: StocksDashboardProps) {
    const [stockCode, setStockCode] = useState<string | null>(null);
    const isManualSelectionRef = useRef(false);
    const loadIdRef = useRef(0); // stale 요청 무시용
    const [candles, setCandles] = useState<any[]>([]);
    const [score, setScore] = useState<StockScore | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [chartMode, setChartMode] = useState<ChartMode>('daily');
    const [cupHandle, setCupHandle] = useState<EntrySignal['cup_handle'] | null | undefined>(undefined);
    const [cupHandleLoading, setCupHandleLoading] = useState(false);
    const [stockAnalysis, setStockAnalysis] = useState<StockAnalysis | null>(null);

    // Surge stocks state
    const [surgeStocks, setSurgeStocks] = useState<SurgeStock[]>([]);
    const [surgeLoading, setSurgeLoading] = useState(true);
    const [scoreMap, setScoreMap] = useState<Record<string, number>>({});
    const [chMap, setChMap] = useState<Record<string, string>>({});

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

        // 종합점수 내림차순 정렬 (점수 없는 종목은 뒤로)
        filtered.sort((a, b) => (scoreMap[b.code] ?? -1) - (scoreMap[a.code] ?? -1));

        return filtered;
    }, [surgeStocks, filter, scoreMap]);

    // Current surge stock info
    const surgeInfo = filteredStocks.find(s => s.code === stockCode);
    const stockName = surgeInfo?.name ?? stockCode ?? '';

    // Left panel tab: 급등주 vs 눌림목
    const [leftTab, setLeftTab] = useState<'surge' | 'pullback'>('surge');
    const [pullbackCandidates, setPullbackCandidates] = useState<PullbackCandidate[]>([]);
    const [pullbackLoading, setPullbackLoading] = useState(false);

    // Watchlist (localStorage) — WatchlistDashboard 와 동일 키/구조
    const [watchlist, setWatchlist] = useState<WatchItem[]>(loadWatchlist);
    const [watchlistAdded, setWatchlistAdded] = useState(false);
    const isWatchlisted = watchlist.some(w => w.code === stockCode);

    // Track B: 눌림목 스캔
    const runPullbackScan = useCallback(async () => {
        if (watchlist.length === 0) { setPullbackCandidates([]); return; }
        setPullbackLoading(true);
        try {
            const results = await scanPullback(watchlist.map(w => w.code), market, 55);
            setPullbackCandidates(results);
        } catch { setPullbackCandidates([]); }
        finally { setPullbackLoading(false); }
    }, [watchlist, market]);

    useEffect(() => {
        if (leftTab === 'pullback') runPullbackScan();
    }, [leftTab, runPullbackScan]);

    const toggleWatchlist = useCallback(() => {
        if (!stockCode) return;
        setWatchlist(prev => {
            const next = prev.some(w => w.code === stockCode)
                ? prev.filter(w => w.code !== stockCode)
                : [...prev, { code: stockCode, market, addedAt: new Date().toISOString(), name: stockName }];
            saveWatchlist(next);
            return next;
        });
        if (!isWatchlisted) {
            setWatchlistAdded(true);
            setTimeout(() => setWatchlistAdded(false), 2000);
        }
    }, [stockCode, stockName, isWatchlisted]);

    // Load surge stocks + poll every 30s
    useEffect(() => {
        isManualSelectionRef.current = false;
        setSurgeStocks([]);
        setStockCode(null);
        setCandles([]);
        setScore(null);
        setError(null);
        setSurgeLoading(true);
        setChartMode('daily');
        setCupHandle(undefined);
        setStockAnalysis(null);

        const loadSurge = async () => {
            try {
                const data = await fetchSurgeStocks(market);
                setSurgeStocks(data);

                // 종목별 점수 병렬 fetch (scorer 캐시 없이 직접 조회)
                const scoreResults = await Promise.allSettled(
                    data.map(s => fetchStockScore(s.code, market))
                );
                const newScoreMap: Record<string, number> = {};
                scoreResults.forEach((r, i) => {
                    if (r.status === 'fulfilled' && r.value.total_score != null) {
                        newScoreMap[data[i].code] = Number(r.value.total_score);
                    }
                });
                setScoreMap(newScoreMap);

                // C&H 데이터: 상위 30개만 pattern 신호 fetch (성능 고려)
                const top30 = data.slice(0, 30);
                const chResults = await Promise.allSettled(
                    top30.map(s => fetchEntrySignal(s.code, market, 'pattern'))
                );
                const newChMap: Record<string, string> = {};
                chResults.forEach((r, i) => {
                    if (r.status === 'fulfilled' && r.value.cup_handle?.breakout_status) {
                        newChMap[top30[i].code] = r.value.cup_handle.breakout_status;
                    }
                });
                setChMap(newChMap);
            } catch { /* ignore */ }
            finally { setSurgeLoading(false); }
        };
        loadSurge();
        const interval = setInterval(loadSurge, 30_000);
        return () => clearInterval(interval);
    }, [market]);

    // Auto-select first filtered stock (수동 입력 시 건너뜀)
    useEffect(() => {
        if (isManualSelectionRef.current) return;
        if (filteredStocks.length > 0 && (!stockCode || !filteredStocks.find(s => s.code === stockCode))) {
            setStockCode(filteredStocks[0].code);
        }
    }, [filteredStocks, stockCode]);

    // Reset to daily chart when stock changes (리스트 클릭 선택)
    const handleSelectStock = useCallback((code: string) => {
        isManualSelectionRef.current = false;
        setChartMode('daily');
        setStockCode(code);
    }, []);

    // 레프트메뉴 수동 코드 입력 - auto-select 덮어쓰기 방지
    const handleManualSelect = useCallback((code: string) => {
        isManualSelectionRef.current = true;
        setChartMode('daily');
        setStockCode(code);
    }, []);

    // 외부(관심종목 탭 등)에서 종목 코드 전달 시 자동 선택
    useEffect(() => {
        if (!focusCode) return;
        handleManualSelect(focusCode);
        onFocusDone?.();
    }, [focusCode, handleManualSelect, onFocusDone]);

    // Load chart and score for selected stock
    const chartModeRef = useRef(chartMode);
    chartModeRef.current = chartMode;
    const marketRef = useRef(market);
    marketRef.current = market;

    const loadStockData = useCallback(async (code: string, isPolling = false, mode?: ChartMode) => {
        const myLoadId = ++loadIdRef.current;
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

            // 더 최신 요청이 시작됐으면 이 응답은 무시
            if (myLoadId !== loadIdRef.current) return;

            // fetchStockAnalyze는 실패해도 차트/점수 로드를 막지 않음
            fetchStockAnalyze(code, currentMarket as Market)
                .then(d => { if (myLoadId === loadIdRef.current) setStockAnalysis(d.error ? null : d); })
                .catch(() => { if (myLoadId === loadIdRef.current) setStockAnalysis(null); });

            const chartFormatted = chartData.map((c) => {
                if (currentMode === 'minute') {
                    return {
                        time: Math.floor(new Date(c.time).getTime() / 1000),
                        open: c.open,
                        high: c.high,
                        low: c.low,
                        close: c.close,
                        volume: c.volume ?? 0,
                    };
                }
                return {
                    time: c.time,
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close,
                    volume: c.volume ?? 0,
                };
            });
            setCandles(chartFormatted);
            setScore(scoreData);
        } catch (err: any) {
            if (myLoadId !== loadIdRef.current) return;
            if (!isPolling) setError(err?.message ?? '데이터를 불러오지 못했습니다.');
        } finally {
            if (myLoadId === loadIdRef.current && !isPolling) setLoading(false);
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

    // Fetch cup & handle data independently (pattern strategy only)
    useEffect(() => {
        if (!stockCode) { setCupHandle(undefined); return; }
        let cancelled = false;
        setCupHandle(undefined);
        setCupHandleLoading(true);
        fetchEntrySignal(stockCode, market, 'pattern')
            .then(sig => { if (!cancelled) setCupHandle(sig.cup_handle ?? null); })
            .catch(() => { if (!cancelled) setCupHandle(null); })
            .finally(() => { if (!cancelled) setCupHandleLoading(false); });
        return () => { cancelled = true; };
    }, [stockCode, market]);

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

    // ── 차트 데이터 기반 통계 (구간 고저, ATR, 손절가) ──────────────────────
    const chartStats = useMemo(() => {
        if (!candles || candles.length < 2) return null;
        const highs = candles.map((c: any) => c.high as number);
        const lows  = candles.map((c: any) => c.low  as number);
        const closes= candles.map((c: any) => c.close as number);
        const periodHigh = Math.max(...highs);
        const periodLow  = Math.min(...lows);
        const cur = closes[closes.length - 1];
        const vsHighPct = ((cur - periodHigh) / periodHigh) * 100;
        const vsLowPct  = ((cur - periodLow)  / periodLow)  * 100;

        // ATR(14) = 14일 단순평균 True Range
        let atr: number | null = null;
        if (candles.length >= 15) {
            const trs = (candles as any[]).slice(1).map((c: any, i: number) => {
                const pc = closes[i];
                return Math.max(c.high - c.low, Math.abs(c.high - pc), Math.abs(c.low - pc));
            });
            atr = trs.slice(-14).reduce((s: number, v: number) => s + v, 0) / 14;
        }

        // 적응형 ATR 손절가 (signal_service._compute_atr_stop 와 동일 로직)
        let atrStop: number | null = null;
        let atrMult: number | null = null;
        if (atr && cur > 0) {
            const atrPct = atr / cur;
            atrMult = atrPct < 0.02 ? 1.2 : atrPct < 0.04 ? 1.5 : 2.0;
            const rawStop  = cur - atr * atrMult;
            const hardFloor = cur * (1 - 0.08);
            atrStop = Math.max(rawStop, hardFloor);
        }

        // 거래량 (차트 데이터에 volume 포함 시 사용)
        const vols = (candles as any[]).map((c: any) => c.volume as number).filter(Boolean);
        const vol5dAvg  = vols.length >= 5  ? vols.slice(-5).reduce((s:number,v:number)=>s+v,0)/5   : null;
        const vol20dAvg = vols.length >= 20 ? vols.slice(-20).reduce((s:number,v:number)=>s+v,0)/20  : null;
        const volRatio  = vol5dAvg && vol20dAvg ? vol5dAvg / vol20dAvg : null;

        return {
            periodHigh, periodLow, cur, vsHighPct, vsLowPct,
            atr, atrStop, atrMult,
            vol5dAvg, vol20dAvg, volRatio,
            periodDays: candles.length,
        };
    }, [candles]);

    return (
        <div className="h-full grid grid-cols-[280px_1fr_320px] gap-4">
            {/* LEFT PANEL: Tab (급등주 / 눌림목) */}
            <aside className="flex flex-col overflow-hidden">
                {/* Tab Switcher */}
                <div className="flex mb-3 bg-slate-800/60 rounded-lg p-0.5 shrink-0">
                    <button
                        onClick={() => setLeftTab('surge')}
                        className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all ${leftTab === 'surge' ? 'bg-primary text-white shadow' : 'text-slate-400 hover:text-slate-200'}`}
                    >
                        급등주
                    </button>
                    <button
                        onClick={() => setLeftTab('pullback')}
                        className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all ${leftTab === 'pullback' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'}`}
                    >
                        눌림목
                    </button>
                </div>

                {/* 급등주 탭 */}
                {leftTab === 'surge' && (
                    <div className="flex-1 overflow-y-auto">
                        <SurgeList
                            stocks={filteredStocks}
                            selectedCode={stockCode}
                            onSelect={handleSelectStock}
                            onManualSelect={handleManualSelect}
                            loading={surgeLoading}
                            market={market}
                            scoreMap={scoreMap}
                            chMap={chMap}
                        />
                        {!surgeLoading && filteredStocks.length === 0 && surgeStocks.length > 0 && (
                            <div className="mt-4 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-sm text-yellow-300">
                                필터 조건에 맞는 종목이 없습니다
                            </div>
                        )}
                    </div>
                )}

                {/* 눌림목 탭 (Track B) */}
                {leftTab === 'pullback' && (
                    <div className="flex-1 overflow-y-auto">
                        <div className="flex items-center justify-between mb-3 px-1">
                            <span className="text-xs text-slate-400">관심종목 {watchlist.length}개 스캔</span>
                            <button
                                onClick={runPullbackScan}
                                disabled={pullbackLoading || watchlist.length === 0}
                                className="text-xs px-2 py-1 rounded bg-indigo-600/30 text-indigo-300 hover:bg-indigo-600/50 disabled:opacity-40 transition-all"
                            >
                                {pullbackLoading ? '스캔 중…' : '재스캔'}
                            </button>
                        </div>

                        {watchlist.length === 0 && (
                            <div className="text-center py-10 text-slate-500 text-xs px-2">
                                관심종목을 추가하면<br />눌림목 후보를 자동 탐색합니다
                            </div>
                        )}

                        {pullbackLoading && (
                            <div className="flex items-center justify-center py-10">
                                <Loader2 className="animate-spin text-indigo-400" size={22} />
                            </div>
                        )}

                        {!pullbackLoading && pullbackCandidates.length === 0 && watchlist.length > 0 && (
                            <div className="text-center py-10 text-slate-500 text-xs">
                                눌림목 후보 없음<br />(score ≥ 55 기준)
                            </div>
                        )}

                        {!pullbackLoading && pullbackCandidates.map(c => (
                            <button
                                key={c.code}
                                onClick={() => handleSelectStock(c.code)}
                                className={`w-full text-left px-3 py-2.5 rounded-lg mb-1 transition-all border ${stockCode === c.code ? 'bg-indigo-600/20 border-indigo-500/40' : 'hover:bg-slate-800/60 border-transparent'}`}
                            >
                                <div className="flex items-center justify-between">
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-1.5 flex-wrap">
                                            <span className="font-medium text-slate-200 text-sm truncate">
                                                {watchlist.find(w => w.code === c.code)?.name ?? c.code}
                                            </span>
                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-600/30 text-indigo-300 font-bold shrink-0">
                                                눌림목
                                            </span>
                                        </div>
                                        <div className="text-xs text-slate-500 mt-0.5">{c.code} · {c.adjustment_days}일 조정</div>
                                        {c.fib_levels['382'] && (
                                            <div className="text-[10px] text-indigo-400 mt-0.5 font-mono">
                                                Fib 38.2%: {Number(c.fib_levels['382']).toLocaleString()}
                                                {c.fib_levels['500'] ? ` / 50%: ${Number(c.fib_levels['500']).toLocaleString()}` : ''}
                                            </div>
                                        )}
                                    </div>
                                    <div className="text-right shrink-0 ml-2">
                                        <div className="text-sm font-mono text-slate-200">{c.current_price.toLocaleString()}원</div>
                                        <span className={`text-[10px] font-bold px-1 py-0.5 rounded font-mono ${c.score >= 80 ? 'bg-green-500/20 text-green-400' : c.score >= 65 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-slate-700 text-slate-400'}`}>
                                            {c.score}
                                        </span>
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>
                )}
            </aside>

            {/* CENTER PANEL: Stock Info + Chart + Info Cards */}
            <main className="flex flex-col overflow-hidden min-h-0">
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
                        {/* ── 상단: 종목 정보 헤더 ─────────────────────────── */}
                        <div className="bg-surface rounded-xl border border-slate-700 p-4 mb-3 shrink-0">
                            <div className="flex items-center justify-between">
                                <div>
                                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                                        <h2 className="text-2xl font-bold">{stockName}</h2>
                                        <button
                                            onClick={toggleWatchlist}
                                            title={isWatchlisted ? '관심종목 해제' : '관심종목 추가'}
                                            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-sm font-medium border transition-all ${
                                                isWatchlisted
                                                    ? 'bg-yellow-500/20 border-yellow-500/60 text-yellow-400 hover:bg-yellow-500/30'
                                                    : 'bg-slate-700/50 border-slate-600 text-slate-400 hover:bg-slate-700 hover:text-yellow-400 hover:border-yellow-500/40'
                                            }`}
                                        >
                                            <Star size={14} className={isWatchlisted ? 'fill-yellow-400 text-yellow-400' : ''} />
                                            {watchlistAdded ? '추가됨!' : isWatchlisted ? '관심종목' : '관심추가'}
                                        </button>
                                        {cupHandleLoading && (
                                            <span className="text-xs text-slate-500 animate-pulse">☕ 분석중...</span>
                                        )}
                                        {!cupHandleLoading && cupHandle && (
                                            <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-sm font-bold ${
                                                cupHandle.breakout_status === 'fresh'   ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/30' :
                                                cupHandle.breakout_status === 'pre'     ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/30' :
                                                cupHandle.breakout_status === 'expired' ? 'bg-slate-600/60 text-slate-400' :
                                                                                          'bg-slate-700/60 text-slate-400'
                                            }`}>
                                                ☕
                                                {cupHandle.breakout_status === 'fresh'   ? 'C&H 돌파'  :
                                                 cupHandle.breakout_status === 'pre'     ? 'C&H 임박'  :
                                                 cupHandle.breakout_status === 'expired' ? 'C&H 소멸'  : 'C&H 형성중'}
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-sm text-slate-400">{stockCode} · {market}</p>
                                </div>
                                {surgeInfo && (
                                    <div className="text-right">
                                        <div className="text-3xl font-mono font-bold mb-1">
                                            {market === 'US' ? '$' : ''}{surgeInfo.price.toLocaleString()}{market === 'KR' ? '원' : ''}
                                        </div>
                                        <div className={`flex items-center justify-end gap-1 text-sm font-mono ${surgeInfo.change_rate > 0 ? 'text-red-400' : 'text-blue-400'}`}>
                                            {surgeInfo.change_rate > 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                                            <span>
                                                {surgeInfo.change_rate > 0 ? '+' : ''}{market === 'US' ? '$' : ''}
                                                {surgeInfo.change_price.toLocaleString()}{market === 'KR' ? '원' : ''}
                                            </span>
                                            <span>({surgeInfo.change_rate > 0 ? '+' : ''}{surgeInfo.change_rate.toFixed(2)}%)</span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* ── 중간: 차트 (50% 축소) ───────────────────────── */}
                        <div className="flex gap-2 mb-2 shrink-0">
                            {(['daily','weekly','minute'] as ChartMode[]).map(m => (
                                <button key={m} onClick={() => setChartMode(m)}
                                    className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                                        chartMode === m ? 'bg-primary text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                                    }`}>
                                    {m === 'daily' ? '일봉' : m === 'weekly' ? '주봉' : '분봉'}
                                </button>
                            ))}
                        </div>

                        <div className="h-[260px] shrink-0 mb-3">
                            {candles.length > 0 ? (
                                <CandleChart key={`${stockCode}-${chartMode}`} data={candles} />
                            ) : (
                                <div className="bg-surface rounded-xl border border-slate-700 h-full flex items-center justify-center text-slate-500">
                                    차트 데이터 없음
                                </div>
                            )}
                        </div>

                        {/* ── 하단: 정보 카드 그리드 (2열) ────────────────── */}
                        <div className="flex-1 overflow-y-auto min-h-0">
                            <div className="grid grid-cols-2 gap-2 pb-2">

                                {/* 카드 1: 현재 패턴 */}
                                <div className="bg-surface rounded-xl border border-slate-700 p-3">
                                    <h4 className="text-xs font-bold text-slate-400 mb-2 uppercase tracking-wide">🔍 현재 패턴</h4>
                                    <div className="space-y-1.5 text-xs">
                                        {/* RSI 상태 */}
                                        {technical?.rsi != null && (
                                            <div className="flex justify-between items-center">
                                                <span className="text-slate-400">RSI(14)</span>
                                                <span className={`font-mono font-bold ${
                                                    technical.rsi > 70 ? 'text-red-400' :
                                                    technical.rsi < 30 ? 'text-blue-400' : 'text-green-400'
                                                }`}>
                                                    {technical.rsi.toFixed(1)}
                                                    <span className="text-slate-500 font-normal ml-1">
                                                        {technical.rsi > 70 ? '과매수' : technical.rsi < 30 ? '과매도' : '중립'}
                                                    </span>
                                                </span>
                                            </div>
                                        )}
                                        {/* MA 배열 */}
                                        {technical?.ma20 != null && technical?.ma60 != null && chartStats && (
                                            <div className="flex justify-between items-center">
                                                <span className="text-slate-400">MA 배열</span>
                                                <span className={`font-bold text-[10px] px-1.5 py-0.5 rounded ${
                                                    chartStats.cur > technical.ma20 && technical.ma20 > technical.ma60
                                                        ? 'bg-red-500/20 text-red-300' : 'bg-blue-500/20 text-blue-300'
                                                }`}>
                                                    {chartStats.cur > technical.ma20 && technical.ma20 > technical.ma60 ? '정배열' : '역배열/혼조'}
                                                </span>
                                            </div>
                                        )}
                                        {/* C&H 패턴 */}
                                        <div className="flex justify-between items-center">
                                            <span className="text-slate-400">C&H</span>
                                            {cupHandleLoading ? (
                                                <span className="text-slate-500 text-[10px]">분석중...</span>
                                            ) : cupHandle ? (
                                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                                    cupHandle.breakout_status === 'fresh'   ? 'bg-purple-600/40 text-purple-300' :
                                                    cupHandle.breakout_status === 'pre'     ? 'bg-orange-600/40 text-orange-300' :
                                                    cupHandle.breakout_status === 'expired' ? 'bg-slate-600/40 text-slate-400' :
                                                                                              'bg-slate-700/40 text-slate-400'
                                                }`}>
                                                    {cupHandle.breakout_status === 'fresh'   ? '돌파 ✓' :
                                                     cupHandle.breakout_status === 'pre'     ? '임박'   :
                                                     cupHandle.breakout_status === 'expired' ? '소멸'   : '형성중'}
                                                </span>
                                            ) : (
                                                <span className="text-slate-600 text-[10px]">—</span>
                                            )}
                                        </div>
                                        {/* 60일 수익률 */}
                                        {technical?.return_60d != null && (
                                            <div className="flex justify-between">
                                                <span className="text-slate-400">60일 수익</span>
                                                <span className={`font-mono ${technical.return_60d > 0 ? 'text-red-400' : 'text-blue-400'}`}>
                                                    {technical.return_60d > 0 ? '+' : ''}{technical.return_60d.toFixed(1)}%
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* 카드 2: 구간 고/저점 */}
                                <div className="bg-surface rounded-xl border border-slate-700 p-3">
                                    <h4 className="text-xs font-bold text-slate-400 mb-2 uppercase tracking-wide">📊 구간 고/저점</h4>
                                    {chartStats ? (
                                        <div className="space-y-1.5 text-xs">
                                            <div className="flex justify-between">
                                                <span className="text-slate-400">구간 고점</span>
                                                <span className="font-mono text-red-300">{chartStats.periodHigh.toLocaleString()}{market === 'KR' ? '원' : ''}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-slate-400">구간 저점</span>
                                                <span className="font-mono text-blue-300">{chartStats.periodLow.toLocaleString()}{market === 'KR' ? '원' : ''}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-slate-400">현재가</span>
                                                <span className="font-mono text-slate-200">{chartStats.cur.toLocaleString()}{market === 'KR' ? '원' : ''}</span>
                                            </div>
                                            <div className="pt-1 border-t border-slate-700/60 flex justify-between">
                                                <span className="text-slate-400">구간</span>
                                                <span className="text-slate-400">{chartStats.periodDays}거래일</span>
                                            </div>
                                        </div>
                                    ) : <p className="text-xs text-slate-600">데이터 없음</p>}
                                </div>

                                {/* 카드 3: 고점대비 비율 */}
                                <div className="bg-surface rounded-xl border border-slate-700 p-3">
                                    <h4 className="text-xs font-bold text-slate-400 mb-2 uppercase tracking-wide">📉 고점/저점 대비</h4>
                                    {chartStats ? (
                                        <div className="space-y-2 text-xs">
                                            <div>
                                                <div className="flex justify-between mb-1">
                                                    <span className="text-slate-400">고점 대비</span>
                                                    <span className={`font-mono font-bold ${chartStats.vsHighPct >= -5 ? 'text-red-400' : chartStats.vsHighPct >= -15 ? 'text-yellow-400' : 'text-slate-400'}`}>
                                                        {chartStats.vsHighPct.toFixed(1)}%
                                                    </span>
                                                </div>
                                                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                                    <div className="h-full bg-red-500/60 rounded-full"
                                                        style={{ width: `${Math.max(0, 100 + chartStats.vsHighPct)}%` }} />
                                                </div>
                                            </div>
                                            <div>
                                                <div className="flex justify-between mb-1">
                                                    <span className="text-slate-400">저점 대비</span>
                                                    <span className={`font-mono font-bold ${chartStats.vsLowPct > 50 ? 'text-green-400' : chartStats.vsLowPct > 20 ? 'text-yellow-400' : 'text-slate-400'}`}>
                                                        +{chartStats.vsLowPct.toFixed(1)}%
                                                    </span>
                                                </div>
                                                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                                    <div className="h-full bg-green-500/60 rounded-full"
                                                        style={{ width: `${Math.min(100, chartStats.vsLowPct / 2)}%` }} />
                                                </div>
                                            </div>
                                            {technical?.ma20 != null && (
                                                <div className="flex justify-between pt-1 border-t border-slate-700/60">
                                                    <span className="text-slate-400">MA20 대비</span>
                                                    <span className={`font-mono ${((chartStats.cur / technical.ma20) - 1) > 0 ? 'text-red-400' : 'text-blue-400'}`}>
                                                        {(((chartStats.cur / technical.ma20) - 1) * 100) > 0 ? '+' : ''}
                                                        {(((chartStats.cur / technical.ma20) - 1) * 100).toFixed(1)}%
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                    ) : <p className="text-xs text-slate-600">데이터 없음</p>}
                                </div>

                                {/* 카드 4: ATR 손절가 */}
                                <div className="bg-surface rounded-xl border border-amber-600/30 p-3">
                                    <h4 className="text-xs font-bold text-amber-400/80 mb-2 uppercase tracking-wide">⚡ ATR 손절 기준</h4>
                                    {chartStats?.atr != null ? (
                                        <div className="space-y-1.5 text-xs">
                                            <div className="flex justify-between">
                                                <span className="text-slate-400">ATR(14)</span>
                                                <span className="font-mono text-slate-300">
                                                    {chartStats.atr.toFixed(0)}{market === 'KR' ? '원' : ''}
                                                    <span className="text-slate-500 ml-1">({(chartStats.atr / chartStats.cur * 100).toFixed(1)}%)</span>
                                                </span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-slate-400">배수</span>
                                                <span className="font-mono text-slate-300">{chartStats.atrMult}×</span>
                                            </div>
                                            <div className="flex justify-between items-center pt-1 border-t border-slate-700/60">
                                                <span className="text-amber-400/80 font-medium">손절가</span>
                                                <span className="font-mono font-bold text-amber-400">
                                                    {chartStats.atrStop!.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}{market === 'KR' ? '원' : ''}
                                                </span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-slate-400">손실 비율</span>
                                                <span className="font-mono text-red-400">
                                                    {(((chartStats.atrStop! - chartStats.cur) / chartStats.cur) * 100).toFixed(1)}%
                                                </span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-slate-400">hard floor</span>
                                                <span className="font-mono text-slate-500">
                                                    {(chartStats.cur * 0.92).toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}원 (-8%)
                                                </span>
                                            </div>
                                        </div>
                                    ) : <p className="text-xs text-slate-600">차트 데이터 부족 (15일 필요)</p>}
                                </div>

                                {/* 카드 5: 거래량 */}
                                <div className="bg-surface rounded-xl border border-slate-700 p-3">
                                    <h4 className="text-xs font-bold text-slate-400 mb-2 uppercase tracking-wide">📦 거래량</h4>
                                    <div className="space-y-1.5 text-xs">
                                        {surgeInfo && (
                                            <div className="flex justify-between">
                                                <span className="text-slate-400">거래대금</span>
                                                <span className="font-mono text-slate-300">
                                                    {surgeInfo.volume >= 1_000_000
                                                        ? `${(surgeInfo.volume / 1_000_000).toFixed(1)}M`
                                                        : surgeInfo.volume >= 1_000
                                                        ? `${(surgeInfo.volume / 1_000).toFixed(0)}K`
                                                        : surgeInfo.volume.toLocaleString()}
                                                </span>
                                            </div>
                                        )}
                                        {chartStats?.vol5dAvg != null && (
                                            <div className="flex justify-between">
                                                <span className="text-slate-400">5일 평균</span>
                                                <span className="font-mono text-slate-300">
                                                    {chartStats.vol5dAvg >= 1_000_000
                                                        ? `${(chartStats.vol5dAvg / 1_000_000).toFixed(2)}M`
                                                        : `${(chartStats.vol5dAvg / 1_000).toFixed(0)}K`}
                                                </span>
                                            </div>
                                        )}
                                        {chartStats?.vol20dAvg != null && (
                                            <div className="flex justify-between">
                                                <span className="text-slate-400">20일 평균</span>
                                                <span className="font-mono text-slate-300">
                                                    {chartStats.vol20dAvg >= 1_000_000
                                                        ? `${(chartStats.vol20dAvg / 1_000_000).toFixed(2)}M`
                                                        : `${(chartStats.vol20dAvg / 1_000).toFixed(0)}K`}
                                                </span>
                                            </div>
                                        )}
                                        {chartStats?.volRatio != null ? (
                                            <div className="pt-1 border-t border-slate-700/60">
                                                <div className="flex justify-between mb-1">
                                                    <span className="text-slate-400">비율 (5일/20일)</span>
                                                    <span className={`font-mono font-bold ${chartStats.volRatio >= 1.5 ? 'text-red-400' : chartStats.volRatio >= 1.0 ? 'text-yellow-400' : 'text-slate-400'}`}>
                                                        {chartStats.volRatio.toFixed(2)}×
                                                    </span>
                                                </div>
                                                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                                    <div className={`h-full rounded-full ${chartStats.volRatio >= 1.5 ? 'bg-red-500/70' : chartStats.volRatio >= 1.0 ? 'bg-yellow-500/70' : 'bg-slate-500/70'}`}
                                                        style={{ width: `${Math.min(100, chartStats.volRatio * 50)}%` }} />
                                                </div>
                                            </div>
                                        ) : (
                                            technical?.volatility != null && (
                                                <div className="flex justify-between pt-1 border-t border-slate-700/60">
                                                    <span className="text-slate-400">변동성(20d)</span>
                                                    <span className="font-mono text-slate-300">{(technical.volatility * 100).toFixed(2)}%</span>
                                                </div>
                                            )
                                        )}
                                    </div>
                                </div>

                                {/* 카드 6: 종합 의견 (백엔드 signal 기반) */}
                                {(() => {
                                    const isBuy = stockAnalysis?.signal === 'BUY';
                                    const isChaseBlocked = stockAnalysis?.chase_blocked ?? false;
                                    const verdict = !stockAnalysis ? '분석 중'
                                        : isChaseBlocked ? '추격차단'
                                        : isBuy       ? '매수'
                                        :               '관망';
                                    const verdictColor = verdict === '매수'       ? 'bg-green-500/20 text-green-300 border-green-500/40'
                                        : verdict === '추격차단' ? 'bg-orange-500/20 text-orange-300 border-orange-500/40'
                                        : verdict === '분석 중'  ? 'bg-slate-700/40 text-slate-400 border-slate-600'
                                        :                          'bg-yellow-500/20 text-yellow-300 border-yellow-500/40';
                                    const reasons: string[] = stockAnalysis?.signal_reasons ?? [];
                                    const beScore = stockAnalysis?.score ?? null;
                                    const ps = stockAnalysis?.pre_surge;
                                    const hasPreSurge = ps && (
                                        ps.dryup_recovery.detected ||
                                        ps.seoryuk.detected ||
                                        ps.tight_consol.detected
                                    );

                                    return (
                                        <div className="bg-surface rounded-xl border border-slate-700 p-3">
                                            <h4 className="text-xs font-bold text-slate-400 mb-2 uppercase tracking-wide">💡 종합 의견</h4>
                                            <div className="space-y-1.5 text-xs">
                                                <div className="flex items-center justify-between">
                                                    <span className={`inline-block px-2 py-0.5 rounded border font-bold text-sm ${verdictColor}`}>
                                                        {verdict}
                                                    </span>
                                                    {beScore != null && (
                                                        <span className={`font-mono font-bold text-sm ${beScore >= 70 ? 'text-green-400' : beScore >= 50 ? 'text-yellow-400' : 'text-slate-500'}`}>
                                                            {beScore}점
                                                        </span>
                                                    )}
                                                </div>
                                                {reasons.length > 0 ? (
                                                    <div className="pt-1 space-y-1">
                                                        {reasons.map((r, i) => (
                                                            <div key={i} className={`flex items-start gap-1 ${r.includes('추격차단') || r.includes('급등') ? 'text-orange-400' : isBuy ? 'text-green-400' : 'text-slate-400'}`}>
                                                                <span className="shrink-0 mt-0.5">{r.includes('추격차단') || r.includes('급등') ? '⚠' : isBuy ? '▲' : '–'}</span>
                                                                <span>{r}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                ) : (
                                                    stockAnalysis && <p className="text-slate-600 text-[10px] pt-1">신호 근거 없음</p>
                                                )}
                                                {hasPreSurge && (
                                                    <div className="mt-2 pt-2 border-t border-slate-700/60">
                                                        <p className="text-[10px] font-bold text-purple-400 mb-1">⚡ 급등 전 시그널</p>
                                                        {ps!.dryup_recovery.detected && (
                                                            <div className="text-purple-300 text-[10px]">
                                                                📊 거래량 건조 회복 ({ps!.dryup_recovery.dryup_days}일 건조
                                                                {ps!.dryup_recovery.extreme_dryup ? ' · 극단' : ''} → ×{ps!.dryup_recovery.vol_ratio_at_recovery})
                                                            </div>
                                                        )}
                                                        {ps!.seoryuk.detected && (
                                                            <div className="text-red-300 text-[10px]">
                                                                🔥 세력 매집 의심 (폭발 ×{ps!.seoryuk.spike_ratio} · 최저 ×{ps!.seoryuk.dryup_min_ratio})
                                                            </div>
                                                        )}
                                                        {ps!.tight_consol.detected && (
                                                            <div className="text-cyan-300 text-[10px]">
                                                                🗜️ 에너지 압축 {ps!.tight_consol.range_pct}% 횡보
                                                                {ps!.tight_consol.vol_trend === 'shrinking' ? ' · 거래량 수축' : ''}
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })()}

                            </div>
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

                        {/* Cup & Handle Pattern — show when loading or pattern found */}
                        {(cupHandleLoading || cupHandle) && (
                            <div className={`rounded-xl border p-4 ${cupHandle?.breakout_status === 'fresh' ? 'bg-purple-900/20 border-purple-600/60' :
                                    cupHandle?.breakout_status === 'pre' ? 'bg-orange-900/20 border-orange-600/60' :
                                        'bg-surface border-slate-700'
                                }`}>
                                <h3 className="text-sm font-bold text-slate-300 mb-3">☕ 컵앤핸들 패턴</h3>
                                {cupHandleLoading ? (
                                    <p className="text-xs text-slate-500">분석 중...</p>
                                ) : cupHandle ? (
                                    <>
                                        <div className="flex items-center justify-between mb-2">
                                            <span className={`text-xs font-bold px-2 py-0.5 rounded ${cupHandle.breakout_status === 'fresh' ? 'bg-purple-600 text-white' :
                                                    cupHandle.breakout_status === 'pre' ? 'bg-orange-500 text-white' :
                                                        cupHandle.breakout_status === 'expired' ? 'bg-slate-600 text-slate-300' :
                                                            'bg-slate-700 text-slate-400'
                                                }`}>
                                                {cupHandle.breakout_status === 'fresh' ? '돌파 확인' :
                                                    cupHandle.breakout_status === 'pre' ? '돌파 임박' :
                                                        cupHandle.breakout_status === 'expired' ? '기회 소멸' : '형성 중'}
                                            </span>
                                            <span className="text-sm font-bold text-slate-300">{cupHandle.score}점</span>
                                        </div>
                                        <ul className="space-y-1">
                                            {cupHandle.reasons.map((r, i) => (
                                                <li key={i} className={`text-xs flex items-start gap-1 ${cupHandle.breakout_status === 'expired' ? 'text-slate-500' : 'text-slate-300'
                                                    }`}>
                                                    <span className="mt-0.5 shrink-0">◆</span>
                                                    <span>{r}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </>
                                ) : (
                                    <p className="text-xs text-slate-500">패턴 없음</p>
                                )}
                            </div>
                        )}

                        {/* Fundamental Data */}
                        <div className="bg-surface rounded-xl border border-slate-700 p-4">
                            <h3 className="text-sm font-bold text-slate-300 mb-3">📊 펀더멘털</h3>
                            {fundamental ? (
                                <div className="space-y-2 text-sm">
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">PER</span>
                                        <span className={`font-mono ${(fundamental.per ?? 0) < 20 ? 'text-green-400' :
                                                (fundamental.per ?? 0) > 50 ? 'text-red-400' : 'text-slate-300'
                                            }`}>
                                            {fundamental.per != null ? fundamental.per.toFixed(1) : '-'}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">PBR</span>
                                        <span className={`font-mono ${(fundamental.pbr ?? 0) < 1.5 ? 'text-green-400' : 'text-slate-300'
                                            }`}>
                                            {fundamental.pbr != null ? fundamental.pbr.toFixed(2) : '-'}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">ROE</span>
                                        <span className={`font-mono ${(fundamental.roe ?? 0) > 10 ? 'text-green-400' : 'text-slate-300'
                                            }`}>
                                            {fundamental.roe != null ? `${fundamental.roe.toFixed(1)}%` : '-'}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">EPS</span>
                                        <span className={`font-mono ${(fundamental.eps ?? 0) > 0 ? 'text-slate-300' : 'text-red-400'
                                            }`}>
                                            {fundamental.eps != null ? `${market === 'US' ? '$' : ''}${fundamental.eps.toLocaleString()}` : '-'}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">BPS</span>
                                        <span className="font-mono text-slate-300">
                                            {fundamental.bps != null ? `${market === 'US' ? '$' : ''}${fundamental.bps.toLocaleString()}` : '-'}
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
                                        <span className={`font-mono ${(technical.rsi ?? 50) > 70 ? 'text-red-400' :
                                                (technical.rsi ?? 50) < 30 ? 'text-blue-400' : 'text-slate-300'
                                            }`}>
                                            {technical.rsi != null ? technical.rsi.toFixed(1) : '-'}
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
                                            {technical.volatility != null ? `${(technical.volatility * 100).toFixed(2)}%` : '-'}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">60일 수익률</span>
                                        <span className={`font-mono ${(technical.return_60d ?? 0) > 0 ? 'text-red-400' : 'text-blue-400'
                                            }`}>
                                            {technical.return_60d != null
                                                ? `${technical.return_60d > 0 ? '+' : ''}${technical.return_60d.toFixed(1)}%`
                                                : '-'}
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
