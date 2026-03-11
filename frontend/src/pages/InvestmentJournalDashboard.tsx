import { useState, useCallback, useRef } from 'react';
import {
    Search, ChevronLeft, ChevronRight, RefreshCw, RotateCcw,
    TrendingUp, TrendingDown, BookOpen, BarChart2,
} from 'lucide-react';
import type { PaperTrade, JournalFilter } from '../lib/api';
import { paperTrading } from '../lib/api';

// ── 유틸 ────────────────────────────────────────────────────────

function fmtDate(iso: string | null): string {
    if (!iso) return '-';
    const d = new Date(iso);
    return d.toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' })
        + ' '
        + d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
}

function fmtPrice(n: number | null, market = 'KR'): string {
    if (n == null) return '-';
    return market === 'US'
        ? `$${n.toLocaleString(undefined, { minimumFractionDigits: 2 })}`
        : `${n.toLocaleString()}원`;
}

function fmtPnl(n: number, market = 'KR'): string {
    const sign = n >= 0 ? '+' : '';
    return market === 'US'
        ? `${sign}$${Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2 })}`
        : `${sign}${n.toLocaleString()}원`;
}

function todayStr(): string {
    return new Date().toISOString().slice(0, 10);
}

function addDays(dateStr: string, delta: number): string {
    const d = new Date(dateStr);
    d.setDate(d.getDate() + delta);
    return d.toISOString().slice(0, 10);
}

// 청산 사유 한글화
function fmtReason(r: string | null): string {
    if (!r) return '-';
    const map: Record<string, string> = {
        take_profit: '익절',
        stop_loss: '손절',
        time_based: '시간청산',
        manual: '수동',
        수동청산: '수동',
        일괄청산: '일괄',
    };
    return map[r] ?? r;
}

// ── 컴포넌트 ────────────────────────────────────────────────────

type SortKey = 'exit_time' | 'entry_time' | 'profit_loss' | 'profit_loss_pct';
type SortDir = 'asc' | 'desc';

