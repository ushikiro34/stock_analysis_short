import { useState, useEffect, useCallback, useRef } from 'react';
import { PlayCircle, StopCircle, RotateCcw, TrendingUp, TrendingDown, DollarSign, Activity, Clock, AlertCircle, Loader2, Timer, X, Info, Plus, Search } from 'lucide-react';
import { createChart, ColorType, LineStyle } from 'lightweight-charts';
import { paperTrading, type PaperStatus, type PaperPosition, type PaperTrade, type PaperHistoryPoint, type PaperStartConfig } from '../lib/api';

const REFRESH_INTERVAL = 30_000; // 30초

const DEFAULT_CONFIG: PaperStartConfig = {
    initial_capital: 10_000_000,
    market: 'KR',
    strategy: 'combined',
    min_score: 65,
    max_positions: 3,
    position_size_pct: 0.3,
};

const fmtKRW = (v: number) => v.toLocaleString('ko-KR') + '원';
const fmtPct = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;

function PnlBadge({ pct }: { pct: number }) {
    const color = pct > 0 ? 'text-green-400' : pct < 0 ? 'text-red-400' : 'text-slate-400';
    return <span className={`font-bold ${color}`}>{fmtPct(pct)}</span>;
}

function TradeDetailModal({ trade, onClose }: { trade: PaperTrade; onClose: () => void }) {
    const totalBuy = trade.entry_price * trade.quantity;
    const totalSell = trade.exit_price != null ? trade.exit_price * trade.quantity : null;
    const isProfit = trade.profit_loss >= 0;

    const exitLabel = (() => {
        if (!trade.exit_reason) return '청산가';
        if (trade.exit_reason === 'fixed_stop_loss' || trade.exit_reason === 'trailing_stop') return '손절가';
        if (trade.exit_reason.includes('익절')) return '익절가';
        return '청산가';
    })();

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={onClose}
        >
            <div
                className="relative w-[480px] bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl p-6"
                onClick={e => e.stopPropagation()}
            >
                {/* 헤더 */}
                <div className="flex items-start justify-between mb-5">
                    <div>
                        <div className="text-lg font-bold">{trade.name}</div>
                        <div className="text-sm text-slate-400 mt-0.5">
                            {trade.code} &middot; {trade.market}
                            {trade.exit_reason && (
                                <span className="ml-2">
                                    <ExitReasonLabel reason={trade.exit_reason} />
                                </span>
                            )}
                        </div>
                    </div>
                    <button onClick={onClose} className="text-slate-500 hover:text-slate-200 transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {/* 손익 배지 */}
                <div className={`rounded-xl p-4 mb-5 text-center ${isProfit ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'}`}>
                    <div className={`text-3xl font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                        {isProfit ? '+' : ''}{trade.profit_loss.toLocaleString('ko-KR')}원
                    </div>
                    <div className={`text-sm mt-1 ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                        {isProfit ? '+' : ''}{trade.profit_loss_pct.toFixed(2)}%
                    </div>
                </div>

                {/* 상세 정보 그리드 */}
                <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="bg-slate-800/60 rounded-lg p-3">
                        <div className="text-xs text-slate-500 mb-1">시작 시간</div>
                        <div className="font-mono text-slate-200 text-xs">
                            {trade.entry_time ? new Date(trade.entry_time).toLocaleString('ko-KR') : '-'}
                        </div>
                    </div>
                    <div className="bg-slate-800/60 rounded-lg p-3">
                        <div className="text-xs text-slate-500 mb-1">종료 시간</div>
                        <div className="font-mono text-slate-200 text-xs">
                            {trade.exit_time ? new Date(trade.exit_time).toLocaleString('ko-KR') : '-'}
                        </div>
                    </div>
                    <div className="bg-slate-800/60 rounded-lg p-3">
                        <div className="text-xs text-slate-500 mb-1">1주당 매입가</div>
                        <div className="font-bold text-blue-300">{trade.entry_price.toLocaleString('ko-KR')}원</div>
                    </div>
                    <div className="bg-slate-800/60 rounded-lg p-3">
                        <div className="text-xs text-slate-500 mb-1">1주당 {exitLabel}</div>
                        <div className={`font-bold ${isProfit ? 'text-green-300' : 'text-red-300'}`}>
                            {trade.exit_price != null ? trade.exit_price.toLocaleString('ko-KR') + '원' : '-'}
                        </div>
                    </div>
                    <div className="bg-slate-800/60 rounded-lg p-3">
                        <div className="text-xs text-slate-500 mb-1">총 주식 수</div>
                        <div className="font-bold text-slate-200">{trade.quantity.toLocaleString('ko-KR')}주</div>
                    </div>
                    <div className="bg-slate-800/60 rounded-lg p-3">
                        <div className="text-xs text-slate-500 mb-1">총 매입가</div>
                        <div className="font-bold text-slate-200">{totalBuy.toLocaleString('ko-KR')}원</div>
                    </div>
                    <div className="bg-slate-800/60 rounded-lg p-3 col-span-2">
                        <div className="text-xs text-slate-500 mb-1">총 판매가</div>
                        <div className={`font-bold text-lg ${isProfit ? 'text-green-300' : 'text-red-300'}`}>
                            {totalSell != null ? totalSell.toLocaleString('ko-KR') + '원' : '-'}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

function ExitReasonLabel({ reason }: { reason: string | null }) {
    if (!reason) return null;
    const map: Record<string, { label: string; color: string }> = {
        '1차 익절 +3%':  { label: '1차 +3%',  color: 'text-green-400' },
        '2차 익절 +7%':  { label: '2차 +7%',  color: 'text-green-400' },
        '3차 익절 +15%': { label: '3차 +15%', color: 'text-green-300' },
        fixed_stop_loss: { label: '손절',      color: 'text-red-400' },
        trailing_stop:   { label: '트레일링',  color: 'text-orange-400' },
        수동청산:         { label: '수동청산',  color: 'text-yellow-400' },
        일괄청산:         { label: '일괄청산',  color: 'text-orange-300' },
    };
    const info = map[reason] ?? { label: reason, color: 'text-slate-400' };
    return <span className={`text-xs font-semibold ${info.color}`}>{info.label}</span>;
}

function Stopwatch({ startedAt, elapsedSeconds }: { startedAt: string | null; elapsedSeconds: number }) {
    // extra: 현재 구간에서 추가된 실시간 초 (실행 중에만 증가)
    const [extra, setExtra] = useState(0);

    useEffect(() => {
        if (!startedAt) {
            setExtra(0);
            return;
        }
        const origin = new Date(startedAt).getTime();
        const update = () => setExtra(Math.max(0, Math.floor((Date.now() - origin) / 1000)));
        update();
        const id = setInterval(update, 1000);
        return () => clearInterval(id);
    }, [startedAt]);

    const total = elapsedSeconds + extra;
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    const fmt = (n: number) => String(n).padStart(2, '0');
    const active = !!startedAt;

    return (
        <div className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg">
            <Timer size={14} className={active ? 'text-cyan-400' : 'text-slate-500'} />
            <span className={`font-mono text-sm tracking-widest ${active ? 'text-cyan-300' : 'text-slate-400'}`}>
                {fmt(h)}:{fmt(m)}:{fmt(s)}
            </span>
        </div>
    );
}

export default function PaperTradingDashboard({ onNavigateToStock }: { onNavigateToStock?: (name: string) => void }) {
    const [status, setStatus] = useState<PaperStatus | null>(null);
    const [positions, setPositions] = useState<PaperPosition[]>([]);
    const [trades, setTrades] = useState<PaperTrade[]>([]);
    const [history, setHistory] = useState<PaperHistoryPoint[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [config, setConfig] = useState<PaperStartConfig>(DEFAULT_CONFIG);
    const [selectedTrade, setSelectedTrade] = useState<PaperTrade | null>(null);

    const fetchAll = useCallback(async () => {
        try {
            const [s, p, t, h] = await Promise.all([
                paperTrading.getStatus(),
                paperTrading.getPositions(),
                paperTrading.getTrades(30),
                paperTrading.getHistory(200),
            ]);
            setStatus(s);
            setPositions(p);
            setTrades(t);
            setHistory(h);
            setError(null);
        } catch {
            setError('서버에 연결할 수 없습니다');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAll();
        const id = setInterval(fetchAll, REFRESH_INTERVAL);
        return () => clearInterval(id);
    }, [fetchAll]);

    const handleStart = async () => {
        setActionLoading(true);
        try {
            await paperTrading.start(config);
            await fetchAll();
        } catch (e: any) {
            setError(e?.message || '시작 실패');
        } finally {
            setActionLoading(false);
        }
    };

    const handleStop = async () => {
        setActionLoading(true);
        try {
            await paperTrading.stop();
            await fetchAll();
        } finally {
            setActionLoading(false);
        }
    };

    const handleReset = async () => {
        if (!confirm('모든 거래 내역과 포지션이 삭제됩니다. 초기화할까요?')) return;
        setActionLoading(true);
        try {
            await paperTrading.reset();
            await fetchAll();
        } finally {
            setActionLoading(false);
        }
    };

    const [closingCode, setClosingCode] = useState<string | null>(null);
    const [closingAll, setClosingAll] = useState(false);

    const handleCloseAll = async () => {
        if (positions.length === 0) return;
        if (!confirm(`보유 중인 포지션 ${positions.length}개를 전체 청산할까요?`)) return;
        setClosingAll(true);
        try {
            await paperTrading.closeAllPositions();
            await fetchAll();
        } catch (e: any) {
            setError(e?.message || '일괄청산 실패');
        } finally {
            setClosingAll(false);
        }
    };

    // ── 수동 포지션 추가 ────────────────────────────────────
    const [showAddForm, setShowAddForm] = useState(false);
    const [addForm, setAddForm] = useState({ code: '', name: '', entry_price: '', quantity: '' });
    const [addLoading, setAddLoading] = useState(false);
    const [addError, setAddError] = useState<string | null>(null);

    const handleAddPosition = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!addForm.code || !addForm.entry_price) return;
        setAddLoading(true);
        setAddError(null);
        try {
            await paperTrading.addPosition({
                code: addForm.code.trim(),
                name: addForm.name.trim() || undefined,
                entry_price: parseFloat(addForm.entry_price),
                quantity: addForm.quantity ? parseInt(addForm.quantity) : 0,
            });
            setAddForm({ code: '', name: '', entry_price: '', quantity: '' });
            setShowAddForm(false);
            await fetchAll();
        } catch (e: any) {
            setAddError(e?.message || '추가 실패');
        } finally {
            setAddLoading(false);
        }
    };

    const handleClosePosition = async (code: string, name: string) => {
        if (!confirm(`[${name}] 포지션을 지금 즉시 수동 청산할까요?`)) return;
        setClosingCode(code);
        try {
            await paperTrading.closePosition(code);
            await fetchAll();
        } catch (e: any) {
            setError(e?.message || '청산 실패');
        } finally {
            setClosingCode(null);
        }
    };

    // ── 포트폴리오 차트 (lightweight-charts) ───────────────────
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<ReturnType<typeof createChart> | null>(null);

    useEffect(() => {
        if (!chartContainerRef.current || history.length < 2) return;

        // 이전 차트 제거
        if (chartRef.current) {
            chartRef.current.remove();
            chartRef.current = null;
        }

        const chart = createChart(chartContainerRef.current, {
            layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#94a3b8' },
            grid: { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
            rightPriceScale: { borderColor: '#334155' },
            timeScale: { borderColor: '#334155', timeVisible: true, secondsVisible: false },
            width: chartContainerRef.current.clientWidth,
            height: 180,
        });
        chartRef.current = chart;

        const lineSeries = chart.addLineSeries({ color: '#22d3ee', lineWidth: 2, priceLineVisible: false });

        // 초기자본 기준선
        const baselineSeries = chart.addLineSeries({
            color: '#475569', lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false,
        });

        const lineData = history.map(h => ({
            time: Math.floor(new Date(h.recorded_at).getTime() / 1000) as any,
            value: h.total_value,
        }));
        const baseValue = status?.initial_capital ?? history[0].total_value;
        const baseData = [
            { time: lineData[0].time, value: baseValue },
            { time: lineData[lineData.length - 1].time, value: baseValue },
        ];

        lineSeries.setData(lineData);
        baselineSeries.setData(baseData);
        chart.timeScale().fitContent();

        return () => { chart.remove(); chartRef.current = null; };
    }, [history, status?.initial_capital]);

    if (loading) return (
        <div className="flex items-center justify-center h-full">
            <Loader2 className="animate-spin text-primary mr-3" size={28} />
            <span className="text-slate-400">불러오는 중...</span>
        </div>
    );

    return (
        <>
        {selectedTrade && (
            <TradeDetailModal trade={selectedTrade} onClose={() => setSelectedTrade(null)} />
        )}
        <div className="h-full flex flex-col gap-5 overflow-y-auto">

            {/* ── 헤더 ───────────────────────────────────────── */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold flex items-center gap-2">
                        <Activity className="text-cyan-400" size={28} />
                        모의투자 시뮬레이션
                    </h2>
                    <p className="text-slate-400 text-sm mt-1">
                        실시간 데이터로 자동매매를 테스트합니다 (실제 거래 없음)
                    </p>
                </div>

                {/* 컨트롤 버튼 */}
                <div className="flex items-center gap-2">
                    <Stopwatch
                        startedAt={status?.is_running ? (status.started_at ?? null) : null}
                        elapsedSeconds={status?.elapsed_seconds ?? 0}
                    />
                    {!status?.is_running ? (
                        <button
                            onClick={handleStart}
                            disabled={actionLoading}
                            className="flex items-center gap-2 px-5 py-2.5 bg-cyan-600 hover:bg-cyan-500 rounded-lg font-semibold transition-colors disabled:opacity-50"
                        >
                            {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <PlayCircle size={16} />}
                            시작
                        </button>
                    ) : (
                        <button
                            onClick={handleStop}
                            disabled={actionLoading}
                            className="flex items-center gap-2 px-5 py-2.5 bg-slate-600 hover:bg-slate-500 rounded-lg font-semibold transition-colors disabled:opacity-50"
                        >
                            {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <StopCircle size={16} />}
                            중지
                        </button>
                    )}
                    <button
                        onClick={handleReset}
                        disabled={actionLoading}
                        className="flex items-center gap-2 px-4 py-2.5 bg-red-900/40 hover:bg-red-800/60 border border-red-700/50 rounded-lg text-sm transition-colors disabled:opacity-50"
                    >
                        <RotateCcw size={14} />
                        초기화
                    </button>
                </div>
            </div>

            {error && (
                <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/40 rounded-lg px-4 py-3 text-red-400 text-sm">
                    <AlertCircle size={16} />
                    {error}
                </div>
            )}

            {/* ── 설정 폼 (중지 상태일 때만) ─────────────────── */}
            {!status?.is_running && (
                <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-5">
                    <h3 className="text-sm font-semibold text-slate-300 mb-4">시뮬레이션 설정</h3>
                    <div className="grid grid-cols-3 gap-4 text-sm">
                        <label className="flex flex-col gap-1">
                            <span className="text-slate-400">초기 자본 (원)</span>
                            <input type="number" value={config.initial_capital}
                                onChange={e => setConfig(c => ({ ...c, initial_capital: +e.target.value }))}
                                className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 focus:outline-none focus:border-primary" />
                        </label>
                        <label className="flex flex-col gap-1">
                            <span className="text-slate-400">전략</span>
                            <select value={config.strategy}
                                onChange={e => setConfig(c => ({ ...c, strategy: e.target.value }))}
                                className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 focus:outline-none focus:border-primary">
                                <option value="combined">종합 전략</option>
                                <option value="volume">거래량 기반</option>
                                <option value="technical">기술적 지표</option>
                                <option value="rsi_golden_cross">RSI 골든크로스</option>
                                <option value="weekly_rsi_swing">주봉 RSI 스윙</option>
                            </select>
                        </label>
                        <label className="flex flex-col gap-1">
                            <span className="text-slate-400">최소 진입 점수</span>
                            <input type="number" value={config.min_score} min={50} max={90}
                                onChange={e => setConfig(c => ({ ...c, min_score: +e.target.value }))}
                                className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 focus:outline-none focus:border-primary" />
                        </label>
                        <label className="flex flex-col gap-1">
                            <span className="text-slate-400">최대 동시 보유</span>
                            <input type="number" value={config.max_positions} min={1} max={10}
                                onChange={e => setConfig(c => ({ ...c, max_positions: +e.target.value }))}
                                className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 focus:outline-none focus:border-primary" />
                        </label>
                        <label className="flex flex-col gap-1">
                            <span className="text-slate-400">종목당 투자 비율</span>
                            <select value={config.position_size_pct}
                                onChange={e => setConfig(c => ({ ...c, position_size_pct: +e.target.value }))}
                                className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 focus:outline-none focus:border-primary">
                                <option value={0.2}>20%</option>
                                <option value={0.3}>30%</option>
                                <option value={0.5}>50%</option>
                            </select>
                        </label>
                    </div>
                </div>
            )}

            {/* ── 계좌 요약 카드 ──────────────────────────────── */}
            {status && (
                <div className="grid grid-cols-4 gap-4">
                    {[
                        { label: '총 자산', value: fmtKRW(status.total_value), icon: DollarSign, color: 'text-cyan-400' },
                        { label: '현금', value: fmtKRW(status.cash), icon: DollarSign, color: 'text-slate-300' },
                        { label: '평가 손익', value: fmtPct(status.roi), icon: status.roi >= 0 ? TrendingUp : TrendingDown, color: status.roi >= 0 ? 'text-green-400' : 'text-red-400' },
                        { label: '보유 / 오늘 청산', value: `${status.open_count}종목 / ${status.closed_today}건`, icon: Activity, color: 'text-purple-400' },
                    ].map(({ label, value, icon: Icon, color }) => (
                        <div key={label} className="bg-slate-800 border border-slate-700 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-2">
                                <Icon size={16} className={color} />
                                <span className="text-xs text-slate-400">{label}</span>
                            </div>
                            <div className={`text-lg font-bold ${color}`}>{value}</div>
                        </div>
                    ))}
                </div>
            )}

            {/* ── 포지션 + 거래 내역 ─────────────────────────── */}
            <div className="grid grid-cols-2 gap-4">

                {/* 보유 포지션 */}
                <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-semibold text-slate-300">
                            보유 포지션 ({positions.length}/{status?.max_positions ?? 3})
                        </h3>
                        <div className="flex items-center gap-1.5">
                            <button
                                onClick={() => { setShowAddForm(v => !v); setAddError(null); }}
                                className={`flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors ${
                                    showAddForm
                                        ? 'bg-slate-600 text-slate-200'
                                        : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
                                }`}
                            >
                                <Plus size={11} />
                                수동 추가
                            </button>
                            <button
                                onClick={handleCloseAll}
                                disabled={closingAll || positions.length === 0}
                                className="flex items-center gap-1 px-2 py-1 text-xs bg-red-900/50 hover:bg-red-700/60 border border-red-700/50 rounded text-red-300 transition-colors disabled:opacity-40"
                            >
                                {closingAll ? <Loader2 size={11} className="animate-spin" /> : <X size={11} />}
                                일괄청산
                            </button>
                        </div>
                    </div>

                    {/* 수동 추가 폼 */}
                    {showAddForm && (
                        <form onSubmit={handleAddPosition} className="mb-3 bg-slate-900/60 border border-slate-600 rounded-lg p-3 space-y-2">
                            <div className="grid grid-cols-2 gap-2">
                                <label className="flex flex-col gap-1">
                                    <span className="text-xs text-slate-400">종목 코드 *</span>
                                    <input
                                        type="text" placeholder="043200" required
                                        value={addForm.code}
                                        onChange={e => setAddForm(f => ({ ...f, code: e.target.value }))}
                                        className="bg-slate-700 border border-slate-600 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-cyan-500"
                                    />
                                </label>
                                <label className="flex flex-col gap-1">
                                    <span className="text-xs text-slate-400">종목명 (선택)</span>
                                    <input
                                        type="text" placeholder="종목명"
                                        value={addForm.name}
                                        onChange={e => setAddForm(f => ({ ...f, name: e.target.value }))}
                                        className="bg-slate-700 border border-slate-600 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-cyan-500"
                                    />
                                </label>
                                <label className="flex flex-col gap-1">
                                    <span className="text-xs text-slate-400">진입가 (원) *</span>
                                    <input
                                        type="number" placeholder="1000" required min={1}
                                        value={addForm.entry_price}
                                        onChange={e => setAddForm(f => ({ ...f, entry_price: e.target.value }))}
                                        className="bg-slate-700 border border-slate-600 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-cyan-500"
                                    />
                                </label>
                                <label className="flex flex-col gap-1">
                                    <span className="text-xs text-slate-400">수량 (0=자동)</span>
                                    <input
                                        type="number" placeholder="0" min={0}
                                        value={addForm.quantity}
                                        onChange={e => setAddForm(f => ({ ...f, quantity: e.target.value }))}
                                        className="bg-slate-700 border border-slate-600 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-cyan-500"
                                    />
                                </label>
                            </div>
                            {addError && (
                                <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/30 rounded px-2 py-1.5">
                                    {addError}
                                </div>
                            )}
                            <div className="flex gap-2 pt-1">
                                <button
                                    type="submit" disabled={addLoading}
                                    className="flex-1 flex items-center justify-center gap-1.5 py-1.5 bg-cyan-600 hover:bg-cyan-500 rounded text-sm font-semibold transition-colors disabled:opacity-50"
                                >
                                    {addLoading ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
                                    추가
                                </button>
                                <button
                                    type="button" onClick={() => setShowAddForm(false)}
                                    className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded text-sm transition-colors"
                                >
                                    취소
                                </button>
                            </div>
                        </form>
                    )}

                    {positions.length === 0 ? (
                        <p className="text-sm text-slate-500 py-4 text-center">보유 종목 없음</p>
                    ) : (
                        <div className="space-y-3">
                            {positions.map(p => (
                                <div key={p.id ?? p.code} className="bg-slate-900/50 rounded-lg p-3">
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="font-semibold text-sm">{p.name}({p.code})</span>
                                        <div className="flex items-center gap-2">
                                            {p.unrealized_pnl_pct !== null && <PnlBadge pct={p.unrealized_pnl_pct} />}
                                            {onNavigateToStock && (
                                                <button
                                                    onClick={() => onNavigateToStock(p.name)}
                                                    title="주식 분석 탭에서 검색"
                                                    className="flex items-center gap-1 px-2 py-0.5 text-xs bg-blue-900/40 hover:bg-blue-700/60 border border-blue-700/50 rounded text-blue-300 transition-colors"
                                                >
                                                    <Search size={10} />
                                                    분석
                                                </button>
                                            )}
                                            <button
                                                onClick={() => handleClosePosition(p.code, p.name)}
                                                disabled={closingCode === p.code}
                                                title="수동 청산"
                                                className="flex items-center gap-1 px-2 py-0.5 text-xs bg-red-900/40 hover:bg-red-700/60 border border-red-700/50 rounded text-red-300 transition-colors disabled:opacity-50"
                                            >
                                                {closingCode === p.code
                                                    ? <Loader2 size={10} className="animate-spin" />
                                                    : <X size={10} />
                                                }
                                                청산
                                            </button>
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-2 gap-x-4 text-xs text-slate-400 mt-1">
                                        <span>진입가: <span className="text-slate-200">{p.entry_price.toLocaleString()}원</span></span>
                                        <span>수량: <span className="text-slate-200">{p.quantity.toLocaleString()}주</span></span>
                                        <span>점수: <span className="text-slate-200">{p.entry_score.toFixed(0)}점</span></span>
                                        <span className="flex items-center gap-1">
                                            <Clock size={10} />
                                            {p.holding_hours}시간 보유
                                        </span>
                                    </div>
                                    {p.unrealized_pnl !== null && (
                                        <div className={`text-xs mt-1.5 font-mono ${p.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {p.unrealized_pnl >= 0 ? '+' : ''}{p.unrealized_pnl.toLocaleString()}원
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* 최근 거래 내역 */}
                <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
                    <h3 className="text-sm font-semibold text-slate-300 mb-3">최근 거래 내역</h3>
                    {trades.length === 0 ? (
                        <p className="text-sm text-slate-500 py-4 text-center">거래 내역 없음</p>
                    ) : (
                        <div className="space-y-2 max-h-72 overflow-y-auto">
                            {trades.map(t => (
                                <div
                                    key={t.id}
                                    onClick={() => setSelectedTrade(t)}
                                    className="flex items-center justify-between bg-slate-900/50 hover:bg-slate-700/50 rounded-lg px-3 py-2 cursor-pointer transition-colors group"
                                >
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm font-semibold truncate">{t.name}({t.code})</span>
                                            <ExitReasonLabel reason={t.exit_reason} />
                                            <Info size={12} className="text-slate-600 group-hover:text-slate-400 transition-colors shrink-0" />
                                        </div>
                                        <div className="text-xs text-slate-500 mt-0.5">
                                            {t.exit_time ? new Date(t.exit_time).toLocaleString('ko-KR') : ''}
                                        </div>
                                    </div>
                                    <div className="text-right ml-2 shrink-0">
                                        <PnlBadge pct={t.profit_loss_pct} />
                                        <div className="text-xs text-slate-400 mt-0.5 font-mono">
                                            {t.profit_loss >= 0 ? '+' : ''}{t.profit_loss.toLocaleString()}원
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* ── 포트폴리오 가치 차트 ────────────────────────── */}
            {history.length > 1 && (
                <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
                    <h3 className="text-sm font-semibold text-slate-300 mb-4">포트폴리오 가치 변화</h3>
                    <div ref={chartContainerRef} className="w-full" style={{ height: 180 }} />
                </div>
            )}

            {history.length <= 1 && status?.is_running && (
                <div className="bg-slate-800 border border-slate-700 rounded-xl p-8 text-center text-slate-500 text-sm">
                    시뮬레이션 시작 후 5분마다 데이터가 쌓입니다
                </div>
            )}
        </div>
        </>
    );
}
