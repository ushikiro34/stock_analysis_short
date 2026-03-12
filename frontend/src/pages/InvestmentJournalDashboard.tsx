import { useState, useCallback, useRef, useEffect } from 'react';
import {
    Search, ChevronLeft, ChevronRight, RefreshCw, RotateCcw,
    TrendingUp, TrendingDown, BookOpen, BarChart2, X, Loader2, Sparkles,
} from 'lucide-react';
import type { PaperTrade, JournalFilter } from '../lib/api';
import { paperTrading } from '../lib/api';
const API_BASE = 'http://localhost:8000';

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

// ── AI 분석 모달 ─────────────────────────────────────────────────

const SECTION_ICONS: Record<string, string> = {
    '1': '🏭', '2': '📰', '3': '🕯️', '4': '📉',
    '5': '📊', '6': '🔮', '7': '💡',
};

function parseAnalysisSections(text: string): { title: string; body: string }[] {
    const parts = text.split(/(?=### \d+\.)/).filter(Boolean);
    return parts.map(part => {
        const lines = part.trim().split('\n');
        const title = lines[0].replace(/^### /, '').trim();
        const body = lines.slice(1).join('\n').trim();
        return { title, body };
    });
}

function AnalysisModal({ trade, onClose }: { trade: PaperTrade; onClose: () => void }) {
    const [text, setText] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const abortRef = useRef<AbortController | null>(null);

    const isProfit = trade.profit_loss >= 0;
    const pnlColor = isProfit ? 'text-green-400' : 'text-red-400';

    // 마운트 즉시 스트리밍 시작
    useEffect(() => {
        const ctrl = new AbortController();
        abortRef.current = ctrl;

        (async () => {
            try {
                const res = await fetch(`${API_BASE}/paper/journal/${trade.id}/analyze`, {
                    signal: ctrl.signal,
                });
                if (!res.ok) {
                    const j = await res.json().catch(() => ({}));
                    setError(j.detail || `오류 ${res.status}`);
                    return;
                }
                const reader = res.body!.getReader();
                const dec = new TextDecoder();
                let buf = '';
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buf += dec.decode(value, { stream: true });
                    const lines = buf.split('\n');
                    buf = lines.pop() ?? '';
                    for (const line of lines) {
                        if (!line.startsWith('data: ')) continue;
                        const payload = line.slice(6).trim();
                        if (payload === '[DONE]') continue;
                        try {
                            const { text: t, error: e } = JSON.parse(payload);
                            if (e) { setError(e); return; }
                            if (t) setText(prev => prev + t);
                        } catch { /* ignore parse errors */ }
                    }
                }
            } catch (e: any) {
                if (e?.name !== 'AbortError') setError(String(e));
            } finally {
                setLoading(false);
            }
        })();

        return () => ctrl.abort();
    }, [trade.id]);

    const sections = parseAnalysisSections(text);
    const showRaw = sections.length === 0 && text;

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
            onClick={onClose}
        >
            <div
                className="relative flex flex-col bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden"
                style={{ width: '92vw', maxWidth: '1200px', height: '90vh' }}
                onClick={e => e.stopPropagation()}
            >
                {/* 헤더 */}
                <div className="shrink-0 flex items-start justify-between px-6 py-4 bg-slate-800/80 border-b border-slate-700">
                    <div className="flex items-center gap-4">
                        <div>
                            <div className="flex items-center gap-2">
                                <Sparkles size={18} className="text-amber-400" />
                                <span className="font-bold text-lg text-slate-100">AI 거래 분석</span>
                                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                                    trade.market === 'KR' ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'
                                }`}>{trade.market}</span>
                            </div>
                            <div className="text-sm text-slate-400 mt-0.5">
                                {trade.name} <span className="text-slate-600 font-mono">({trade.code})</span>
                            </div>
                        </div>
                    </div>
                    {/* 거래 요약 배지 */}
                    <div className="flex items-center gap-6 mr-10">
                        <div className="text-center">
                            <div className="text-[10px] text-slate-500 mb-0.5">매수가</div>
                            <div className="text-sm font-mono text-slate-200">{trade.entry_price.toLocaleString()}원</div>
                        </div>
                        <div className="text-slate-700 text-lg">→</div>
                        <div className="text-center">
                            <div className="text-[10px] text-slate-500 mb-0.5">매도가</div>
                            <div className="text-sm font-mono text-slate-200">{trade.exit_price?.toLocaleString() ?? '-'}원</div>
                        </div>
                        <div className={`text-center px-3 py-1.5 rounded-lg ${isProfit ? 'bg-green-500/15 border border-green-500/30' : 'bg-red-500/15 border border-red-500/30'}`}>
                            <div className="text-[10px] text-slate-500 mb-0.5">손익</div>
                            <div className={`text-sm font-bold font-mono ${pnlColor}`}>
                                {isProfit ? '+' : ''}{trade.profit_loss.toLocaleString()}원
                            </div>
                            <div className={`text-xs ${pnlColor}`}>
                                {isProfit ? '+' : ''}{trade.profit_loss_pct.toFixed(2)}%
                            </div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-slate-500 mb-0.5">청산</div>
                            <div className="text-sm text-slate-300">{fmtReason(trade.exit_reason)}</div>
                        </div>
                    </div>
                    <button onClick={onClose} className="absolute top-4 right-4 text-slate-500 hover:text-slate-200 transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {/* 본문 */}
                <div className="flex-1 overflow-y-auto px-6 py-5">
                    {error ? (
                        <div className="flex items-center justify-center h-full">
                            <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/30 rounded-xl px-6 py-4">
                                {error}
                            </div>
                        </div>
                    ) : sections.length > 0 ? (
                        <div className="grid grid-cols-2 gap-4">
                            {sections.map(({ title, body }, i) => {
                                const numMatch = title.match(/^(\d+)/);
                                const num = numMatch?.[1] ?? '';
                                const icon = SECTION_ICONS[num] ?? '📌';
                                const isLastOdd = sections.length % 2 === 1 && i === sections.length - 1;
                                return (
                                    <div
                                        key={i}
                                        className={`bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 ${isLastOdd ? 'col-span-2' : ''}`}
                                    >
                                        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-700/50">
                                            <span className="text-base">{icon}</span>
                                            <h3 className="text-sm font-bold text-slate-200">{title.replace(/^\d+\.\s*/, '').trim() || title}</h3>
                                        </div>
                                        <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{body}</p>
                                    </div>
                                );
                            })}
                            {/* 스트리밍 중 마지막 섹션 뒤에 커서 표시 */}
                            {loading && (
                                <div className="col-span-2 flex items-center gap-2 text-slate-500 text-sm py-2">
                                    <Loader2 size={14} className="animate-spin text-amber-400" />
                                    <span className="text-amber-400/70">분석 중...</span>
                                </div>
                            )}
                        </div>
                    ) : showRaw ? (
                        <pre className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{text}</pre>
                    ) : loading ? (
                        <div className="flex flex-col items-center justify-center h-full gap-4">
                            <Loader2 size={32} className="animate-spin text-amber-400" />
                            <div className="text-slate-400 text-sm">AI가 거래를 분석하는 중...</div>
                            <div className="text-slate-600 text-xs">Groq · Llama-3.3-70b powered</div>
                        </div>
                    ) : null}
                </div>
            </div>
        </div>
    );
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

    const [analyzingTrade, setAnalyzingTrade] = useState<PaperTrade | null>(null);
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
        <>
        {analyzingTrade && (
            <AnalysisModal trade={analyzingTrade} onClose={() => setAnalyzingTrade(null)} />
        )}
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
                                            <td
                                                className="px-3 py-2 text-left cursor-pointer group/name"
                                                onClick={() => setAnalyzingTrade(t)}
                                                title="AI 분석 보기"
                                            >
                                                <div className="flex items-center gap-1.5">
                                                    <span className="font-semibold text-slate-100 group-hover/name:text-amber-300 transition-colors">
                                                        {t.name || t.code}
                                                    </span>
                                                    <Sparkles size={11} className="text-slate-600 group-hover/name:text-amber-400 transition-colors shrink-0" />
                                                </div>
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
        </>
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
