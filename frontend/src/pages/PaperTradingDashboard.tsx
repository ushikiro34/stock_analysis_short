import { useState, useEffect, useCallback, useRef } from 'react';
import { PlayCircle, StopCircle, RotateCcw, TrendingUp, TrendingDown, DollarSign, Activity, Clock, AlertCircle, Loader2, Timer } from 'lucide-react';
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

function ExitReasonLabel({ reason }: { reason: string | null }) {
    if (!reason) return null;
    const map: Record<string, { label: string; color: string }> = {
        '1차 익절 +3%':  { label: '익절 +3%',  color: 'text-green-400' },
        '2차 익절 +5%':  { label: '익절 +5%',  color: 'text-green-400' },
        '3차 익절 +10%': { label: '익절 +10%', color: 'text-green-300' },
        fixed_stop_loss: { label: '손절',       color: 'text-red-400' },
        trailing_stop:   { label: '트레일링',   color: 'text-orange-400' },
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

export default function PaperTradingDashboard() {
    const [status, setStatus] = useState<PaperStatus | null>(null);
    const [positions, setPositions] = useState<PaperPosition[]>([]);
    const [trades, setTrades] = useState<PaperTrade[]>([]);
    const [history, setHistory] = useState<PaperHistoryPoint[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [config, setConfig] = useState<PaperStartConfig>(DEFAULT_CONFIG);

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
            setError(e?.response?.data?.detail || '시작 실패');
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
                    <h3 className="text-sm font-semibold text-slate-300 mb-3">
                        보유 포지션 ({positions.length}/{status?.max_positions ?? 3})
                    </h3>
                    {positions.length === 0 ? (
                        <p className="text-sm text-slate-500 py-4 text-center">보유 종목 없음</p>
                    ) : (
                        <div className="space-y-3">
                            {positions.map(p => (
                                <div key={p.id ?? p.code} className="bg-slate-900/50 rounded-lg p-3">
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="font-semibold text-sm">{p.name}({p.code})</span>
                                        {p.unrealized_pnl_pct !== null && <PnlBadge pct={p.unrealized_pnl_pct} />}
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
                                <div key={t.id} className="flex items-center justify-between bg-slate-900/50 rounded-lg px-3 py-2">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm font-semibold truncate">{t.name}({t.code})</span>
                                            <ExitReasonLabel reason={t.exit_reason} />
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
    );
}
