import { useState, useEffect, useCallback, useRef } from 'react';
import { PlayCircle, StopCircle, AlertTriangle, Activity, Shield, Loader2, X, RefreshCw, Zap, FileText, ChevronDown, ChevronUp, Brain, TrendingUp, Clock, Target, CheckCircle2, AlertCircle } from 'lucide-react';
import { createChart, ColorType, LineStyle } from 'lightweight-charts';
import {
    liveTrading, insightsApi,
    type LiveStatus, type LivePosition, type LiveTradesResponse,
    type LiveHistoryPoint, type LiveBalance, type LiveStartConfig,
    type LiveDailyReport, type TradeAnalysis, type Recommendation, type PresurgeStats,
} from '../lib/api';

const REFRESH_INTERVAL = 30_000;

const fmtKRW = (v: number) => v.toLocaleString('ko-KR') + '원';
const fmtPct = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;

function PnlBadge({ pct }: { pct: number }) {
    const color = pct > 0 ? 'text-green-400' : pct < 0 ? 'text-red-400' : 'text-slate-400';
    return <span className={`font-bold ${color}`}>{fmtPct(pct)}</span>;
}

/** 시작 전 경고 확인 모달 */
function ConfirmStartModal({ onConfirm, onCancel }: { onConfirm: (cfg: LiveStartConfig) => void; onCancel: () => void }) {
    const [cfg, setCfg] = useState<LiveStartConfig>({
        market: 'KR',
        strategy: 'combined',
        min_score: 65,
        max_positions: 2,
        position_size_pct: 0.15,
        pre_surge_mode: false,
    });
    const [confirmed, setConfirmed] = useState(false);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
            <div className="w-[520px] bg-slate-900 border border-red-500/60 rounded-2xl shadow-2xl p-6">
                {/* 경고 헤더 */}
                <div className="flex items-center gap-3 mb-5">
                    <div className="w-10 h-10 bg-red-500/20 rounded-full flex items-center justify-center">
                        <AlertTriangle size={22} className="text-red-400" />
                    </div>
                    <div>
                        <div className="text-lg font-bold text-red-400">실전 투자 모드</div>
                        <div className="text-xs text-slate-400">실제 자금이 사용됩니다</div>
                    </div>
                </div>

                <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-5 text-sm text-red-300 space-y-1">
                    <p>⚠️ 이 기능은 <strong>KIS 실전 계좌</strong>로 실제 주문을 제출합니다.</p>
                    <p>⚠️ 손실이 발생해도 복구되지 않습니다.</p>
                    <p>⚠️ 시장가 주문으로 즉시 체결됩니다 (슬리피지 발생 가능).</p>
                    <p>⚠️ 일일 손실 한도 -3% 초과 시 자동으로 매수가 중단됩니다.</p>
                </div>

                {/* 설정 */}
                <div className="grid grid-cols-2 gap-3 mb-5 text-sm">
                    <div>
                        <label className="text-xs text-slate-400 mb-1 block">최대 포지션 수</label>
                        <input
                            type="number" min={1} max={5}
                            value={cfg.max_positions}
                            onChange={e => setCfg(c => ({ ...c, max_positions: Number(e.target.value) }))}
                            className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm focus:outline-none focus:border-primary"
                        />
                    </div>
                    <div>
                        <label className="text-xs text-slate-400 mb-1 block">종목당 비중 (%)</label>
                        <input
                            type="number" min={5} max={50} step={5}
                            value={Math.round((cfg.position_size_pct ?? 0.15) * 100)}
                            onChange={e => setCfg(c => ({ ...c, position_size_pct: Number(e.target.value) / 100 }))}
                            className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm focus:outline-none focus:border-primary"
                        />
                    </div>
                    <div>
                        <label className="text-xs text-slate-400 mb-1 block">최소 점수</label>
                        <input
                            type="number" min={50} max={90}
                            value={cfg.min_score}
                            onChange={e => setCfg(c => ({ ...c, min_score: Number(e.target.value) }))}
                            className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm focus:outline-none focus:border-primary"
                        />
                    </div>
                    <div className="flex items-end pb-1">
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={cfg.pre_surge_mode}
                                onChange={e => setCfg(c => ({ ...c, pre_surge_mode: e.target.checked }))}
                                className="w-4 h-4"
                            />
                            <span className="text-slate-300 text-sm">급등전 모드</span>
                        </label>
                    </div>
                </div>

                {/* 확인 체크박스 */}
                <label className="flex items-center gap-2 cursor-pointer mb-5">
                    <input
                        type="checkbox"
                        checked={confirmed}
                        onChange={e => setConfirmed(e.target.checked)}
                        className="w-4 h-4"
                    />
                    <span className="text-sm text-slate-300">
                        위 경고를 읽었으며, 실전 자동매매를 시작하겠습니다.
                    </span>
                </label>

                <div className="flex gap-3">
                    <button onClick={onCancel} className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm transition-colors">
                        취소
                    </button>
                    <button
                        onClick={() => confirmed && onConfirm(cfg)}
                        disabled={!confirmed}
                        className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-bold transition-colors"
                    >
                        실전 매매 시작
                    </button>
                </div>
            </div>
        </div>
    );
}

/** 긴급 청산 확인 모달 */
function ConfirmCloseAllModal({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
            <div className="w-96 bg-slate-900 border border-red-500/60 rounded-2xl shadow-2xl p-6">
                <div className="flex items-center gap-3 mb-4">
                    <AlertTriangle size={22} className="text-red-400" />
                    <div className="text-lg font-bold text-red-400">전량 긴급 청산</div>
                </div>
                <p className="text-sm text-slate-300 mb-6">
                    모든 보유 포지션을 시장가로 즉시 청산합니다.<br />
                    이 작업은 되돌릴 수 없습니다.
                </p>
                <div className="flex gap-3">
                    <button onClick={onCancel} className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm transition-colors">
                        취소
                    </button>
                    <button onClick={onConfirm} className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg text-sm font-bold transition-colors">
                        전량 청산
                    </button>
                </div>
            </div>
        </div>
    );
}

