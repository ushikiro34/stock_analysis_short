import { useState } from 'react';
import { runQuickOptimize, type OptimizeRequest, type OptimizeResult, type Market } from '../lib/api';
import { Settings, Loader2, Play, Award, TrendingUp } from 'lucide-react';

interface OptimizeDashboardProps {
    market: Market;
}

export default function OptimizeDashboard({ market }: OptimizeDashboardProps) {
    const [result, setResult] = useState<OptimizeResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Form state
    const [symbols, setSymbols] = useState('AAPL,TSLA,NVDA');
    const [days, setDays] = useState(60);
    const [metric, setMetric] = useState('sharpe_ratio');

    const handleRun = async () => {
        setLoading(true);
        setError(null);
        setResult(null);

        const symbolList = symbols.split(',').map(s => s.trim()).filter(Boolean);

        if (symbolList.length === 0) {
            setError('최소 1개의 종목 코드를 입력하세요');
            setLoading(false);
            return;
        }

        const request: OptimizeRequest = {
            symbols: symbolList,
            market,
            days,
            optimization_metric: metric
        };

        try {
            const data = await runQuickOptimize(request);
            setResult(data);
        } catch (err: any) {
            setError(err?.message || '최적화 실행 실패');
        } finally {
            setLoading(false);
        }
    };

    const metricOptions = [
        { value: 'roi', label: '수익률 (ROI)', desc: '총 수익률 극대화' },
        { value: 'sharpe_ratio', label: 'Sharpe Ratio', desc: '위험 대비 수익률 (추천)' },
        { value: 'sortino_ratio', label: 'Sortino Ratio', desc: '하방 위험 최소화' },
        { value: 'calmar_ratio', label: 'Calmar Ratio', desc: 'MDD 대비 수익률' },
        { value: 'win_rate', label: '승률', desc: '거래 성공 비율' },
        { value: 'profit_factor', label: 'Profit Factor', desc: '손익비 최적화' }
    ];

    return (
        <div className="h-full flex gap-6">
            {/* Left Panel: Controls */}
            <aside className="w-96 shrink-0 space-y-4">
                <div>
                    <h2 className="text-2xl font-bold flex items-center gap-2 mb-4">
                        <Settings className="text-orange-400" size={28} />
                        파라미터 최적화
                    </h2>
                    <p className="text-slate-400 text-sm">
                        Grid Search로 최적의 매매 파라미터를 자동 탐색합니다
                    </p>
                </div>

                <div className="space-y-4 bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                    {/* Symbols */}
                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-2">
                            종목 코드 (쉼표로 구분)
                        </label>
                        <input
                            type="text"
                            value={symbols}
                            onChange={(e) => setSymbols(e.target.value)}
                            placeholder="AAPL,TSLA,NVDA"
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                        />
                    </div>

                    {/* Days */}
                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-2">
                            백테스팅 기간 (일)
                        </label>
                        <input
                            type="number"
                            value={days}
                            onChange={(e) => setDays(Number(e.target.value))}
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                        />
                        <p className="text-xs text-slate-500 mt-1">60일 권장 (빠른 실행)</p>
                    </div>

                    {/* Optimization Metric */}
                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-2">
                            최적화 지표
                        </label>
                        <select
                            value={metric}
                            onChange={(e) => setMetric(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                        >
                            {metricOptions.map(opt => (
                                <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                </option>
                            ))}
                        </select>
                        <p className="text-xs text-slate-500 mt-1">
                            {metricOptions.find(o => o.value === metric)?.desc}
                        </p>
                    </div>

                    {/* Info Box */}
                    <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 text-xs text-blue-300">
                        <strong className="block mb-1">빠른 최적화</strong>
                        제한된 파라미터 범위에서 빠르게 최적화를 수행합니다. 약 1-3분 소요됩니다.
                    </div>

                    {/* Run Button */}
                    <button
                        onClick={handleRun}
                        disabled={loading}
                        className="w-full flex items-center justify-center gap-2 bg-primary hover:bg-primary/80 disabled:opacity-50 rounded-lg py-3 font-semibold transition-colors"
                    >
                        {loading ? (
                            <>
                                <Loader2 className="animate-spin" size={18} />
                                최적화 중... (1-3분)
                            </>
                        ) : (
                            <>
                                <Play size={18} />
                                최적화 실행
                            </>
                        )}
                    </button>
                </div>
            </aside>

            {/* Right Panel: Results */}
            <main className="flex-1 overflow-y-auto">
                {error && (
                    <div className="bg-red-500/10 border border-red-500/50 rounded-lg p-4 text-red-400 mb-4">
                        {error}
                    </div>
                )}

                {!result && !loading && !error && (
                    <div className="flex items-center justify-center h-full text-slate-500">
                        <div className="text-center">
                            <Settings size={64} className="mx-auto mb-4 opacity-20" />
                            <p className="text-lg">좌측에서 파라미터를 설정하고 최적화를 실행하세요</p>
                            <p className="text-sm mt-2">실행 시간: 약 1-3분</p>
                        </div>
                    </div>
                )}

                {result && (
                    <div className="space-y-6">
                        {/* Summary */}
                        <div className="bg-gradient-to-r from-orange-500/10 to-purple-500/10 border border-orange-500/30 rounded-xl p-6">
                            <div className="flex items-start justify-between mb-4">
                                <div>
                                    <h3 className="text-2xl font-bold flex items-center gap-2">
                                        <Award className="text-orange-400" />
                                        최적화 완료!
                                    </h3>
                                    <p className="text-slate-400 text-sm mt-1">
                                        {result.total_combinations_tested}개 조합 테스트 완료
                                    </p>
                                </div>
                                <div className="text-right">
                                    <div className="text-sm text-slate-400">실행 시간</div>
                                    <div className="text-2xl font-bold">{result.execution_time_seconds?.toFixed(1)}초</div>
                                </div>
                            </div>
                        </div>

                        {/* Best Parameters */}
                        {result.best_params && (
                            <div className="bg-surface p-6 rounded-xl border border-slate-700">
                                <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                                    <TrendingUp className="text-green-400" />
                                    최적 파라미터
                                </h3>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="bg-slate-800/50 p-4 rounded-lg">
                                        <div className="text-xs text-slate-400 mb-1">손절 비율</div>
                                        <div className="text-2xl font-bold text-red-400">
                                            {(result.best_params.stop_loss_ratio * 100).toFixed(1)}%
                                        </div>
                                    </div>
                                    <div className="bg-slate-800/50 p-4 rounded-lg">
                                        <div className="text-xs text-slate-400 mb-1">익절 비율</div>
                                        <div className="text-2xl font-bold text-green-400">
                                            +{(result.best_params.take_profit_ratio * 100).toFixed(1)}%
                                        </div>
                                    </div>
                                    <div className="bg-slate-800/50 p-4 rounded-lg">
                                        <div className="text-xs text-slate-400 mb-1">최대 보유 기간</div>
                                        <div className="text-2xl font-bold text-blue-400">
                                            {result.best_params.max_holding_days}일
                                        </div>
                                    </div>
                                    <div className="bg-slate-800/50 p-4 rounded-lg">
                                        <div className="text-xs text-slate-400 mb-1">최소 진입 점수</div>
                                        <div className="text-2xl font-bold text-purple-400">
                                            {result.best_params.min_entry_score}점
                                        </div>
                                    </div>
                                    <div className="bg-slate-800/50 p-4 rounded-lg col-span-2">
                                        <div className="text-xs text-slate-400 mb-1">포지션 크기</div>
                                        <div className="text-2xl font-bold text-orange-400">
                                            {(result.best_params.position_size_pct * 100).toFixed(0)}%
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Best Performance */}
                        {result.best_performance && (
                            <div className="bg-surface p-6 rounded-xl border border-slate-700">
                                <h3 className="text-lg font-bold mb-4">최적 성과</h3>
                                <div className="grid grid-cols-3 gap-4">
                                    <div>
                                        <div className="text-xs text-slate-400 mb-1">ROI</div>
                                        <div className={`text-2xl font-bold ${result.best_performance.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {result.best_performance.roi >= 0 ? '+' : ''}{result.best_performance.roi.toFixed(2)}%
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-slate-400 mb-1">Sharpe Ratio</div>
                                        <div className="text-2xl font-bold text-blue-400">
                                            {result.best_performance.sharpe_ratio.toFixed(2)}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-slate-400 mb-1">승률</div>
                                        <div className="text-2xl font-bold text-purple-400">
                                            {result.best_performance.win_rate.toFixed(1)}%
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-slate-400 mb-1">총 거래</div>
                                        <div className="text-2xl font-bold text-slate-200">
                                            {result.best_performance.total_trades}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-slate-400 mb-1">MDD</div>
                                        <div className="text-2xl font-bold text-red-400">
                                            {result.best_performance.mdd.toFixed(2)}%
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Top 5 Results */}
                        {result.top_5_results && result.top_5_results.length > 0 && (
                            <div className="bg-surface p-6 rounded-xl border border-slate-700">
                                <h3 className="text-lg font-bold mb-4">상위 5개 결과</h3>
                                <div className="space-y-3">
                                    {result.top_5_results.map((item, idx) => (
                                        <div
                                            key={idx}
                                            className="bg-slate-800/50 p-4 rounded-lg border border-slate-700"
                                        >
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="text-lg font-bold text-slate-300">
                                                    #{idx + 1}
                                                </span>
                                                <span className={`text-xl font-bold ${item.performance.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    ROI: {item.performance.roi >= 0 ? '+' : ''}{item.performance.roi?.toFixed(2)}%
                                                </span>
                                            </div>
                                            <div className="grid grid-cols-4 gap-2 text-xs">
                                                <div>
                                                    <span className="text-slate-500">손절:</span>
                                                    <span className="ml-1 font-mono">{(item.params.stop_loss_ratio * 100).toFixed(1)}%</span>
                                                </div>
                                                <div>
                                                    <span className="text-slate-500">익절:</span>
                                                    <span className="ml-1 font-mono">+{(item.params.take_profit_ratio * 100).toFixed(1)}%</span>
                                                </div>
                                                <div>
                                                    <span className="text-slate-500">보유:</span>
                                                    <span className="ml-1 font-mono">{item.params.max_holding_days}일</span>
                                                </div>
                                                <div>
                                                    <span className="text-slate-500">진입:</span>
                                                    <span className="ml-1 font-mono">{item.params.min_entry_score}점</span>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Copy Parameters Button */}
                        <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
                            <p className="text-sm text-blue-300 mb-3">
                                <strong>다음 단계:</strong> 위의 최적 파라미터를 백테스팅 탭에서 사용하여 상세 검증을 진행하세요.
                            </p>
                            <button
                                onClick={() => {
                                    if (result.best_params) {
                                        const params = result.best_params;
                                        alert(`최적 파라미터:\n손절: ${(params.stop_loss_ratio * 100).toFixed(1)}%\n익절: ${(params.take_profit_ratio * 100).toFixed(1)}%\n보유 기간: ${params.max_holding_days}일\n진입 점수: ${params.min_entry_score}점`);
                                    }
                                }}
                                className="px-4 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg text-sm font-semibold transition-colors"
                            >
                                파라미터 복사
                            </button>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
