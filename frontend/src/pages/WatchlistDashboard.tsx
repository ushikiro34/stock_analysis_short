import { useState, useEffect, useCallback } from 'react';
import {
    Plus, Trash2, RefreshCw, Star, TrendingUp, TrendingDown,
    AlertTriangle, CheckCircle, Minus, ChevronUp, ChevronDown,
    ShoppingCart, Check, X,
} from 'lucide-react';
import type { Market, StockAnalysis } from '../lib/api';
import { fetchStockAnalyze, paperTrading } from '../lib/api';

// ── 로컬스토리지 관심종목 관리 ────────────────────────────────

interface WatchItem {
    code: string;
    market: Market;
    addedAt: string;
    name?: string;  // StocksDashboard 에서 추가 시 종목명 포함
}

const STORAGE_KEY = 'watchlist_v1';

function loadWatchlist(): WatchItem[] {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); }
    catch { return []; }
}

function saveWatchlist(items: WatchItem[]) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
}

// ── 유틸 ─────────────────────────────────────────────────────

function fmtPrice(n: number, market: string) {
    return market === 'US'
        ? `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
        : `${n.toLocaleString()}원`;
}

function fmtPct(n: number) {
    return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`;
}

function fmtVolRatio(r: number) {
    return `${r.toFixed(1)}x`;
}

type SortKey = 'code' | 'change_pct' | 'vol_ratio' | 'vs_ma20_pct' | 'score' | 'signal';
type SortDir = 'asc' | 'desc';
type BuyState = 'idle' | 'loading' | 'success' | 'error';

// ── 컴포넌트 ──────────────────────────────────────────────────

interface AnalysisRow extends WatchItem {
    data?: StockAnalysis;
    loading: boolean;
    error?: string;
}

const rowKey = (r: { code: string; market: string }) => `${r.code}-${r.market}`;