/** 포트폴리오 가치 라인 차트 */
function PortfolioChart({ history }: { history: LiveHistoryPoint[] }) {
    const chartRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!chartRef.current || history.length === 0) return;
        const chart = createChart(chartRef.current, {
            layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#94a3b8' },
            grid: { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
            crosshair: { mode: 1 },
            rightPriceScale: { borderColor: '#334155' },
            timeScale: { borderColor: '#334155', timeVisible: true },
            width: chartRef.current.clientWidth,
            height: 180,
        });
        const series = chart.addLineSeries({ color: '#ef4444', lineWidth: 2, lineStyle: LineStyle.Solid });
        const data = history
            .filter(p => p.recorded_at && p.total_value > 0)
            .map(p => ({ time: Math.floor(new Date(p.recorded_at).getTime() / 1000) as any, value: p.total_value }));
        if (data.length > 0) {
            series.setData(data);
            chart.timeScale().fitContent();
        }
        const handleResize = () => chart.applyOptions({ width: chartRef.current?.clientWidth ?? 400 });
        window.addEventListener('resize', handleResize);
        return () => { window.removeEventListener('resize', handleResize); chart.remove(); };
    }, [history]);

    if (history.length === 0) return (
        <div className="h-[180px] flex items-center justify-center text-slate-600 text-sm">거래 이력 없음</div>
    );
    return <div ref={chartRef} />;
}

// ── Insights Tab ───────────────────────────────────────────────

interface InsightsTabProps {
    analysis: TradeAnalysis | null;
    source: 'all' | 'live' | 'paper';
    loading: boolean;
    error: string | null;
    applyingParam: string | null;
    onSourceChange: (s: 'all' | 'live' | 'paper') => void;
    onRefresh: () => void;
    onApply: (rec: Recommendation) => void;
}

const confidenceColor = (c: string) =>
    c === 'high' ? 'text-green-400 border-green-400/40 bg-green-400/10'
    : c === 'medium' ? 'text-yellow-400 border-yellow-400/40 bg-yellow-400/10'
    : 'text-slate-400 border-slate-600 bg-slate-800/40';

const qualityBadge = (q: string) =>
    q === 'sufficient' ? 'text-green-400 bg-green-400/10 border-green-400/30'
    : q === 'limited' ? 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30'
    : 'text-red-400 bg-red-400/10 border-red-400/30';

const qualityLabel = (q: string) =>
    q === 'sufficient' ? '데이터 충분' : q === 'limited' ? '데이터 부족' : '데이터 없음';

