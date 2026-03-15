import { useState, useEffect, useRef } from 'react';
import { scanSignals, type EntrySignal, type Market } from '../lib/api';
import { TrendingUp, AlertCircle, Loader2, RefreshCw } from 'lucide-react';

interface SignalsDashboardProps {
    market: Market;
    focusCode?: string;
    onFocusDone?: () => void;
}

export default function SignalsDashboard({ market, focusCode, onFocusDone }: SignalsDashboardProps) {
    const [signals, setSignals] = useState<EntrySignal[]>([]);
    const [loading, setLoading] = useState(true);
    const [strategy, setStrategy] = useState('combined');
    const [minScore, setMinScore] = useState(60);
    const [error, setError] = useState<string | null>(null);
    const signalRefs = useRef<Record<string, HTMLDivElement | null>>({});

    // 알럿에서 이동 시 해당 신호 카드로 스크롤 + 2.5초 하이라이트 유지
    useEffect(() => {
        if (!focusCode || loading || signals.length === 0) return;
        const el = signalRefs.current[focusCode];
        if (el) {
            // rAF: ref 연결 후 DOM이 완전히 정착된 시점에 스크롤
            const raf = requestAnimationFrame(() => {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            });
            const timer = setTimeout(() => onFocusDone?.(), 2500);
            return () => { cancelAnimationFrame(raf); clearTimeout(timer); };
        }
    }, [focusCode, loading, signals]);

    const loadSignals = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await scanSignals(market, strategy, minScore);
            setSignals(data);
        } catch (err: any) {
            setError(err?.message || '신호를 불러올 수 없습니다');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadSignals();
    }, [market, strategy, minScore]);

    const getSignalColor = (signal: EntrySignal) => {
        if (signal.cup_handle_confirmed && signal.signal !== 'BUY') {
            return 'bg-purple-500/20 border-purple-500 text-purple-300';
        }
        if (signal.signal === 'BUY') {
            if (signal.strength === 'high') return 'bg-green-500/20 border-green-500 text-green-400';
            if (signal.strength === 'medium') return 'bg-yellow-500/20 border-yellow-500 text-yellow-400';
            return 'bg-blue-500/20 border-blue-500 text-blue-400';
        }
        return 'bg-slate-700/20 border-slate-600 text-slate-400';
    };

    const getStrengthBadge = (strength: string) => {
        const colors = {
            high: 'bg-green-500 text-white',
            medium: 'bg-yellow-500 text-black',
            low: 'bg-slate-500 text-white'
        };
        return colors[strength as keyof typeof colors] || colors.low;
    };

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h2 className="text-2xl font-bold flex items-center gap-2">
                        <TrendingUp className="text-green-400" size={28} />
                        매매 신호
                    </h2>
                    <p className="text-slate-400 text-sm mt-1">
                        급등주에서 자동으로 진입 기회를 탐색합니다
                    </p>
                </div>
                <button
                    onClick={loadSignals}
                    disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/80 rounded-lg transition-colors disabled:opacity-50"
                >
                    <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                    새로고침
                </button>
            </div>

            {/* Controls */}
            <div className="flex gap-4 mb-6">
                <div>
                    <label className="block text-sm text-slate-400 mb-2">전략</label>
                    <select
                        value={strategy}
                        onChange={(e) => setStrategy(e.target.value)}
                        className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-primary"
                    >
                        <option value="combined">종합 전략</option>
                        <option value="volume">거래량 기반</option>
                        <option value="technical">기술적 지표</option>
                        <option value="pattern">패턴 분석</option>
                        <option value="rsi_golden_cross">RSI 골든크로스 ⭐</option>
                        <option value="weekly_rsi_swing">주봉 RSI 스윙 🆕</option>
                    </select>
                </div>
                <div>
                    <label className="block text-sm text-slate-400 mb-2">최소 점수</label>
                    <select
                        value={minScore}
                        onChange={(e) => setMinScore(Number(e.target.value))}
                        className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-primary"
                    >
                        <option value="50">50점 이상</option>
                        <option value="60">60점 이상</option>
                        <option value="70">70점 이상 (추천)</option>
                        <option value="80">80점 이상</option>
                    </select>
                </div>
            </div>

            {/* Loading */}
            {loading && (
                <div className="flex items-center justify-center py-20">
                    <Loader2 className="animate-spin text-primary mr-3" size={28} />
                    <span className="text-slate-400">신호 스캔 중...</span>
                </div>
            )}

            {/* Error */}
            {error && !loading && (
                <div className="flex items-center gap-3 bg-red-500/10 border border-red-500/50 rounded-lg p-4 text-red-400">
                    <AlertCircle size={20} />
                    <span>{error}</span>
                </div>
            )}

            {/* Signals List */}
            {!loading && !error && (
                <div className="flex-1 overflow-y-auto">
                    {signals.length === 0 ? (
                        <div className="text-center py-20 text-slate-500">
                            <p className="text-lg">현재 진입 신호가 없습니다</p>
                            <p className="text-sm mt-2">최소 점수를 낮춰보세요</p>
                        </div>
                    ) : (
                        <div className="grid gap-4">
                            {signals.map((signal, idx) => (
                                <div
                                    key={idx}
                                    ref={el => { signalRefs.current[signal.code] = el; }}
                                    className={`border rounded-xl p-5 transition-all ${getSignalColor(signal)} ${
                                        focusCode === signal.code ? 'ring-2 ring-white/60 shadow-lg' : ''
                                    }`}
                                >
                                    {/* Header */}
                                    <div className="flex items-start justify-between mb-4">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-2 flex-wrap">
                                                <h3 className="text-xl font-bold">
                                                    {signal.stock_info?.name
                                                        ? `${signal.stock_info.name}(${signal.code})`
                                                        : signal.code}
                                                </h3>
                                                <span className={`px-2 py-1 rounded text-xs font-bold ${getStrengthBadge(signal.strength)}`}>
                                                    {signal.strength.toUpperCase()}
                                                </span>
                                                {signal.cup_handle_confirmed && (
                                                    <span className="px-2 py-1 rounded text-xs font-bold bg-purple-600 text-white" title="컵앤핸들 패턴 감지">
                                                        ☕ C&H
                                                    </span>
                                                )}
                                                {signal.cup_handle_confirmed && signal.signal !== 'BUY' && (
                                                    <span className="px-2 py-1 rounded text-xs font-medium bg-purple-900/60 text-purple-300">
                                                        패턴 진입
                                                    </span>
                                                )}
                                            </div>
                                            {signal.current_price && (
                                                <div className="flex items-center gap-1 text-slate-300">
                                                    <span className="text-sm">[주가 :</span>
                                                    <span className="text-2xl font-bold font-mono">
                                                        {market === 'US' ? '$' : ''}{signal.current_price.toLocaleString()}{market === 'KR' ? '원' : ''}
                                                    </span>
                                                    <span className="text-sm">]</span>
                                                </div>
                                            )}
                                        </div>
                                        <div className="text-right ml-3 shrink-0">
                                            <div className="text-3xl font-bold">{signal.score.toFixed(0)}</div>
                                            <div className="text-xs text-slate-400">점수</div>
                                        </div>
                                    </div>

                                    {/* Breakdown */}
                                    {signal.breakdown && (
                                        <div className="grid grid-cols-3 gap-3 mb-4">
                                            {signal.breakdown.volume && (
                                                <div className="bg-slate-900/30 rounded-lg p-3">
                                                    <div className="text-xs text-slate-400 mb-1">거래량</div>
                                                    <div className="text-lg font-bold">{signal.breakdown.volume.score.toFixed(0)}</div>
                                                </div>
                                            )}
                                            {signal.breakdown.technical && (
                                                <div className="bg-slate-900/30 rounded-lg p-3">
                                                    <div className="text-xs text-slate-400 mb-1">기술적 지표</div>
                                                    <div className="text-lg font-bold">{signal.breakdown.technical.score.toFixed(0)}</div>
                                                </div>
                                            )}
                                            {signal.breakdown.pattern && (
                                                <div className="bg-slate-900/30 rounded-lg p-3">
                                                    <div className="text-xs text-slate-400 mb-1">패턴</div>
                                                    <div className="text-lg font-bold">{signal.breakdown.pattern.score.toFixed(0)}</div>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Cup & Handle Detail */}
                                    {signal.cup_handle && (
                                        <div className={`mb-4 rounded-lg p-3 border ${
                                            signal.cup_handle_confirmed
                                                ? 'bg-purple-900/20 border-purple-700/50'
                                                : signal.cup_handle.breakout_status === 'expired'
                                                    ? 'bg-slate-800/40 border-slate-600/50'
                                                    : 'bg-slate-800/40 border-slate-600/50'
                                        }`}>
                                            <div className={`text-xs mb-2 font-semibold flex items-center gap-1 ${
                                                signal.cup_handle_confirmed ? 'text-purple-300' : 'text-slate-400'
                                            }`}>
                                                ☕ 컵앤핸들 패턴
                                                {signal.cup_handle.breakout_status && (
                                                    <span className={`ml-1 px-1.5 py-0.5 rounded text-xs ${
                                                        signal.cup_handle.breakout_status === 'fresh' ? 'bg-purple-600 text-white' :
                                                        signal.cup_handle.breakout_status === 'pre' ? 'bg-orange-500 text-white' :
                                                        signal.cup_handle.breakout_status === 'expired' ? 'bg-slate-600 text-slate-300' :
                                                        'bg-slate-700 text-slate-400'
                                                    }`}>
                                                        {signal.cup_handle.breakout_status === 'fresh' ? '돌파 확인' :
                                                         signal.cup_handle.breakout_status === 'pre' ? '돌파 임박' :
                                                         signal.cup_handle.breakout_status === 'expired' ? '기회 소멸' : '형성 중'}
                                                    </span>
                                                )}
                                                <span className={`ml-auto font-bold ${signal.cup_handle_confirmed ? 'text-purple-400' : 'text-slate-500'}`}>
                                                    {signal.cup_handle.score}점
                                                </span>
                                            </div>
                                            <ul className="space-y-1">
                                                {signal.cup_handle.reasons.map((r, i) => (
                                                    <li key={i} className={`text-xs flex items-start gap-2 ${
                                                        signal.cup_handle_confirmed ? 'text-purple-200' : 'text-slate-500'
                                                    }`}>
                                                        <span className={`mt-0.5 ${signal.cup_handle_confirmed ? 'text-purple-400' : 'text-slate-600'}`}>◆</span>
                                                        <span>{r}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}

                                    {/* Reasons */}
                                    <div>
                                        <div className="text-xs text-slate-400 mb-2 font-semibold">신호 발생 이유:</div>
                                        <ul className="space-y-1">
                                            {signal.reasons.map((reason, i) => (
                                                <li key={i} className="text-sm flex items-start gap-2">
                                                    <span className="text-green-400 mt-0.5">▸</span>
                                                    <span>{reason}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>

                                    {/* Timestamp */}
                                    <div className="mt-4 pt-3 border-t border-slate-700/50 text-xs text-slate-500">
                                        {new Date(signal.timestamp).toLocaleString('ko-KR')}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