export default function InvestmentJournalDashboard() {
    // 필터 상태
    const [dateFrom, setDateFrom] = useState(addDays(todayStr(), -30));
    const [dateTo, setDateTo] = useState(todayStr());
    const [codeInput, setCodeInput] = useState('');
    const [profitType, setProfitType] = useState<'all' | 'profit' | 'loss'>('all');

    // 데이터 상태
    const [trades, setTrades] = useState<PaperTrade[]>([]);
    const [total, setTotal] = useState(0);
    const [totalPnl, setTotalPnl] = useState(0);
    const [profitCount, setProfitCount] = useState(0);
    const [profitAmount, setProfitAmount] = useState(0);
    const [lossCount, setLossCount] = useState(0);
    const [lossAmount, setLossAmount] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [searched, setSearched] = useState(false);

    // 정렬 상태
    const [sortKey, setSortKey] = useState<SortKey>('exit_time');
    const [sortDir, setSortDir] = useState<SortDir>('desc');

    const codeRef = useRef<HTMLInputElement>(null);

    const fetchJournal = useCallback(async (filter: JournalFilter) => {
        setLoading(true);
        setError(null);
        try {
            const res = await paperTrading.getJournal(filter);
            setTrades(res.trades);
            setTotal(res.total);
            setTotalPnl(res.total_pnl);
            setProfitCount(res.profit_count);
            setProfitAmount(res.profit_amount);
            setLossCount(res.loss_count);
            setLossAmount(res.loss_amount);
            setSearched(true);
        } catch (e) {
            setError(e instanceof Error ? e.message : '조회 실패');
        } finally {
            setLoading(false);
        }
    }, []);

    const handleSearch = () => {
        fetchJournal({
            date_from: dateFrom,
            date_to: dateTo,
            code: codeInput.trim() || undefined,
            profit_type: profitType,
        });
    };

    // 날짜 이동: from/to 동시에 이동
    const shiftDate = (delta: number) => {
        setDateFrom(prev => addDays(prev, delta));
        setDateTo(prev => addDays(prev, delta));
    };

    // 정렬 토글
    const handleSort = (key: SortKey) => {
        if (sortKey === key) {
            setSortDir(d => d === 'asc' ? 'desc' : 'asc');
        } else {
            setSortKey(key);
            setSortDir('desc');
        }
    };

    const sortedTrades = [...trades].sort((a, b) => {
        let av: number, bv: number;
        if (sortKey === 'exit_time') {
            av = a.exit_time ? new Date(a.exit_time).getTime() : 0;
            bv = b.exit_time ? new Date(b.exit_time).getTime() : 0;
        } else if (sortKey === 'entry_time') {
            av = a.entry_time ? new Date(a.entry_time).getTime() : 0;
            bv = b.entry_time ? new Date(b.entry_time).getTime() : 0;
        } else {
            av = (a as Record<string, number>)[sortKey] ?? 0;
            bv = (b as Record<string, number>)[sortKey] ?? 0;
        }
        return sortDir === 'asc' ? av - bv : bv - av;
    });

    const SortIcon = ({ k }: { k: SortKey }) => (
        <span className="ml-1 text-slate-500">
            {sortKey === k ? (sortDir === 'asc' ? '▲' : '▼') : '⇅'}
        </span>
    );

    const handleReset = () => {
        setDateFrom(addDays(todayStr(), -30));
        setDateTo(todayStr());
        setCodeInput('');
        setProfitType('all');
        setTrades([]);
        setTotal(0);
        setTotalPnl(0);
        setProfitCount(0);
        setProfitAmount(0);
        setLossCount(0);
        setLossAmount(0);
        setSearched(false);
        setError(null);
    };

    const winRate = total > 0 ? ((profitCount / total) * 100).toFixed(1) : '0.0';

    return (
        <div className="h-full flex flex-col gap-4 overflow-hidden">

            {/* ── 필터 바 ─────────────────────────────────────────── */}
            <div className="bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 flex flex-wrap items-end gap-3 shrink-0">
                {/* 조회 기간 */}
                <div className="flex flex-col gap-1">
                    <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider px-1">조회기간</span>
                    <div className="flex items-center gap-1 bg-slate-900 border border-slate-600 rounded-lg px-2 py-1.5">
                        <button
                            onClick={() => shiftDate(-1)}
                            className="p-0.5 rounded hover:bg-slate-700 text-slate-400 hover:text-amber-400 transition-colors"
                            title="하루 이전"
                        >
                            <ChevronLeft size={15} />
                        </button>
                        <input
                            type="date"
                            value={dateFrom}
                            onChange={e => setDateFrom(e.target.value)}
                            className="bg-transparent text-sm text-slate-200 focus:outline-none w-32"
                        />
                        <span className="text-slate-600 text-xs px-0.5">~</span>
                        <input
                            type="date"
                            value={dateTo}
                            onChange={e => setDateTo(e.target.value)}
                            className="bg-transparent text-sm text-slate-200 focus:outline-none w-32"
                        />
                        <button
                            onClick={() => shiftDate(1)}
                            className="p-0.5 rounded hover:bg-slate-700 text-slate-400 hover:text-amber-400 transition-colors"
                            title="하루 이후"
                        >
                            <ChevronRight size={15} />
                        </button>
                    </div>
                </div>

                {/* 투자 종목 */}
                <div className="flex flex-col gap-1">
                    <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider px-1">투자종목</span>
                    <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-600 rounded-lg px-2.5 py-1.5">
                        <Search size={13} className="text-slate-500 shrink-0" />
                        <input
                            ref={codeRef}
                            type="text"
                            placeholder="코드 / 종목명"
                            value={codeInput}
                            onChange={e => setCodeInput(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleSearch()}
                            className="w-28 bg-transparent text-sm text-slate-200 placeholder-slate-600 focus:outline-none"
                        />
                    </div>
                </div>

                {/* 손익 구분 */}
                <div className="flex flex-col gap-1">
                    <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider px-1">손익구분</span>
                    <div className="flex items-center gap-1 bg-slate-900 border border-slate-600 rounded-lg p-1">
                        {([
                            { val: 'all',    label: '전체',  active: 'bg-slate-600 text-white' },
                            { val: 'profit', label: '수익',  active: 'bg-green-500/25 text-green-400 ring-1 ring-green-500/50' },
                            { val: 'loss',   label: '손실',  active: 'bg-red-500/25 text-red-400 ring-1 ring-red-500/50' },
                        ] as const).map(({ val, label, active }) => (
                            <button
                                key={val}
                                onClick={() => setProfitType(val)}
                                className={`px-3 py-1 rounded text-xs font-semibold transition-all ${
                                    profitType === val
                                        ? active
                                        : 'text-slate-500 hover:text-slate-300'
                                }`}
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* 검색 버튼 */}
                <div className="flex flex-col gap-1">
                    <span className="text-[10px] font-semibold text-transparent uppercase tracking-wider px-1 select-none">검색</span>
                    <button
                        onClick={handleSearch}
                        disabled={loading}
                        className="flex items-center gap-2 px-5 py-1.5 bg-primary hover:bg-primary/80 disabled:opacity-50 rounded-lg text-sm font-semibold transition-colors border border-primary/60 shadow-sm shadow-primary/20"
                    >
                        {loading
                            ? <RefreshCw size={14} className="animate-spin" />
                            : <Search size={14} />
                        }
                        <span>검색</span>
                    </button>
                </div>

                {/* 초기화 버튼 — 우측 끝 */}
                <div className="flex flex-col gap-1 ml-auto">
                    <span className="text-[10px] font-semibold text-transparent uppercase tracking-wider px-1 select-none">초기화</span>
                    <button
                        onClick={handleReset}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm font-semibold text-slate-300 hover:text-slate-100 transition-colors border border-slate-600"
                    >
                        <RotateCcw size={13} />
                        <span>초기화</span>
                    </button>
                </div>
            </div>

            {/* ── 요약 카드 ────────────────────────────────────────── */}
            {searched && (
                <div className="grid grid-cols-5 gap-3 shrink-0">
                    <SummaryCard
                        label="총 거래수"
                        value={`${total}건`}
                        sub={`승률 ${winRate}%`}
                        color="text-slate-200"
                        icon={<BarChart2 size={16} className="text-slate-400" />}
                    />
                    <SummaryCard
                        label="수익 거래"
                        value={`${profitCount}건`}
                        sub={total > 0 ? `${((profitCount / total) * 100).toFixed(1)}%` : '-'}
                        color="text-green-400"
                        icon={<TrendingUp size={16} className="text-green-400" />}
                    />
                    <SummaryCard
                        label="손실 거래"
                        value={`${lossCount}건`}
                        sub={total > 0 ? `${((lossCount / total) * 100).toFixed(1)}%` : '-'}
                        color="text-red-400"
                        icon={<TrendingDown size={16} className="text-red-400" />}
                    />
                    {/* 총 손익금액 — 수익합계 / 손실합계 분리 표시 */}
                    <div className="bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 flex items-center gap-3">
                        <div className="shrink-0">
                            <BarChart2 size={16} className="text-amber-400" />
                        </div>
                        <div className="min-w-0 flex-1">
                            <p className="text-xs text-slate-500 mb-1">총 손익금액</p>
                            <div className="flex items-center justify-between">
                                <span className="text-xs text-slate-500">수익</span>
                                <span className="text-sm font-bold text-green-400 font-mono">
                                    +{profitAmount.toLocaleString()}원
                                </span>
                            </div>
                            <div className="flex items-center justify-between mt-0.5">
                                <span className="text-xs text-slate-500">손실</span>
                                <span className="text-sm font-bold text-red-400 font-mono">
                                    {lossAmount.toLocaleString()}원
                                </span>
                            </div>
                        </div>
                    </div>
                    <SummaryCard
                        label="순 손익"
                        value={fmtPnl(totalPnl)}
                        sub={totalPnl >= 0 ? '수익' : '손실'}
                        color={totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}
                        icon={totalPnl >= 0
                            ? <TrendingUp size={16} className="text-green-400" />
                            : <TrendingDown size={16} className="text-red-400" />
                        }
                    />
                </div>
            )}

            {/* ── 그리드 테이블 ────────────────────────────────────── */}
            <div className="flex-1 bg-slate-800 border border-slate-700 rounded-xl overflow-hidden flex flex-col min-h-0">
                {!searched ? (
                    <div className="flex-1 flex items-center justify-center text-slate-500">
                        <div className="text-center">
                            <BookOpen size={40} className="mx-auto mb-3 text-slate-600" />
                            <p className="text-sm">날짜 범위와 조건을 설정 후 검색하세요</p>
                        </div>
                    </div>
                ) : error ? (
                    <div className="flex-1 flex items-center justify-center text-red-400 text-sm">{error}</div>
                ) : sortedTrades.length === 0 ? (
                    <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
                        조건에 맞는 거래 내역이 없습니다
                    </div>
                ) : (
                    <div className="overflow-auto flex-1">
                        <table className="w-full text-sm border-collapse">
                            <thead className="sticky top-0 bg-slate-950 z-10 shadow-md">
                                <tr className="text-xs font-bold text-slate-300 border-b-2 border-slate-700 divide-x divide-slate-700/50">
                                    <th className="px-3 py-2.5 text-center w-10">#</th>
                                    <th className="px-3 py-2.5 text-center">종목</th>
                                    <th className="px-3 py-2.5 text-center">시장</th>
                                    <th
                                        className="px-3 py-2.5 text-center cursor-pointer hover:text-white select-none"
                                        onClick={() => handleSort('entry_time')}
                                    >
                                        매수시간 <SortIcon k="entry_time" />
                                    </th>
                                    <th
                                        className="px-3 py-2.5 text-center cursor-pointer hover:text-white select-none"
                                        onClick={() => handleSort('exit_time')}
                                    >
                                        매도시간 <SortIcon k="exit_time" />
                                    </th>
                                    <th className="px-3 py-2.5 text-center">매수가</th>
                                    <th className="px-3 py-2.5 text-center">매도가</th>
                                    <th className="px-3 py-2.5 text-center">수량</th>
                                    <th
                                        className="px-3 py-2.5 text-center cursor-pointer hover:text-white select-none"
                                        onClick={() => handleSort('profit_loss')}
                                    >
                                        손익금액 <SortIcon k="profit_loss" />
                                    </th>
                                    <th
                                        className="px-3 py-2.5 text-center cursor-pointer hover:text-white select-none"
                                        onClick={() => handleSort('profit_loss_pct')}
                                    >
                                        손익률 <SortIcon k="profit_loss_pct" />
                                    </th>
                                    <th className="px-3 py-2.5 text-center">청산 사유</th>
                                </tr>
                            </thead>
                            <tbody>
                                {sortedTrades.map((t, idx) => {
                                    const isProfit = t.profit_loss > 0;
                                    const isBreak = t.profit_loss === 0;
                                    const pnlColor = isProfit ? 'text-green-400' : isBreak ? 'text-slate-400' : 'text-red-400';
                                    const isEven = idx % 2 === 1;
                                    // 짝수행(2,4,6...): 약간 밝은 배경 / 홀수행: 기본
                                    const zebraBg = isEven ? 'bg-slate-900/60' : 'bg-transparent';
                                    const hoverBg = isProfit
                                        ? 'hover:bg-green-500/10'
                                        : isBreak ? 'hover:bg-slate-700/40'
                                        : 'hover:bg-red-500/10';
                                    return (
                                        <tr
                                            key={t.id}
                                            className={`border-b border-slate-700/40 divide-x divide-slate-700/30 transition-colors ${zebraBg} ${hoverBg}`}
                                        >
                                            <td className="px-3 py-2 text-right text-slate-500 font-mono text-xs">{idx + 1}</td>
                                            <td className="px-3 py-2 text-left">
                                                <div className="font-semibold text-slate-100">{t.name || t.code}</div>
                                                <div className="text-xs text-slate-500 font-mono">{t.code}</div>
                                            </td>
                                            <td className="px-3 py-2 text-center">
                                                <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                                                    t.market === 'KR'
                                                        ? 'bg-blue-500/15 text-blue-400'
                                                        : 'bg-purple-500/15 text-purple-400'
                                                }`}>
                                                    {t.market}
                                                </span>
                                            </td>
                                            <td className="px-3 py-2 text-right text-slate-400 text-xs font-mono">
                                                {fmtDate(t.entry_time)}
                                            </td>
                                            <td className="px-3 py-2 text-right text-slate-400 text-xs font-mono">
                                                {fmtDate(t.exit_time)}
                                            </td>
                                            <td className="px-3 py-2 text-right text-slate-300 font-mono text-xs">
                                                {fmtPrice(t.entry_price, t.market)}
                                            </td>
                                            <td className="px-3 py-2 text-right text-slate-300 font-mono text-xs">
                                                {fmtPrice(t.exit_price, t.market)}
                                            </td>
                                            <td className="px-3 py-2 text-right text-slate-400 text-xs">
                                                {t.quantity.toLocaleString()}주
                                            </td>
                                            <td className={`px-3 py-2 text-right font-semibold font-mono text-xs ${pnlColor}`}>
                                                {fmtPnl(t.profit_loss, t.market)}
                                            </td>
                                            <td className={`px-3 py-2 text-right font-semibold text-xs ${pnlColor}`}>
                                                {t.profit_loss >= 0 ? '+' : ''}
                                                {t.profit_loss_pct.toFixed(2)}%
                                            </td>
                                            <td className="px-3 py-2 text-center">
                                                <span className={`text-xs px-2 py-0.5 rounded-full ${
                                                    t.exit_reason === 'take_profit'
                                                        ? 'bg-green-500/15 text-green-400'
                                                    : t.exit_reason === 'stop_loss'
                                                        ? 'bg-red-500/15 text-red-400'
                                                    : 'bg-slate-700 text-slate-400'
                                                }`}>
                                                    {fmtReason(t.exit_reason)}
                                                </span>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}

// ── 요약 카드 서브컴포넌트 ───────────────────────────────────────

function SummaryCard({
    label, value, sub, color, icon,
}: {
    label: string;
    value: string;
    sub: string;
    color: string;
    icon: React.ReactNode;
}) {
    return (
        <div className="bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 flex items-center gap-3">
            <div className="shrink-0">{icon}</div>
            <div className="min-w-0">
                <p className="text-xs text-slate-500 mb-0.5">{label}</p>
                <p className={`text-lg font-bold ${color} leading-tight`}>{value}</p>
                <p className="text-xs text-slate-500">{sub}</p>
            </div>
        </div>
    );
}