function InsightsTab({ analysis, source, loading, error, applyingParam, onSourceChange, onRefresh, onApply }: InsightsTabProps) {
    return (
        <div className="space-y-4">
            {/* 상단 컨트롤 */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Brain size={16} className="text-purple-400" />
                    <span className="text-sm font-medium text-slate-300">거래 패턴 학습 분석</span>
                    {analysis && (
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${qualityBadge(analysis.data_quality)}`}>
                            {qualityLabel(analysis.data_quality)}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    {/* 소스 선택 */}
                    <div className="flex bg-slate-800 rounded-lg border border-slate-700 overflow-hidden text-xs">
                        {(['all', 'live', 'paper'] as const).map(s => (
                            <button
                                key={s}
                                onClick={() => onSourceChange(s)}
                                className={`px-3 py-1.5 transition-colors ${source === s ? 'bg-primary text-white' : 'text-slate-400 hover:text-slate-200'}`}
                            >
                                {s === 'all' ? '전체' : s === 'live' ? '실전' : '페이퍼'}
                            </button>
                        ))}
                    </div>
                    <button
                        onClick={onRefresh}
                        disabled={loading}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 rounded-lg text-xs transition-colors"
                    >
                        {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                        분석
                    </button>
                </div>
            </div>

            {/* 에러 */}
            {error && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-400 flex items-center gap-2">
                    <AlertCircle size={14} /> {error}
                </div>
            )}

            {/* 로딩 */}
            {loading && !analysis && (
                <div className="flex flex-col items-center justify-center h-32 text-slate-500">
                    <Loader2 size={28} className="animate-spin mb-2" />
                    <p className="text-sm">거래 패턴 분석 중...</p>
                </div>
            )}

            {/* 데이터 없음 안내 */}
            {!loading && !analysis && !error && (
                <div className="flex flex-col items-center justify-center h-32 text-slate-600">
                    <Brain size={28} className="mb-2" />
                    <p className="text-sm">위 [분석] 버튼을 클릭하여 거래 패턴을 분석하세요</p>
                </div>
            )}

            {analysis && (
                <>
                    {/* 거래 없음 메시지 */}
                    {analysis.total_trades === 0 && (
                        <div className="flex flex-col items-center justify-center h-24 text-slate-600">
                            <p className="text-sm">{analysis.message ?? '청산된 거래 없음'}</p>
                        </div>
                    )}

                    {analysis.total_trades > 0 && (
                        <>
                            {/* 전체 통계 요약 */}
                            <div className="grid grid-cols-4 gap-3">
                                {[
                                    { label: '총 거래', value: `${analysis.total_trades}건`, icon: <FileText size={14} /> },
                                    { label: '승률', value: `${analysis.win_rate.toFixed(1)}%`, color: analysis.win_rate >= 50 ? 'text-green-400' : 'text-red-400', icon: <Target size={14} /> },
                                    { label: '평균 수익률', value: `${analysis.avg_pnl_pct >= 0 ? '+' : ''}${analysis.avg_pnl_pct.toFixed(2)}%`, color: analysis.avg_pnl_pct >= 0 ? 'text-green-400' : 'text-red-400', icon: <TrendingUp size={14} /> },
                                    { label: '누적 손익', value: `${analysis.total_pnl >= 0 ? '+' : ''}${analysis.total_pnl.toLocaleString()}원`, color: analysis.total_pnl >= 0 ? 'text-green-400' : 'text-red-400', icon: <Activity size={14} /> },
                                ].map(item => (
                                    <div key={item.label} className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-3">
                                        <div className="flex items-center gap-1.5 text-slate-500 text-xs mb-1">
                                            {item.icon} {item.label}
                                        </div>
                                        <div className={`text-lg font-bold font-mono ${item.color ?? 'text-white'}`}>{item.value}</div>
                                    </div>
                                ))}
                            </div>

                            {/* 점수 구간별 성과 */}
                            {analysis.score_analysis?.buckets?.length > 0 && (
                                <div className="bg-slate-800/40 border border-slate-700/60 rounded-xl p-4">
                                    <div className="flex items-center justify-between mb-3">
                                        <div className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
                                            <Target size={13} /> 점수 구간별 성과
                                        </div>
                                        {analysis.score_analysis.insight && (
                                            <div className="text-[10px] text-slate-500 max-w-[60%] text-right">{analysis.score_analysis.insight}</div>
                                        )}
                                    </div>
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-xs">
                                            <thead>
                                                <tr className="text-slate-500 border-b border-slate-700">
                                                    <th className="text-left pb-2">구간</th>
                                                    <th className="text-right pb-2">거래수</th>
                                                    <th className="text-right pb-2">승률</th>
                                                    <th className="text-right pb-2">평균수익률</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-slate-700/40">
                                                {analysis.score_analysis.buckets.map(b => (
                                                    <tr key={b.label} className={`${!b.reliable ? 'opacity-50' : ''}`}>
                                                        <td className="py-1.5 font-mono text-slate-300">{b.label}</td>
                                                        <td className="text-right text-slate-400">
                                                            {b.count}
                                                            {!b.reliable && <span className="ml-1 text-yellow-500 text-[10px]">*</span>}
                                                        </td>
                                                        <td className={`text-right font-medium ${b.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}`}>{b.win_rate.toFixed(0)}%</td>
                                                        <td className={`text-right font-mono ${b.avg_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                            {b.avg_pnl >= 0 ? '+' : ''}{b.avg_pnl.toFixed(2)}%
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                        <div className="text-[10px] text-slate-600 mt-1">* 샘플 부족 (신뢰도 낮음)</div>
                                    </div>
                                </div>
                            )}

                            {/* 급등전 vs 일반 비교 */}
                            {'presurge' in (analysis.presurge_analysis ?? {}) && (
                                <div className="bg-slate-800/40 border border-slate-700/60 rounded-xl p-4">
                                    <div className="text-xs font-medium text-slate-400 mb-3 flex items-center gap-1.5">
                                        <Zap size={13} /> 급등전 신호 vs 일반 거래 비교
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        {([
                                            { label: '급등전 신호', data: (analysis.presurge_analysis as any).presurge as PresurgeStats, border: 'border-amber-500/20', text: 'text-amber-400' },
                                            { label: '일반 거래', data: (analysis.presurge_analysis as any).normal as PresurgeStats, border: 'border-blue-500/20', text: 'text-blue-400' },
                                        ]).map(({ label, data, border, text }) => (
                                            <div key={label} className={`border ${border} rounded-lg p-3`}>
                                                <div className={`text-xs font-medium ${text} mb-2`}>{label}</div>
                                                <div className="space-y-1 text-xs">
                                                    <div className="flex justify-between text-slate-400">
                                                        <span>거래수</span><span className="text-slate-200">{data.count}건</span>
                                                    </div>
                                                    <div className="flex justify-between text-slate-400">
                                                        <span>승률</span>
                                                        <span className={data.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}>{data.win_rate.toFixed(1)}%</span>
                                                    </div>
                                                    <div className="flex justify-between text-slate-400">
                                                        <span>평균수익률</span>
                                                        <span className={`font-mono ${data.avg_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                            {data.avg_pnl >= 0 ? '+' : ''}{data.avg_pnl.toFixed(2)}%
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                    {(analysis.presurge_analysis as any).insight && (
                                        <div className="mt-2 text-[10px] text-slate-500">{(analysis.presurge_analysis as any).insight}</div>
                                    )}
                                </div>
                            )}

                            <div className="grid grid-cols-2 gap-4">
                                {/* 청산 사유 분포 */}
                                {analysis.exit_analysis.length > 0 && (
                                    <div className="bg-slate-800/40 border border-slate-700/60 rounded-xl p-4">
                                        <div className="text-xs font-medium text-slate-400 mb-3 flex items-center gap-1.5">
                                            <X size={13} /> 청산 사유 분포
                                        </div>
                                        <div className="space-y-2">
                                            {analysis.exit_analysis.map(r => (
                                                <div key={r.reason} className="flex items-center gap-2">
                                                    <div className="min-w-[80px] text-xs text-slate-400 truncate">{r.reason || '미분류'}</div>
                                                    <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                                                        <div
                                                            className={`h-full rounded-full ${r.win_rate >= 50 ? 'bg-green-500' : 'bg-red-500'}`}
                                                            style={{ width: `${Math.min(100, r.win_rate)}%` }}
                                                        />
                                                    </div>
                                                    <div className="text-xs text-slate-500 min-w-[32px] text-right">{r.count}건</div>
                                                    <div className={`text-xs min-w-[44px] text-right font-mono ${r.avg_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                        {r.avg_pnl >= 0 ? '+' : ''}{r.avg_pnl.toFixed(1)}%
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* 시간대별 성과 */}
                                {analysis.time_analysis.length > 0 && (
                                    <div className="bg-slate-800/40 border border-slate-700/60 rounded-xl p-4">
                                        <div className="text-xs font-medium text-slate-400 mb-3 flex items-center gap-1.5">
                                            <Clock size={13} /> 시간대별 성과 (KST)
                                        </div>
                                        <div className="space-y-1.5">
                                            {analysis.time_analysis.map(t => (
                                                <div key={t.hour} className="flex items-center gap-2">
                                                    <div className="min-w-[40px] text-xs text-slate-500 font-mono">{t.label}</div>
                                                    <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                                                        <div
                                                            className={`h-full rounded-full ${t.avg_pnl >= 0 ? 'bg-green-500' : 'bg-red-500'}`}
                                                            style={{ width: `${Math.min(100, Math.abs(t.avg_pnl) * 10)}%` }}
                                                        />
                                                    </div>
                                                    <div className="text-xs text-slate-500 min-w-[30px] text-right">{t.count}건</div>
                                                    <div className={`text-xs min-w-[44px] text-right font-mono ${t.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                                                        {t.win_rate.toFixed(0)}%승
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* 보유 기간별 성과 */}
                            {analysis.holding_analysis.length > 0 && (
                                <div className="bg-slate-800/40 border border-slate-700/60 rounded-xl p-4">
                                    <div className="text-xs font-medium text-slate-400 mb-3 flex items-center gap-1.5">
                                        <Clock size={13} /> 보유 기간별 성과
                                    </div>
                                    <div className="grid grid-cols-5 gap-2">
                                        {analysis.holding_analysis.map(b => (
                                            <div key={b.label} className="bg-slate-900/60 rounded-lg p-2.5 text-center">
                                                <div className="text-[10px] text-slate-500 mb-1 leading-tight">{b.label}</div>
                                                <div className={`text-sm font-bold ${b.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                                                    {b.win_rate.toFixed(0)}%
                                                </div>
                                                <div className={`text-[10px] font-mono mt-0.5 ${b.avg_pnl >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                                                    {b.avg_pnl >= 0 ? '+' : ''}{b.avg_pnl.toFixed(1)}%
                                                </div>
                                                <div className="text-[10px] text-slate-600 mt-0.5">{b.count}건</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* 파라미터 추천 */}
                            {analysis.recommendations.length > 0 && (
                                <div className="bg-slate-800/40 border border-slate-700/60 rounded-xl p-4">
                                    <div className="text-xs font-medium text-slate-400 mb-3 flex items-center gap-1.5">
                                        <CheckCircle2 size={13} /> 파라미터 개선 제안
                                    </div>
                                    <div className="space-y-2">
                                        {analysis.recommendations.map(rec => {
                                            const isApplyable = rec.confidence !== 'info' && rec.suggested != null;
                                            return (
                                                <div key={rec.param} className={`border rounded-lg p-3 ${confidenceColor(rec.confidence)}`}>
                                                    <div className="flex items-start justify-between gap-3">
                                                        <div className="flex-1 min-w-0">
                                                            <div className="flex items-center gap-2 mb-1">
                                                                <span className="font-mono text-xs font-medium">{rec.param}</span>
                                                                <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${confidenceColor(rec.confidence)}`}>
                                                                    {rec.confidence === 'high' ? '신뢰↑' : rec.confidence === 'medium' ? '보통' : rec.confidence === 'low' ? '참고' : '정보'}
                                                                </span>
                                                            </div>
                                                            <div className="text-[11px] text-slate-400 leading-relaxed">{rec.reason}</div>
                                                            {rec.suggested != null && (
                                                                <div className="flex items-center gap-2 mt-1.5 text-xs">
                                                                    <span className="text-slate-500">현재</span>
                                                                    <span className="font-mono text-slate-300">{rec.current != null ? String(rec.current) : 'N/A'}</span>
                                                                    <span className="text-slate-600">→</span>
                                                                    <span className="font-mono font-bold">{String(rec.suggested)}</span>
                                                                </div>
                                                            )}
                                                        </div>
                                                        {isApplyable && (
                                                            <button
                                                                onClick={() => onApply(rec)}
                                                                disabled={applyingParam === rec.param}
                                                                className="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 bg-primary hover:bg-primary/80 disabled:opacity-40 rounded-lg text-xs font-medium text-white transition-colors"
                                                            >
                                                                {applyingParam === rec.param ? <Loader2 size={11} className="animate-spin" /> : <CheckCircle2 size={11} />}
                                                                적용
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}

                            {/* AI 내러티브 */}
                            {analysis.ai_narrative && (
                                <div className="bg-slate-800/40 border border-purple-500/20 rounded-xl p-4">
                                    <div className="text-xs font-medium text-purple-400 mb-2 flex items-center gap-1.5">
                                        <Brain size={13} /> AI 분석 요약
                                    </div>
                                    <div className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">{analysis.ai_narrative}</div>
                                </div>
                            )}
                        </>
                    )}
                </>
            )}
        </div>
    );
}

interface Props {
    isVisible: boolean;
}

export default function LiveTradingDashboard({ isVisible }: Props) {
    const [status, setStatus] = useState<LiveStatus | null>(null);
    const [balance, setBalance] = useState<LiveBalance | null>(null);
    const [positions, setPositions] = useState<LivePosition[]>([]);
    const [tradesResp, setTradesResp] = useState<LiveTradesResponse | null>(null);
    const [history, setHistory] = useState<LiveHistoryPoint[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showStartModal, setShowStartModal] = useState(false);
    const [showCloseAllModal, setShowCloseAllModal] = useState(false);
    const [activeTab, setActiveTab] = useState<'positions' | 'trades' | 'chart' | 'daily' | 'insights'>('positions');
    const [dailyReports, setDailyReports] = useState<LiveDailyReport[]>([]);
    const [generatingReport, setGeneratingReport] = useState(false);
    const [expandedReport, setExpandedReport] = useState<number | null>(null);
    const [insightsAnalysis, setInsightsAnalysis] = useState<TradeAnalysis | null>(null);
    const [insightsSource, setInsightsSource] = useState<'all' | 'live' | 'paper'>('all');
    const [insightsLoading, setInsightsLoading] = useState(false);
    const [insightsError, setInsightsError] = useState<string | null>(null);
    const [applyingParam, setApplyingParam] = useState<string | null>(null);

    const fetchDailyReports = useCallback(async () => {
        try {
            const reports = await liveTrading.getDailyReports(30);
            setDailyReports(reports);
        } catch { /* silent */ }
    }, []);

    const fetchInsights = useCallback(async (src: 'all' | 'live' | 'paper' = insightsSource) => {
        setInsightsLoading(true);
        setInsightsError(null);
        try {
            const data = await insightsApi.getTradeAnalysis(src);
            setInsightsAnalysis(data);
        } catch (e: any) {
            setInsightsError(e.message ?? '분석 데이터 조회 실패');
        }
        setInsightsLoading(false);
    }, [insightsSource]);

    const fetchAll = useCallback(async () => {
        try {
            const [st, pos, hist] = await Promise.all([
                liveTrading.getStatus(),
                liveTrading.getPositions(),
                liveTrading.getHistory(),
            ]);
            setStatus(st);
            setPositions(pos);
            setHistory(hist);
            setError(null);

            // 잔고는 별도 — 실패해도 나머지는 표시
            try {
                const bal = await liveTrading.getBalance();
                setBalance(bal);
            } catch { /* KIS API 미인증 등 */ }

            // 거래내역
            try {
                const tr = await liveTrading.getTrades(50);
                setTradesResp(tr);
            } catch { /* */ }
        } catch (e: any) {
            setError(e.message ?? '데이터 조회 실패');
        }
    }, []);

    useEffect(() => {
        if (!isVisible) return;
        fetchAll();
        fetchDailyReports();
        const iv = setInterval(fetchAll, REFRESH_INTERVAL);
        return () => clearInterval(iv);
    }, [isVisible, fetchAll, fetchDailyReports]);

    // 학습 인사이트 탭 진입 시 자동 로드
    useEffect(() => {
        if (activeTab === 'insights' && !insightsAnalysis && !insightsLoading) {
            fetchInsights(insightsSource);
        }
    }, [activeTab]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleStart = async (cfg: LiveStartConfig) => {
        setLoading(true);
        setShowStartModal(false);
        try {
            await liveTrading.start(cfg);
            await fetchAll();
        } catch (e: any) {
            setError(e.message);
        }
        setLoading(false);
    };

    const handleStop = async () => {
        setLoading(true);
        try {
            await liveTrading.stop();
            await fetchAll();
        } catch (e: any) {
            setError(e.message);
        }
        setLoading(false);
    };

    const handleCloseAll = async () => {
        setShowCloseAllModal(false);
        setLoading(true);
        try {
            await liveTrading.closeAllPositions();
            await fetchAll();
        } catch (e: any) {
            setError(e.message);
        }
        setLoading(false);
    };

    const isEnabled = status?.enabled ?? false;
    const isRunning = status?.is_running ?? false;

    return (
        <div className="h-full flex flex-col gap-4 overflow-auto">
            {/* 실전 경고 배너 */}
            <div className="flex items-center gap-3 px-4 py-2.5 bg-red-500/10 border border-red-500/40 rounded-xl text-sm text-red-300">
                <AlertTriangle size={16} className="shrink-0 text-red-400" />
                <span><strong className="text-red-400">실전 투자 모드</strong> — 실제 자금이 사용됩니다. 신중하게 운용하세요.</span>
                {!isEnabled && (
                    <span className="ml-auto text-xs bg-red-500/20 px-2 py-0.5 rounded border border-red-500/30">
                        LIVE_TRADING_ENABLED=false (비활성)
                    </span>
                )}
            </div>

            {error && (
                <div className="flex items-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
                    <AlertTriangle size={14} />
                    <span>{error}</span>
                    <button onClick={() => setError(null)} className="ml-auto"><X size={14} /></button>
                </div>
            )}

            {/* 상단: 컨트롤 + 잔고 */}
            <div className="grid grid-cols-3 gap-4">
                {/* 컨트롤 카드 */}
                <div className="col-span-1 bg-surface border border-slate-700 rounded-xl p-4 flex flex-col gap-3">
                    <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold text-slate-300">엔진 상태</span>
                        <div className={`flex items-center gap-1.5 text-xs font-semibold px-2 py-0.5 rounded-full ${
                            isRunning ? 'bg-red-500/20 text-red-400 border border-red-500/40' : 'bg-slate-700 text-slate-400'
                        }`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${isRunning ? 'bg-red-400 animate-pulse' : 'bg-slate-500'}`} />
                            {isRunning ? '실행 중' : '중지'}
                        </div>
                    </div>

                    {status && (
                        <div className="text-xs text-slate-500 space-y-1">
                            <div className="flex justify-between">
                                <span>포지션</span>
                                <span className="text-slate-300">{status.open_positions} / {status.max_positions}</span>
                            </div>
                            <div className="flex justify-between">
                                <span>일손실한도</span>
                                <span className="text-red-400">{(status.daily_loss_limit * 100).toFixed(0)}%</span>
                            </div>
                            {status.pre_surge_mode && (
                                <div className="flex items-center gap-1 text-amber-400">
                                    <Zap size={11} />
                                    <span>급등전 모드</span>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="flex flex-col gap-2 mt-auto">
                        {!isRunning ? (
                            <button
                                onClick={() => setShowStartModal(true)}
                                disabled={loading || !isEnabled}
                                className="flex items-center justify-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-bold transition-colors"
                            >
                                {loading ? <Loader2 size={15} className="animate-spin" /> : <PlayCircle size={15} />}
                                실전 시작
                            </button>
                        ) : (
                            <button
                                onClick={handleStop}
                                disabled={loading}
                                className="flex items-center justify-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 rounded-lg text-sm transition-colors"
                            >
                                {loading ? <Loader2 size={15} className="animate-spin" /> : <StopCircle size={15} />}
                                중지
                            </button>
                        )}
                        <button
                            onClick={() => setShowCloseAllModal(true)}
                            disabled={loading || positions.length === 0}
                            className="flex items-center justify-center gap-2 px-4 py-2 bg-red-900/60 hover:bg-red-800/80 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg text-sm text-red-300 font-bold border border-red-700/50 transition-colors"
                        >
                            <Shield size={14} />
                            전량 긴급 청산
                        </button>
                        <button onClick={fetchAll} className="flex items-center justify-center gap-1.5 px-4 py-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors">
                            <RefreshCw size={12} />
                            새로고침
                        </button>
                    </div>
                </div>

                {/* 잔고 카드 */}
                <div className="col-span-2 bg-surface border border-slate-700 rounded-xl p-4">
                    <div className="text-sm font-semibold text-slate-300 mb-3">KIS 실계좌 잔고</div>
                    {balance ? (
                        <div className="grid grid-cols-3 gap-3">
                            <div className="bg-slate-800/60 rounded-lg p-3">
                                <div className="text-xs text-slate-500 mb-1">예수금 (주문가능)</div>
                                <div className="text-lg font-bold font-mono">{fmtKRW(balance.cash)}</div>
                            </div>
                            <div className="bg-slate-800/60 rounded-lg p-3">
                                <div className="text-xs text-slate-500 mb-1">평가금액 (합계)</div>
                                <div className="text-lg font-bold font-mono">{fmtKRW(balance.total_eval)}</div>
                            </div>
                            <div className="bg-slate-800/60 rounded-lg p-3">
                                <div className="text-xs text-slate-500 mb-1">보유 종목</div>
                                <div className="text-lg font-bold">{balance.positions.length}종목</div>
                            </div>
                            {balance.positions.length > 0 && (
                                <div className="col-span-3 mt-1">
                                    <div className="text-xs text-slate-500 mb-1.5">보유 내역</div>
                                    <div className="flex flex-wrap gap-2">
                                        {balance.positions.map(p => (
                                            <div key={p.code} className="text-xs bg-slate-800 border border-slate-700 rounded px-2 py-1">
                                                <span className="font-mono text-slate-300">{p.code}</span>
                                                <span className="text-slate-500 mx-1">·</span>
                                                <span>{p.qty}주</span>
                                                <span className="text-slate-500 mx-1">·</span>
                                                <span className="text-slate-400">avg {p.avg_price.toLocaleString()}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="flex items-center gap-2 text-sm text-slate-500">
                            <Activity size={14} />
                            잔고 조회 중... (KIS API 연결 필요)
                        </div>
                    )}
                </div>
            </div>

            {/* 탭: 포지션 / 거래내역 / 차트 */}
            <div className="bg-surface border border-slate-700 rounded-xl flex flex-col flex-1 min-h-0">
                <div className="flex border-b border-slate-700">
                    {([
                        { id: 'positions', label: `보유 포지션 (${positions.length})` },
                        { id: 'trades',    label: '거래 내역' },
                        { id: 'chart',     label: '자산 추이' },
                        { id: 'daily',     label: `일일 분석 (${dailyReports.length})` },
                        { id: 'insights',  label: '학습 인사이트' },
                    ] as const).map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`px-5 py-3 text-sm font-medium transition-colors relative ${
                                activeTab === tab.id ? 'text-white' : 'text-slate-400 hover:text-slate-200'
                            }`}
                        >
                            {tab.label}
                            {activeTab === tab.id && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />}
                        </button>
                    ))}
                </div>

                <div className="flex-1 overflow-auto p-4">
                    {/* 포지션 탭 */}
                    {activeTab === 'positions' && (
                        positions.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-32 text-slate-600">
                                <Activity size={28} className="mb-2" />
                                <p className="text-sm">보유 포지션 없음</p>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {positions.map(p => {
                                    const pnlPct = p.unrealized_pnl_pct ?? 0;
                                    const pnlColor = pnlPct > 0 ? 'text-green-400' : pnlPct < 0 ? 'text-red-400' : 'text-slate-400';
                                    return (
                                        <div key={p.code} className="flex items-center gap-4 bg-slate-800/60 border border-slate-700/60 rounded-xl px-4 py-3">
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-bold text-sm">{p.name}</span>
                                                    <span className="text-xs text-slate-500 font-mono">{p.code}</span>
                                                    {p.is_presurge && (
                                                        <span className="text-xs text-amber-400 bg-amber-400/10 border border-amber-400/30 rounded px-1.5 py-0.5 flex items-center gap-1">
                                                            <Zap size={9} />급등전
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                                                    <span>진입가 <span className="text-slate-300 font-mono">{p.entry_price.toLocaleString()}</span></span>
                                                    <span>수량 <span className="text-slate-300">{p.quantity}주</span></span>
                                                    <span>보유 <span className="text-slate-300">{p.holding_hours.toFixed(1)}h</span></span>
                                                    <span>점수 <span className="text-slate-300">{p.entry_score.toFixed(0)}</span></span>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                {p.current_price != null && (
                                                    <div className="font-mono text-sm text-slate-200">{p.current_price.toLocaleString()}원</div>
                                                )}
                                                {p.unrealized_pnl_pct != null && (
                                                    <div className={`text-sm font-bold ${pnlColor}`}>{fmtPct(pnlPct)}</div>
                                                )}
                                                <div className="text-xs text-slate-600 mt-0.5">고점 {p.highest_price.toLocaleString()}</div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )
                    )}

                    {/* 거래내역 탭 */}
                    {activeTab === 'trades' && tradesResp && (
                        <div>
                            {/* 요약 */}
                            <div className="grid grid-cols-4 gap-3 mb-4">
                                {[
                                    { label: '총 거래', value: `${tradesResp.total}건`, color: 'text-slate-200' },
                                    { label: '총 손익', value: fmtKRW(tradesResp.total_pnl), color: tradesResp.total_pnl >= 0 ? 'text-green-400' : 'text-red-400' },
                                    { label: `익절 ${tradesResp.profit_count}건`, value: `+${fmtKRW(tradesResp.profit_amount)}`, color: 'text-green-400' },
                                    { label: `손절 ${tradesResp.loss_count}건`, value: fmtKRW(tradesResp.loss_amount), color: 'text-red-400' },
                                ].map(s => (
                                    <div key={s.label} className="bg-slate-800/60 rounded-lg p-3 text-sm">
                                        <div className="text-xs text-slate-500 mb-1">{s.label}</div>
                                        <div className={`font-bold font-mono ${s.color}`}>{s.value}</div>
                                    </div>
                                ))}
                            </div>

                            {/* 거래 목록 */}
                            {tradesResp.trades.length === 0 ? (
                                <div className="text-center text-slate-600 py-8 text-sm">거래 내역 없음</div>
                            ) : (
                                <div className="space-y-1.5">
                                    {tradesResp.trades.map(t => {
                                        const pnlColor = t.profit_loss >= 0 ? 'text-green-400' : 'text-red-400';
                                        return (
                                            <div key={t.id} className="flex items-center gap-4 bg-slate-800/40 border border-slate-700/40 rounded-lg px-3 py-2.5 text-sm">
                                                <div className="min-w-0 flex-1">
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-semibold">{t.name}</span>
                                                        <span className="text-xs text-slate-500 font-mono">{t.code}</span>
                                                        {t.is_presurge && (
                                                            <span className="text-xs text-amber-400 bg-amber-400/10 border border-amber-400/30 rounded px-1 py-0.5 flex items-center gap-0.5">
                                                                <Zap size={8} />급등전
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="flex items-center gap-2 mt-0.5 text-xs text-slate-500">
                                                        <span>{t.entry_time ? new Date(t.entry_time).toLocaleString('ko-KR') : '-'}</span>
                                                        {t.exit_reason && <span className="text-slate-600">· {t.exit_reason}</span>}
                                                    </div>
                                                </div>
                                                <div className="text-right shrink-0">
                                                    <div className={`font-bold ${pnlColor}`}>
                                                        {t.profit_loss >= 0 ? '+' : ''}{t.profit_loss.toLocaleString()}원
                                                    </div>
                                                    <div className={`text-xs ${pnlColor}`}>{fmtPct(t.profit_loss_pct)}</div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}

                    {/* 자산 추이 탭 */}
                    {activeTab === 'chart' && (
                        <div>
                            <div className="text-xs text-slate-500 mb-3">포트폴리오 총 가치 추이 (KIS 잔고 기준, 5분 간격)</div>
                            <PortfolioChart history={history} />
                        </div>
                    )}

                    {/* 학습 인사이트 탭 */}
                    {activeTab === 'insights' && (
                        <InsightsTab
                            analysis={insightsAnalysis}
                            source={insightsSource}
                            loading={insightsLoading}
                            error={insightsError}
                            applyingParam={applyingParam}
                            onSourceChange={(s) => {
                                setInsightsSource(s);
                                fetchInsights(s);
                            }}
                            onRefresh={() => fetchInsights(insightsSource)}
                            onApply={async (rec) => {
                                setApplyingParam(rec.param);
                                try {
                                    await insightsApi.applyRecommendation(rec.param, rec.suggested as number | string, 'live');
                                    await fetchInsights(insightsSource);
                                } catch (e: any) {
                                    setInsightsError(e.message ?? '적용 실패');
                                }
                                setApplyingParam(null);
                            }}
                        />
                    )}

                    {/* 일일 분석 탭 */}
                    {activeTab === 'daily' && (
                        <div className="space-y-3">
                            {/* 수동 생성 버튼 */}
                            <div className="flex items-center justify-between mb-1">
                                <span className="text-xs text-slate-500">장 마감(15:30) 후 자동 생성 · 수동 생성도 가능</span>
                                <button
                                    onClick={async () => {
                                        setGeneratingReport(true);
                                        try {
                                            await liveTrading.generateReport();
                                            await fetchDailyReports();
                                        } catch (e: any) {
                                            setError(e.message);
                                        }
                                        setGeneratingReport(false);
                                    }}
                                    disabled={generatingReport}
                                    className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 rounded-lg text-xs transition-colors"
                                >
                                    {generatingReport ? <Loader2 size={12} className="animate-spin" /> : <FileText size={12} />}
                                    오늘 리포트 생성
                                </button>
                            </div>

                            {dailyReports.length === 0 ? (
                                <div className="flex flex-col items-center justify-center h-32 text-slate-600">
                                    <FileText size={28} className="mb-2" />
                                    <p className="text-sm">일일 리포트 없음</p>
                                    <p className="text-xs mt-1">장 마감(15:30) 후 자동 생성됩니다</p>
                                </div>
                            ) : (
                                dailyReports.map(report => {
                                    const isExpanded = expandedReport === report.id;
                                    const pnlColor = report.total_pnl >= 0 ? 'text-green-400' : 'text-red-400';
                                    return (
                                        <div key={report.id} className="bg-slate-800/60 border border-slate-700/60 rounded-xl overflow-hidden">
                                            {/* 헤더 (항상 표시) */}
                                            <button
                                                className="w-full flex items-center gap-4 px-4 py-3 hover:bg-slate-700/40 transition-colors text-left"
                                                onClick={() => setExpandedReport(isExpanded ? null : report.id)}
                                            >
                                                {/* 날짜 */}
                                                <div className="min-w-[90px]">
                                                    <div className="font-bold text-sm">{report.report_date}</div>
                                                    <div className="text-xs text-slate-500">{report.total_trades}건 거래</div>
                                                </div>
                                                {/* 통계 요약 */}
                                                <div className="flex items-center gap-4 flex-1 text-sm">
                                                    <div>
                                                        <span className={`font-bold font-mono ${pnlColor}`}>
                                                            {report.total_pnl >= 0 ? '+' : ''}{report.total_pnl.toLocaleString()}원
                                                        </span>
                                                    </div>
                                                    <div className="text-slate-400">
                                                        승률 <span className={`font-bold ${report.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}`}>{report.win_rate.toFixed(0)}%</span>
                                                    </div>
                                                    <div className="text-slate-400">
                                                        <span className="text-green-400">{report.profit_count}승</span>
                                                        <span className="text-slate-600 mx-1">/</span>
                                                        <span className="text-red-400">{report.loss_count}패</span>
                                                    </div>
                                                    <div className="text-slate-500 text-xs">평균 {report.avg_pnl_pct >= 0 ? '+' : ''}{report.avg_pnl_pct.toFixed(2)}%</div>
                                                    {report.presurge_count > 0 && (
                                                        <div className="text-xs text-amber-400 flex items-center gap-0.5">
                                                            <Zap size={10} />{report.presurge_count}건
                                                        </div>
                                                    )}
                                                </div>
                                                {isExpanded ? <ChevronUp size={16} className="text-slate-500 shrink-0" /> : <ChevronDown size={16} className="text-slate-500 shrink-0" />}
                                            </button>

                                            {/* 펼쳐진 상세 */}
                                            {isExpanded && (
                                                <div className="border-t border-slate-700/60 px-4 py-4 space-y-4">
                                                    {/* 지표 그리드 */}
                                                    <div className="grid grid-cols-3 gap-2 text-xs">
                                                        {[
                                                            { label: '평균 보유시간', value: `${report.avg_holding_hours.toFixed(1)}h` },
                                                            { label: '최고 수익', value: report.best_trade_name ? `${report.best_trade_name}(${report.best_trade_code}) ${report.best_trade_pnl_pct != null ? (report.best_trade_pnl_pct >= 0 ? '+' : '') + report.best_trade_pnl_pct.toFixed(2) + '%' : ''}` : '-', color: 'text-green-400' },
                                                            { label: '최대 손실', value: report.worst_trade_name ? `${report.worst_trade_name}(${report.worst_trade_code}) ${report.worst_trade_pnl_pct != null ? (report.worst_trade_pnl_pct >= 0 ? '+' : '') + report.worst_trade_pnl_pct.toFixed(2) + '%' : ''}` : '-', color: 'text-red-400' },
                                                        ].map(s => (
                                                            <div key={s.label} className="bg-slate-900/60 rounded-lg p-2.5">
                                                                <div className="text-slate-500 mb-0.5">{s.label}</div>
                                                                <div className={`font-semibold truncate ${s.color ?? 'text-slate-200'}`}>{s.value}</div>
                                                            </div>
                                                        ))}
                                                    </div>

                                                    {/* 청산 사유 분포 */}
                                                    {Object.keys(report.exit_reasons).length > 0 && (
                                                        <div>
                                                            <div className="text-xs text-slate-500 mb-1.5">청산 사유</div>
                                                            <div className="flex flex-wrap gap-1.5">
                                                                {Object.entries(report.exit_reasons).map(([reason, cnt]) => (
                                                                    <span key={reason} className="text-xs bg-slate-700 border border-slate-600 rounded px-2 py-0.5">
                                                                        {reason} <span className="text-slate-400 font-bold">{cnt}건</span>
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}

                                                    {/* 거래 목록 */}
                                                    {report.trades.length > 0 && (
                                                        <div>
                                                            <div className="text-xs text-slate-500 mb-1.5">거래 내역</div>
                                                            <div className="space-y-1">
                                                                {report.trades.map((t, i) => (
                                                                    <div key={i} className="flex items-center gap-3 text-xs bg-slate-900/40 rounded px-2.5 py-1.5">
                                                                        <span className="font-semibold text-slate-200">{t.name}</span>
                                                                        <span className="text-slate-600 font-mono">{t.code}</span>
                                                                        {t.is_presurge && <span className="text-amber-400"><Zap size={9} /></span>}
                                                                        <span className="text-slate-500">{t.holding_hours.toFixed(1)}h</span>
                                                                        <span className="ml-auto font-bold font-mono ${t.profit_loss >= 0 ? 'text-green-400' : 'text-red-400'}" style={{ color: t.profit_loss >= 0 ? '#4ade80' : '#f87171' }}>
                                                                            {t.profit_loss >= 0 ? '+' : ''}{t.profit_loss.toLocaleString()}원 ({t.profit_loss_pct >= 0 ? '+' : ''}{t.profit_loss_pct.toFixed(2)}%)
                                                                        </span>
                                                                        <span className="text-slate-600">{t.exit_reason || '-'}</span>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}

                                                    {/* AI 분석 */}
                                                    {report.ai_summary && (
                                                        <div>
                                                            <div className="text-xs text-slate-500 mb-1.5 flex items-center gap-1">
                                                                <span className="text-purple-400">✦</span> AI 분석
                                                            </div>
                                                            <div className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap bg-slate-900/50 border border-slate-700/40 rounded-lg p-3">
                                                                {report.ai_summary}
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* 모달 */}
            {showStartModal && (
                <ConfirmStartModal
                    onConfirm={handleStart}
                    onCancel={() => setShowStartModal(false)}
                />
            )}
            {showCloseAllModal && (
                <ConfirmCloseAllModal
                    onConfirm={handleCloseAll}
                    onCancel={() => setShowCloseAllModal(false)}
                />
            )}
        </div>
    );
}
