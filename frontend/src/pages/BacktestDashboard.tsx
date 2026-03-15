import { useState, useEffect } from 'react';
import { runBacktest, type BacktestRequest, type BacktestResult, type Market } from '../lib/api';
import { BarChart3, Loader2, Play, TrendingDown, TrendingUp } from 'lucide-react';
import type { OptimizedParams } from '../App';

interface BacktestDashboardProps {
    market: Market;
    optimizedParams?: OptimizedParams | null;
}

export default function BacktestDashboard({ market, optimizedParams }: BacktestDashboardProps) {
    const [result, setResult] = useState<BacktestResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Form state
    const [symbols, setSymbols] = useState('AAPL,TSLA,NVDA');
    const [days, setDays] = useState(90);
    const [initialCapital, setInitialCapital] = useState(10000);
    const [strategy, setStrategy] = useState('combined');
    const [minScore, setMinScore] = useState(60);
    const [stopLoss, setStopLoss] = useState(-0.02);
    const [maxHoldingDays, setMaxHoldingDays] = useState(5);

    // 최적화 파라미터 수신 시 폼 자동 적용
    const [appliedBanner, setAppliedBanner] = useState(false);
    useEffect(() => {
        if (!optimizedParams) return;
        setSymbols(optimizedParams.symbols);
        setDays(optimizedParams.days);
        setStopLoss(optimizedParams.stopLoss);
        setMinScore(optimizedParams.minScore);
        setMaxHoldingDays(optimizedParams.maxHoldingDays);
        setAppliedBanner(true);
        const t = setTimeout(() => setAppliedBanner(false), 4000);
        return () => clearTimeout(t);
    }, [optimizedParams?._appliedAt]);

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

        const request: BacktestRequest = {
            symbols: symbolList,
            market,
            days,
            initial_capital: initialCapital,
            entry_strategy: strategy,
            min_entry_score: minScore,
            stop_loss_ratio: stopLoss,
            max_holding_days: maxHoldingDays
        };

        try {
            const data = await runBacktest(request);
            setResult(data);
        } catch (err: any) {
            setError(err?.message || '백테스팅 실행 실패');
        } finally {
            setLoading(false);
        }
    };

    const getROIColor = (roi: number) => {
        if (roi > 10) return 'text-green-400';
        if (roi > 0) return 'text-blue-400';
        return 'text-red-400';
    };

    return (
        <div className="h-full flex gap-6">
            {/* Left Panel: Controls */}
            <aside className="w-96 shrink-0 space-y-4">
                <div>
                    <h2 className="text-2xl font-bold flex items-center gap-2 mb-4">
                        <BarChart3 className="text-blue-400" size={28} />
                        백테스팅
                    </h2>
                    {appliedBanner && (
                        <div className="flex items-center gap-2 px-3 py-2 bg-blue-500/20 border border-blue-500/50 rounded-lg text-sm text-blue-300 mb-2">
                            ✅ 최적화 파라미터가 적용되었습니다
                        </div>
                    )}
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
                    </div>

                    {/* Initial Capital */}
                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-2">
                            초기 자본금 ({market === 'US' ? '$' : '원'})
                        </label>
                        <input
                            type="number"
                            value={initialCapital}
                            onChange={(e) => setInitialCapital(Number(e.target.value))}
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                        />
                    </div>

                    {/* Strategy */}
                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-2">
                            진입 전략
                        </label>
                        <select
                            value={strategy}
                            onChange={(e) => setStrategy(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                        >
                            <option value="combined">종합 전략</option>
                            <option value="volume">거래량 기반</option>
                            <option value="technical">기술적 지표</option>
                            <option value="pattern">패턴 분석</option>
                            <option value="rsi_golden_cross">RSI 골든크로스 ⭐</option>
                            <option value="weekly_rsi_swing">주봉 RSI 스윙 🆕</option>
                        </select>
                    </div>

                    {/* Min Score */}
                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-2">
                            최소 진입 점수
                        </label>
                        <input
                            type="number"
                            value={minScore}
                            onChange={(e) => setMinScore(Number(e.target.value))}
                            min="0"
                            max="100"
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                        />
                    </div>

                    {/* Stop Loss */}
                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-2">
                            손절 비율 (%)
                        </label>
                        <input
                            type="number"
                            value={stopLoss * 100}
                            onChange={(e) => setStopLoss(Number(e.target.value) / 100)}
                            step="0.1"
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                        />
                    </div>

                    {/* Max Holding Days */}
                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-2">
                            최대 보유 기간 (일)
                        </label>
                        <input
                            type="number"
                            value={maxHoldingDays}
                            onChange={(e) => setMaxHoldingDays(Number(e.target.value))}
                            min="1"
                            max="30"
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                        />
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
                                실행 중...
                            </>
                        ) : (
                            <>
                                <Play size={18} />
                                백테스팅 실행
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
                            <BarChart3 size={64} className="mx-auto mb-4 opacity-20" />
                            <p className="text-lg">좌측에서 파라미터를 설정하고 백테스팅을 실행하세요</p>
                        </div>
                    </div>
                )}

                {result && (
                    <div className="space-y-6">
                        {/* Summary Cards */}
                        <div className="grid grid-cols-4 gap-4">
                            <div className="bg-surface p-5 rounded-xl border border-slate-700">
                                <div className="text-xs text-slate-400 mb-1">ROI</div>
                                <div className={`text-3xl font-bold ${getROIColor(result.summary.roi)}`}>
                                    {result.summary.roi > 0 ? '+' : ''}{result.summary.roi.toFixed(2)}%
                                </div>
                            </div>
                            <div className="bg-surface p-5 rounded-xl border border-slate-700">
                                <div className="text-xs text-slate-400 mb-1">총 거래</div>
                                <div className="text-3xl font-bold text-slate-200">{result.summary.total_trades}</div>
                            </div>
                            <div className="bg-surface p-5 rounded-xl border border-slate-700">
                                <div className="text-xs text-slate-400 mb-1">승률</div>
                                <div className="text-3xl font-bold text-blue-400">{result.summary.win_rate.toFixed(1)}%</div>
                            </div>
                            <div className="bg-surface p-5 rounded-xl border border-slate-700">
                                <div className="text-xs text-slate-400 mb-1">MDD</div>
                                <div className="text-3xl font-bold text-red-400">{result.summary.max_drawdown.toFixed(2)}%</div>
                            </div>
                        </div>

                        {/* Performance Details */}
                        <div className="bg-surface p-6 rounded-xl border border-slate-700">
                            <h3 className="text-lg font-bold mb-4">성과 요약</h3>
                            <div className="grid grid-cols-2 gap-4 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-slate-400">초기 자본금</span>
                                    <span className="font-mono">{market === 'US' ? '$' : ''}{result.summary.initial_capital.toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-400">최종 자본금</span>
                                    <span className="font-mono">{market === 'US' ? '$' : ''}{result.summary.final_capital.toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-400">순수익</span>
                                    <span className={`font-mono ${result.summary.net_profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        {result.summary.net_profit >= 0 ? '+' : ''}{market === 'US' ? '$' : ''}{result.summary.net_profit.toLocaleString()}
                                    </span>
                                </div>
                                {(result.summary.average_profit_per_trade !== undefined || result.summary.avg_win !== undefined) && (
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">평균 거래 수익</span>
                                        <span className={`font-mono ${(result.summary.average_profit_per_trade || result.summary.avg_win || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {(result.summary.average_profit_per_trade || result.summary.avg_win || 0) >= 0 ? '+' : ''}
                                            {market === 'US' ? '$' : ''}
                                            {((result.summary.average_profit_per_trade || result.summary.avg_win || 0)).toLocaleString()}
                                        </span>
                                    </div>
                                )}
                                <div className="flex justify-between">
                                    <span className="text-slate-400">승리 거래</span>
                                    <span className="font-mono text-green-400">{result.summary.winning_trades}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-400">손실 거래</span>
                                    <span className="font-mono text-red-400">{result.summary.losing_trades}</span>
                                </div>
                                {result.summary.sharpe_ratio !== undefined && (
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">Sharpe Ratio</span>
                                        <span className="font-mono">{result.summary.sharpe_ratio.toFixed(2)}</span>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Advanced Metrics */}
                        {result.advanced_metrics && (
                            <div className="bg-surface p-6 rounded-xl border border-slate-700">
                                <h3 className="text-lg font-bold mb-4">고급 지표</h3>
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                    {result.advanced_metrics.sortino_ratio !== undefined && (
                                        <div className="flex justify-between">
                                            <span className="text-slate-400">Sortino Ratio</span>
                                            <span className="font-mono">{result.advanced_metrics.sortino_ratio.toFixed(2)}</span>
                                        </div>
                                    )}
                                    {result.advanced_metrics.calmar_ratio !== undefined && (
                                        <div className="flex justify-between">
                                            <span className="text-slate-400">Calmar Ratio</span>
                                            <span className="font-mono">{result.advanced_metrics.calmar_ratio.toFixed(2)}</span>
                                        </div>
                                    )}
                                    {result.advanced_metrics.profit_factor !== undefined && (
                                        <div className="flex justify-between">
                                            <span className="text-slate-400">Profit Factor</span>
                                            <span className="font-mono">{result.advanced_metrics.profit_factor.toFixed(2)}</span>
                                        </div>
                                    )}
                                    {result.advanced_metrics.expectancy !== undefined && (
                                        <div className="flex justify-between">
                                            <span className="text-slate-400">Expectancy</span>
                                            <span className="font-mono">{result.advanced_metrics.expectancy.toFixed(2)}</span>
                                        </div>
                                    )}
                                    {result.summary.avg_win !== undefined && result.summary.avg_win > 0 && (
                                        <div className="flex justify-between">
                                            <span className="text-slate-400">평균 수익</span>
                                            <span className="font-mono text-green-400">
                                                +{market === 'US' ? '$' : ''}{result.summary.avg_win.toFixed(2)}
                                            </span>
                                        </div>
                                    )}
                                    {result.summary.avg_loss !== undefined && result.summary.avg_loss !== 0 && (
                                        <div className="flex justify-between">
                                            <span className="text-slate-400">평균 손실</span>
                                            <span className="font-mono text-red-400">
                                                {market === 'US' ? '$' : ''}{Math.abs(result.summary.avg_loss).toFixed(2)}
                                            </span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Trades Table */}
                        {result.trades && result.trades.length > 0 && (
                            <div className="bg-surface p-6 rounded-xl border border-slate-700">
                                <h3 className="text-lg font-bold mb-4">거래 내역 (최근 10건)</h3>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead className="text-xs text-slate-400 border-b border-slate-700">
                                            <tr>
                                                <th className="text-left py-2">종목</th>
                                                <th className="text-left py-2">진입일</th>
                                                <th className="text-left py-2">청산일</th>
                                                <th className="text-right py-2">진입가</th>
                                                <th className="text-right py-2">청산가</th>
                                                <th className="text-right py-2">수익률</th>
                                                <th className="text-right py-2">손익</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {result.trades.slice(0, 10).map((trade, idx) => (
                                                <tr key={idx} className="border-b border-slate-800">
                                                    <td className="py-3 font-mono">{trade.symbol || trade.code}</td>
                                                    <td className="py-3 text-xs">{trade.entry_date || trade.entry_time}</td>
                                                    <td className="py-3 text-xs">{trade.exit_date || trade.exit_time}</td>
                                                    <td className="text-right py-3 font-mono text-xs">
                                                        {market === 'US' ? '$' : ''}{trade.entry_price.toFixed(2)}
                                                    </td>
                                                    <td className="text-right py-3 font-mono text-xs">
                                                        {market === 'US' ? '$' : ''}{trade.exit_price.toFixed(2)}
                                                    </td>
                                                    <td className={`text-right py-3 font-mono ${trade.profit_loss_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                        {trade.profit_loss_pct >= 0 ? '+' : ''}{trade.profit_loss_pct.toFixed(2)}%
                                                    </td>
                                                    <td className={`text-right py-3 font-mono ${trade.profit_loss >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                        {trade.profit_loss >= 0 ? '+' : ''}{market === 'US' ? '$' : ''}{trade.profit_loss.toFixed(2)}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}