export default function WatchlistDashboard({ market, isVisible = false, onNavigateToStock }: { market: Market; isVisible?: boolean; onNavigateToStock?: (code: string, market: Market) => void }) {
    const [rows, setRows] = useState<AnalysisRow[]>([]);
    const [sortKey, setSortKey] = useState<SortKey>('code');
    const [sortDir, setSortDir] = useState<SortDir>('asc');
    const [addCode, setAddCode] = useState('');
    const [addMarket, setAddMarket] = useState<Market>(market);
    const [refreshing, setRefreshing] = useState(false);

    // 수량 상태: key = "code-market"
    const [quantities, setQuantities] = useState<Record<string, number>>({});
    // 매수 버튼 상태: key = "code-market"
    const [buyStates, setBuyStates] = useState<Record<string, BuyState>>({});

    // 마켓 변경 시 addMarket 동기화
    useEffect(() => { setAddMarket(market); }, [market]);

    // 분석 데이터 fetch (최대 4개 동시 — 장 종료 후 느린 백엔드 대비)
    const fetchAll = useCallback(async (items: WatchItem[]) => {
        if (items.length === 0) {
            setRows([]);
            return;
        }
        // 로딩 상태로 전환 (기존 데이터는 유지)
        setRows(prev => {
            const prevMap = new Map(prev.map(r => [`${r.code}-${r.market}`, r]));
            return items.map(w => ({ ...w, loading: true, data: prevMap.get(`${w.code}-${w.market}`)?.data }));
        });
        setRefreshing(true);

        const results: PromiseSettledResult<StockAnalysis>[] = [];
        const BATCH = 4;
        for (let i = 0; i < items.length; i += BATCH) {
            const batch = items.slice(i, i + BATCH);
            const batchResults = await Promise.allSettled(
                batch.map(w => fetchStockAnalyze(w.code, w.market))
            );
            results.push(...batchResults);
        }

        setRows(prev => items.map((w, i) => {
            const r = results[i];
            const existing = prev.find(p => p.code === w.code && p.market === w.market);
            if (r.status === 'fulfilled') {
                const d = r.value;
                return { ...w, loading: false, data: d.error ? undefined : d, error: d.error };
            }
            return { ...w, loading: false, data: existing?.data, error: String((r as PromiseRejectedResult).reason) };
        }));
        setRefreshing(false);
    }, []);

    // 초기 로드 + 탭 전환 시 localStorage 재동기화 + 데이터 갱신
    useEffect(() => {
        if (!isVisible) return;
        const saved = loadWatchlist();
        fetchAll(saved);
    }, [isVisible, fetchAll]);

    const persistAndFetch = (items: WatchItem[]) => {
        saveWatchlist(items);
        fetchAll(items);
    };

    // 종목 추가
    const handleAdd = () => {
        const code = addCode.trim().toUpperCase();
        if (!code) return;
        if (rows.some(r => r.code === code && r.market === addMarket)) { setAddCode(''); return; }
        const item: WatchItem = { code, market: addMarket, addedAt: new Date().toISOString() };
        const newItems = [...rows.map(r => ({ code: r.code, market: r.market, addedAt: r.addedAt })), item];
        setAddCode('');
        persistAndFetch(newItems);
    };

    // 종목 삭제
    const handleDelete = (code: string, mkt: Market) => {
        const key = `${code}-${mkt}`;
        const newItems = rows
            .filter(r => !(r.code === code && r.market === mkt))
            .map(r => ({ code: r.code, market: r.market, addedAt: r.addedAt }));
        saveWatchlist(newItems);
        setRows(prev => prev.filter(r => !(r.code === code && r.market === mkt)));
        setQuantities(prev => { const n = { ...prev }; delete n[key]; return n; });
        setBuyStates(prev => { const n = { ...prev }; delete n[key]; return n; });
    };

    // 전체 새로고침
    const handleRefresh = () => {
        fetchAll(rows.map(r => ({ code: r.code, market: r.market, addedAt: r.addedAt })));
    };

    // 수량 변경
    const handleQtyChange = (key: string, val: number) => {
        setQuantities(prev => ({ ...prev, [key]: Math.max(1, Math.floor(val)) }));
    };

    // 매수 실행
    const handleBuy = async (row: AnalysisRow) => {
        if (!row.data) return;
        const key = rowKey(row);
        const qty = quantities[key] ?? 1;
        setBuyStates(prev => ({ ...prev, [key]: 'loading' }));
        try {
            await paperTrading.addPosition({
                code: row.data.code,
                name: row.data.name,
                entry_price: row.data.current_price,
                quantity: qty,
            });
            setBuyStates(prev => ({ ...prev, [key]: 'success' }));
            // 2초 후 idle로 복귀
            setTimeout(() => setBuyStates(prev => ({ ...prev, [key]: 'idle' })), 2000);
        } catch {
            setBuyStates(prev => ({ ...prev, [key]: 'error' }));
            setTimeout(() => setBuyStates(prev => ({ ...prev, [key]: 'idle' })), 3000);
        }
    };

    // 정렬
    const handleSort = (k: SortKey) => {
        if (sortKey === k) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
        else { setSortKey(k); setSortDir('asc'); }
    };

    const sorted = [...rows].sort((a, b) => {
        const ad = a.data, bd = b.data;
        if (!ad && !bd) return 0;
        if (!ad) return 1;
        if (!bd) return -1;
        if (sortKey === 'code')        return sortDir === 'asc' ? a.code.localeCompare(b.code) : b.code.localeCompare(a.code);
        if (sortKey === 'signal')      return sortDir === 'asc'
            ? (ad.signal || '').localeCompare(bd.signal || '')
            : (bd.signal || '').localeCompare(ad.signal || '');
        const vals: Record<SortKey, number> = {
            code: 0, signal: 0,
            change_pct: ad.change_pct - bd.change_pct,
            vol_ratio:  ad.vol_ratio  - bd.vol_ratio,
            vs_ma20_pct: ad.vs_ma20_pct - bd.vs_ma20_pct,
            score: ad.score - bd.score,
        };
        return sortDir === 'asc' ? vals[sortKey] : -vals[sortKey];
    });

    const SortIcon = ({ k }: { k: SortKey }) => {
        if (sortKey !== k) return <span className="text-slate-600 ml-0.5">⇅</span>;
        return sortDir === 'asc'
            ? <ChevronUp size={12} className="inline ml-0.5 text-amber-400" />
            : <ChevronDown size={12} className="inline ml-0.5 text-amber-400" />;
    };

    const Th = ({ k, label, className = '' }: { k: SortKey; label: string; className?: string }) => (
        <th
            className={`px-3 py-2.5 text-center cursor-pointer select-none hover:text-white whitespace-nowrap ${className}`}
            onClick={() => handleSort(k)}
        >
            {label}<SortIcon k={k} />
        </th>
    );

    return (
        <div className="h-full flex flex-col gap-4 overflow-hidden">

            {/* ── 툴바 ─────────────────────────────────────────── */}
            <div className="bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 flex flex-wrap items-end gap-3 shrink-0">
                <div className="flex items-center gap-2">
                    <Star size={16} className="text-amber-400" />
                    <span className="text-sm font-semibold text-slate-200">관심종목</span>
                    <span className="text-xs text-slate-500">{rows.length}종목</span>
                </div>

                {/* 종목 추가 */}
                <div className="flex items-center gap-2 ml-4">
                    <div className="flex items-center gap-1 bg-slate-900 border border-slate-600 rounded-lg p-1">
                        {(['KR', 'US'] as Market[]).map(m => (
                            <button
                                key={m}
                                onClick={() => setAddMarket(m)}
                                className={`px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                                    addMarket === m
                                        ? m === 'KR' ? 'bg-blue-500/25 text-blue-400 ring-1 ring-blue-500/50' : 'bg-purple-500/25 text-purple-400 ring-1 ring-purple-500/50'
                                        : 'text-slate-500 hover:text-slate-300'
                                }`}
                            >
                                {m === 'KR' ? '🇰🇷 KR' : '🇺🇸 US'}
                            </button>
                        ))}
                    </div>
                    <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-600 rounded-lg px-2.5 py-1.5">
                        <input
                            type="text"
                            placeholder="종목코드 입력"
                            value={addCode}
                            onChange={e => setAddCode(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleAdd()}
                            className="w-32 bg-transparent text-sm text-slate-200 placeholder-slate-600 focus:outline-none"
                        />
                    </div>
                    <button
                        onClick={handleAdd}
                        disabled={!addCode.trim()}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-primary hover:bg-primary/80 disabled:opacity-40 rounded-lg text-sm font-semibold transition-colors border border-primary/60"
                    >
                        <Plus size={14} />
                        <span>추가</span>
                    </button>
                </div>

                {/* 새로고침 */}
                <div className="ml-auto flex items-center gap-2">
                    <button
                        onClick={handleRefresh}
                        disabled={refreshing || rows.length === 0}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 rounded-lg text-sm font-semibold text-slate-300 hover:text-slate-100 transition-colors border border-slate-600"
                    >
                        <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
                        <span>새로고침</span>
                    </button>
                </div>
            </div>

            {/* ── 그리드 ───────────────────────────────────────── */}
            <div className="flex-1 bg-slate-800 border border-slate-700 rounded-xl overflow-hidden flex flex-col min-h-0">
                {rows.length === 0 ? (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="text-center">
                            <Star size={40} className="mx-auto mb-3 text-slate-600" />
                            <p className="text-sm text-slate-500">관심종목을 추가하세요</p>
                            <p className="text-xs text-slate-600 mt-1">종목코드 입력 후 엔터 또는 추가 버튼</p>
                        </div>
                    </div>
                ) : (
                    <div className="overflow-auto flex-1">
                        <table className="w-full text-sm border-collapse">
                            <thead className="sticky top-0 bg-slate-950 z-10 shadow-md">
                                <tr className="text-xs font-bold text-slate-300 border-b-2 border-slate-700 divide-x divide-slate-700/50">
                                    <th className="px-3 py-2.5 text-center w-8">#</th>
                                    <Th k="code" label="종목" className="text-left min-w-[120px]" />
                                    <th className="px-3 py-2.5 text-center">시장</th>
                                    <th className="px-2 py-2.5 text-center min-w-[78px]">현재가</th>
                                    <Th k="change_pct" label="등락률" />
                                    <Th k="vol_ratio" label="거래량비율" />
                                    <th className="px-3 py-2.5 text-center">MA5대비</th>
                                    <Th k="vs_ma20_pct" label="MA20대비" />
                                    <th className="px-3 py-2.5 text-center">MA60대비</th>
                                    <th className="px-3 py-2.5 text-center whitespace-nowrap">52주신고가</th>
                                    <th className="px-3 py-2.5 text-center whitespace-nowrap">20일신고가</th>
                                    <Th k="score" label="신호점수" />
                                    <Th k="signal" label="신호" />
                                    <th className="px-3 py-2.5 text-center w-24">구매수량</th>
                                    <th className="px-3 py-2.5 text-center w-20">매수</th>
                                    <th className="px-3 py-2.5 text-center w-12">삭제</th>
                                </tr>
                            </thead>
                            <tbody>
                                {sorted.map((row, idx) => (
                                    <WatchRow
                                        key={rowKey(row)}
                                        row={row}
                                        idx={idx}
                                        quantity={quantities[rowKey(row)] ?? 1}
                                        buyState={buyStates[rowKey(row)] ?? 'idle'}
                                        onQtyChange={v => handleQtyChange(rowKey(row), v)}
                                        onBuy={() => handleBuy(row)}
                                        onDelete={() => handleDelete(row.code, row.market)}
                                        onNavigate={onNavigateToStock ? () => onNavigateToStock(row.code, row.market) : undefined}
                                    />
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}

// ── 행 컴포넌트 ───────────────────────────────────────────────

function WatchRow({ row, idx, quantity, buyState, onQtyChange, onBuy, onDelete, onNavigate }: {
    row: AnalysisRow;
    idx: number;
    quantity: number;
    buyState: BuyState;
    onQtyChange: (v: number) => void;
    onBuy: () => void;
    onDelete: () => void;
    onNavigate?: () => void;
}) {
    const d = row.data;
    const isEven = idx % 2 === 1;
    const zebraBg = isEven ? 'bg-slate-900/60' : 'bg-transparent';
    const TOTAL_COLS = 16;

    if (row.loading) {
        return (
            <tr className={`border-b border-slate-700/40 divide-x divide-slate-700/30 ${zebraBg}`}>
                <td className="px-3 py-2.5 text-right text-slate-500 text-xs">{idx + 1}</td>
                <td className="px-3 py-2.5 text-left">
                    <div className="font-semibold text-slate-200">{row.code}</div>
                </td>
                <td colSpan={TOTAL_COLS - 3} className="px-3 py-2.5 text-center">
                    <span className="text-xs text-slate-500 flex items-center justify-center gap-1.5">
                        <RefreshCw size={11} className="animate-spin" /> 로딩 중...
                    </span>
                </td>
                <td className="px-3 py-2.5 text-center">
                    <DeleteBtn onClick={onDelete} />
                </td>
            </tr>
        );
    }

    if (!d || row.error) {
        return (
            <tr className={`border-b border-slate-700/40 divide-x divide-slate-700/30 ${zebraBg}`}>
                <td className="px-3 py-2.5 text-right text-slate-500 text-xs">{idx + 1}</td>
                <td className="px-3 py-2.5 text-left">
                    <div className="font-semibold text-slate-200">{row.code}</div>
                </td>
                <td className="px-3 py-2.5 text-center">
                    <MarketBadge market={row.market} />
                </td>
                <td colSpan={TOTAL_COLS - 4} className="px-3 py-2.5 text-center">
                    <span className="text-xs text-red-400 flex items-center justify-center gap-1">
                        <AlertTriangle size={11} /> 데이터 조회 실패
                    </span>
                </td>
                <td className="px-3 py-2.5 text-center">
                    <DeleteBtn onClick={onDelete} />
                </td>
            </tr>
        );
    }

    const changePosColor = d.change_pct > 0 ? 'text-red-400' : d.change_pct < 0 ? 'text-blue-400' : 'text-slate-400';
    const signalColor = d.signal === 'BUY' ? 'bg-green-500/20 text-green-400 ring-1 ring-green-500/40'
        : d.chase_blocked ? 'bg-orange-500/20 text-orange-400 ring-1 ring-orange-500/40'
        : 'bg-slate-700 text-slate-400';
    const signalLabel = d.signal === 'BUY' ? '매수' : d.chase_blocked ? '추격차단' : '관망';
    const signalIcon = d.signal === 'BUY'
        ? <TrendingUp size={10} className="inline mr-0.5" />
        : d.chase_blocked ? <AlertTriangle size={10} className="inline mr-0.5" />
        : <Minus size={10} className="inline mr-0.5" />;

    // 매수 버튼 렌더
    const BuyButton = () => {
        if (buyState === 'loading') return (
            <button disabled className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-700 text-slate-400 opacity-60 whitespace-nowrap">
                <RefreshCw size={11} className="animate-spin" />
                <span>처리중</span>
            </button>
        );
        if (buyState === 'success') return (
            <button disabled className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-green-500/20 text-green-400 ring-1 ring-green-500/40 whitespace-nowrap">
                <Check size={11} />
                <span>완료</span>
            </button>
        );
        if (buyState === 'error') return (
            <button disabled className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-red-500/20 text-red-400 ring-1 ring-red-500/40 whitespace-nowrap">
                <X size={11} />
                <span>실패</span>
            </button>
        );
        return (
            <button
                onClick={onBuy}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-primary/90 hover:bg-primary text-white transition-colors shadow-sm whitespace-nowrap"
            >
                <ShoppingCart size={11} />
                <span>매수</span>
            </button>
        );
    };

    const MaPct = ({ val }: { val: number }) => {
        const color = val > 5 ? 'text-red-400' : val > 0 ? 'text-green-400' : val < -5 ? 'text-blue-300' : 'text-blue-400';
        const Icon = val >= 0 ? TrendingUp : TrendingDown;
        return (
            <span className={`text-xs font-mono flex items-center justify-center gap-0.5 ${color}`}>
                <Icon size={10} />{fmtPct(val)}
            </span>
        );
    };

    const VolBadge = ({ ratio }: { ratio: number }) => {
        const color = ratio >= 3 ? 'text-red-400 bg-red-500/10' : ratio >= 2 ? 'text-orange-400 bg-orange-500/10' : ratio >= 1.5 ? 'text-yellow-400 bg-yellow-500/10' : 'text-slate-400 bg-slate-700/40';
        return <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${color}`}>{fmtVolRatio(ratio)}</span>;
    };

    const HighBadge = ({ yes }: { yes: boolean }) => yes
        ? <span className="text-xs font-semibold text-amber-400 flex items-center justify-center gap-0.5"><CheckCircle size={11} /> 신고가</span>
        : <span className="text-xs text-slate-600">-</span>;

    const ScoreBadge = ({ score }: { score: number }) => {
        const color = score >= 70 ? 'text-green-400' : score >= 50 ? 'text-yellow-400' : 'text-slate-500';
        return (
            <div className="flex flex-col items-center gap-0.5">
                <span className={`text-xs font-bold font-mono ${color}`}>{score}</span>
                <div className="w-10 h-1 bg-slate-700 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${score >= 70 ? 'bg-green-400' : score >= 50 ? 'bg-yellow-400' : 'bg-slate-500'}`} style={{ width: `${Math.min(score, 100)}%` }} />
                </div>
            </div>
        );
    };

    return (
        <tr className={`border-b border-slate-700/40 divide-x divide-slate-700/30 transition-colors hover:bg-slate-700/20 ${zebraBg}`}>
            <td className="px-3 py-2.5 text-right text-slate-500 font-mono text-xs">{idx + 1}</td>

            {/* 종목 */}
            <td className="px-3 py-2.5 text-left">
                <div
                    className={`font-semibold text-slate-100 text-xs ${onNavigate ? 'cursor-pointer hover:text-blue-400 transition-colors' : ''}`}
                    onClick={onNavigate}
                    title={onNavigate ? '주식 분석 탭에서 보기' : undefined}
                >
                    {d.name}
                </div>
                <div className="text-xs text-slate-500 font-mono">{d.code}</div>
            </td>

            {/* 시장 */}
            <td className="px-3 py-2.5 text-center"><MarketBadge market={d.market} /></td>

            {/* 현재가 */}
            <td className="px-2 py-2.5 text-right">
                <div className="text-sm font-semibold font-mono text-slate-100">{fmtPrice(d.current_price, d.market)}</div>
                <div className="text-xs text-slate-500 font-mono">
                    H {fmtPrice(d.high, d.market)} / L {fmtPrice(d.low, d.market)}
                </div>
            </td>

            {/* 등락률 */}
            <td className="px-3 py-2.5 text-center">
                <span className={`text-sm font-bold font-mono ${changePosColor}`}>
                    {d.change_pct >= 0 ? '+' : ''}{d.change_pct.toFixed(2)}%
                </span>
            </td>

            {/* 거래량 비율 */}
            <td className="px-3 py-2.5 text-center"><VolBadge ratio={d.vol_ratio} /></td>

            {/* MA 대비 */}
            <td className="px-3 py-2.5 text-center"><MaPct val={d.vs_ma5_pct} /></td>
            <td className="px-3 py-2.5 text-center"><MaPct val={d.vs_ma20_pct} /></td>
            <td className="px-3 py-2.5 text-center"><MaPct val={d.vs_ma60_pct} /></td>

            {/* 신고가 */}
            <td className="px-3 py-2.5 text-center"><HighBadge yes={d.is_52w_high} /></td>
            <td className="px-3 py-2.5 text-center"><HighBadge yes={d.is_20d_high} /></td>

            {/* 신호 점수 */}
            <td className="px-3 py-2.5 text-center"><ScoreBadge score={d.score} /></td>

            {/* 신호 */}
            <td className="px-3 py-2.5 text-center">
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${signalColor}`}>
                    {signalIcon}{signalLabel}
                </span>
            </td>

            {/* 구매수량 */}
            <td className="px-3 py-2.5 text-center">
                <div className="flex items-center justify-center gap-1">
                    <button
                        onClick={() => onQtyChange(quantity - 1)}
                        className="w-5 h-5 flex items-center justify-center rounded bg-slate-700 hover:bg-slate-600 text-slate-400 hover:text-slate-200 text-xs font-bold transition-colors"
                    >−</button>
                    <input
                        type="number"
                        min={1}
                        value={quantity}
                        onChange={e => onQtyChange(Number(e.target.value))}
                        className="w-12 text-center bg-slate-900 border border-slate-600 rounded text-xs text-slate-100 font-mono py-0.5 focus:outline-none focus:border-primary"
                    />
                    <button
                        onClick={() => onQtyChange(quantity + 1)}
                        className="w-5 h-5 flex items-center justify-center rounded bg-slate-700 hover:bg-slate-600 text-slate-400 hover:text-slate-200 text-xs font-bold transition-colors"
                    >+</button>
                </div>
                {/* 예상 금액 */}
                <div className="text-[10px] text-slate-500 text-center mt-0.5 font-mono">
                    ≈ {fmtPrice(d.current_price * quantity, d.market)}
                </div>
            </td>

            {/* 매수 버튼 */}
            <td className="px-3 py-2.5 text-center">
                <BuyButton />
            </td>

            {/* 삭제 */}
            <td className="px-3 py-2.5 text-center">
                <DeleteBtn onClick={onDelete} />
            </td>
        </tr>
    );
}

function MarketBadge({ market }: { market: string }) {
    return (
        <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
            market === 'KR' ? 'bg-blue-500/15 text-blue-400' : 'bg-purple-500/15 text-purple-400'
        }`}>
            {market}
        </span>
    );
}

function DeleteBtn({ onClick }: { onClick: () => void }) {
    return (
        <button
            onClick={onClick}
            className="p-1 rounded hover:bg-red-500/20 text-slate-600 hover:text-red-400 transition-colors"
        >
            <Trash2 size={13} />
        </button>
    );
}
