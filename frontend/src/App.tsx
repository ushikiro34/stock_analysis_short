import { useState, useEffect, useRef, useCallback } from 'react';
import { TrendingUp, Activity, BarChart3, Settings, Search, Bell, X, PlayCircle, Terminal, RefreshCw, Trash2, BookOpen, Star } from 'lucide-react';
import type { Market, LogEntry, MonitorStatus } from './lib/api';
import { scanSignals, monitor } from './lib/api';

// Import page components
import StocksDashboard from './pages/StocksDashboard';
import SignalsDashboard from './pages/SignalsDashboard';
import BacktestDashboard from './pages/BacktestDashboard';
import OptimizeDashboard from './pages/OptimizeDashboard';
import PaperTradingDashboard from './pages/PaperTradingDashboard';
import InvestmentJournalDashboard from './pages/InvestmentJournalDashboard';
import WatchlistDashboard from './pages/WatchlistDashboard';

type Tab = 'stocks' | 'signals' | 'backtest' | 'optimize' | 'paper' | 'journal' | 'watchlist';

export type PriceFilter = 'all' | 'penny' | 'range';

interface SignalAlert {
    id: string;
    code: string;
    name?: string;
    currentPrice?: number;
    score: number;
    strength: string;
    market: Market;
    createdAt: number;
}

export interface StockFilter {
    priceFilter: PriceFilter;
    priceFrom?: number;
    priceTo?: number;
    stockName: string;
}

export interface OptimizedParams {
    symbols: string;
    days: number;
    stopLoss: number;
    minScore: number;
    maxHoldingDays: number;
    _appliedAt: number;
}

function App() {
    const [activeTab, setActiveTab] = useState<Tab>('stocks');
    const [market, setMarket] = useState<Market>('KR');

    // Optimized params shared between Optimize → Backtest tabs
    const [optimizedParams, setOptimizedParams] = useState<OptimizedParams | null>(null);

    const handleApplyOptimizedParams = useCallback((params: OptimizedParams) => {
        setOptimizedParams(params);
        setActiveTab('backtest');
    }, []);

    // Stock filter state
    const [stockFilter, setStockFilter] = useState<StockFilter>({
        priceFilter: 'all',
        priceFrom: undefined,
        priceTo: undefined,
        stockName: ''
    });

    const handleMarketChange = (m: Market) => {
        setMarket(m);
        // range일 때만 수치 초기화 (원/달러 혼용 방지), all/penny는 그대로 유지
        setStockFilter(f => f.priceFilter === 'range'
            ? { ...f, priceFrom: undefined, priceTo: undefined }
            : f
        );
    };

    // ── Signal Alert System ────────────────────────────────────
    const [alerts, setAlerts] = useState<SignalAlert[]>([]);          // 토스트용 (8초 자동 소멸)
    const [alertHistory, setAlertHistory] = useState<SignalAlert[]>([]); // 영구 이력 (최대 10개)
    const [focusSignalCode, setFocusSignalCode] = useState<string | undefined>();
    const [pollError, setPollError] = useState(false);
    const [showAlertPanel, setShowAlertPanel] = useState(false);
    const bellWrapperRef = useRef<HTMLDivElement>(null);
    const seenKeysRef = useRef(new Set<string>());
    const isFirstPollRef = useRef(true);

    const fmtAlertTime = (ts: number) =>
        new Date(ts).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    // 벨 패널 외부 클릭 시 닫기
    useEffect(() => {
        if (!showAlertPanel) return;
        const handleClick = (e: MouseEvent) => {
            if (bellWrapperRef.current && !bellWrapperRef.current.contains(e.target as Node)) {
                setShowAlertPanel(false);
            }
        };
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, [showAlertPanel]);

    const dismissAlert = (id: string) => setAlerts(prev => prev.filter(a => a.id !== id));
    const dismissHistory = (id: string) => setAlertHistory(prev => prev.filter(a => a.id !== id));
    const clearHistory = () => setAlertHistory([]);

    // 이력 패널: 이동만 하고 삭제하지 않음
    const handleAlertNavClick = (code: string) => {
        setActiveTab('signals');
        setFocusSignalCode(code);
        setShowAlertPanel(false);
    };

    // 토스트 클릭: 신호 탭 이동 + 토스트 제거 (이력은 유지)
    const handleAlertClick = (code: string, alertId: string) => {
        setActiveTab('signals');
        setFocusSignalCode(code);
        dismissAlert(alertId);
    };

    // 브라우저 알림 권한 요청
    useEffect(() => {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }, []);

    // 2분마다 신호 폴링
    useEffect(() => {
        seenKeysRef.current = new Set();
        isFirstPollRef.current = true;

        const poll = async () => {
            try {
                const data = await scanSignals(market, 'combined', 65);
                if (!isFirstPollRef.current) {
                    const newSignals = data.filter(s => !seenKeysRef.current.has(`${s.code}-${s.timestamp}`));
                    if (newSignals.length > 0) {
                        const newAlerts: SignalAlert[] = newSignals.map(s => ({
                            id: `${s.code}-${Date.now()}-${Math.random()}`,
                            code: s.code,
                            name: s.stock_info?.name,
                            currentPrice: s.current_price,
                            score: s.score,
                            strength: s.strength,
                            market,
                            createdAt: Date.now(),
                        }));
                        // 토스트: 8초 후 자동 소멸
                        setAlerts(prev => [...newAlerts, ...prev].slice(0, 20));
                        newAlerts.forEach(alert => {
                            setTimeout(() => setAlerts(prev => prev.filter(a => a.id !== alert.id)), 8000);
                        });
                        // 이력: 최대 10개 영구 보관
                        setAlertHistory(prev => [...newAlerts, ...prev].slice(0, 10));
                        if ('Notification' in window && Notification.permission === 'granted') {
                            newSignals.slice(0, 3).forEach(s => {
                                const name = s.stock_info?.name || s.code;
                                const priceStr = s.current_price
                                    ? `${market === 'KR' ? '' : '$'}${s.current_price.toLocaleString()}${market === 'KR' ? '원' : ''}`
                                    : '';
                                new Notification(`매수 신호: ${name}(${s.code})`, {
                                    body: `점수: ${s.score.toFixed(0)}점${priceStr ? ` | ${priceStr}` : ''}`,
                                    tag: `signal-${s.code}`,
                                });
                            });
                        }
                    }
                }
                data.forEach(s => seenKeysRef.current.add(`${s.code}-${s.timestamp}`));
                isFirstPollRef.current = false;
            } catch { setPollError(true); return; }
            setPollError(false);
        };

        poll();
        const interval = setInterval(poll, 120000);
        return () => clearInterval(interval);
    }, [market]);

    // ── Monitor Panel ──────────────────────────────────────────
    const [showMonitor, setShowMonitor] = useState(false);
    const [monitorLogs, setMonitorLogs] = useState<LogEntry[]>([]);
    const [monitorStatus, setMonitorStatus] = useState<MonitorStatus | null>(null);
    const [monitorLevel, setMonitorLevel] = useState<'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'>('INFO');
    const [monitorLoading, setMonitorLoading] = useState(false);
    const logsEndRef = useRef<HTMLDivElement>(null);
    const monitorPanelRef = useRef<HTMLDivElement>(null);

    const fetchMonitorData = useCallback(async () => {
        setMonitorLoading(true);
        try {
            const [logs, status] = await Promise.all([
                monitor.getLogs(monitorLevel, 200),
                monitor.getStatus(),
            ]);
            setMonitorLogs(logs);
            setMonitorStatus(status);
        } catch { /* silent */ }
        setMonitorLoading(false);
    }, [monitorLevel]);

    useEffect(() => {
        if (!showMonitor) return;
        fetchMonitorData();
        const iv = setInterval(fetchMonitorData, 5000);
        return () => clearInterval(iv);
    }, [showMonitor, fetchMonitorData]);

    // 자동 스크롤
    useEffect(() => {
        if (showMonitor) logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [monitorLogs, showMonitor]);

    // 외부 클릭시 닫기
    useEffect(() => {
        if (!showMonitor) return;
        const handleClick = (e: MouseEvent) => {
            if (monitorPanelRef.current && !monitorPanelRef.current.contains(e.target as Node)) {
                setShowMonitor(false);
            }
        };
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, [showMonitor]);

    const handleClearLogs = async () => {
        await monitor.clearLogs();
        setMonitorLogs([]);
    };

    const taskColor = (status: string) => {
        if (status === 'running') return 'text-green-400';
        if (status === 'not_started') return 'text-slate-500';
        return 'text-red-400';
    };

    const logLevelColor = (level: string) => {
        if (level === 'ERROR') return 'text-red-400';
        if (level === 'WARNING') return 'text-yellow-400';
        if (level === 'INFO') return 'text-green-400';
        return 'text-slate-500';
    };

    // 종목명 검색 - 엔터 또는 조회 버튼으로만 실행
    const [stockNameInput, setStockNameInput] = useState('');
    const handleStockNameSearch = () => {
        setStockFilter(f => ({ ...f, stockName: stockNameInput }));
    };

    const tabs = [
        { id: 'stocks' as Tab, label: '주식 분석', icon: Activity, color: 'text-blue-400' },
        { id: 'signals' as Tab, label: '매매 신호', icon: TrendingUp, color: 'text-green-400' },
        { id: 'backtest' as Tab, label: '백테스팅', icon: BarChart3, color: 'text-purple-400' },
        { id: 'optimize' as Tab, label: '최적화', icon: Settings, color: 'text-orange-400' },
        { id: 'paper' as Tab, label: '모의투자', icon: PlayCircle, color: 'text-cyan-400' },
        { id: 'journal' as Tab, label: '투자일지', icon: BookOpen, color: 'text-amber-400' },
        { id: 'watchlist' as Tab, label: '관심종목', icon: Star, color: 'text-yellow-400' },
    ];

    return (
        <div className="h-screen flex flex-col bg-background text-slate-100">
            {/* Top Navigation Bar */}
            <header className="border-b border-slate-700 bg-surface">
                <div className="flex items-center justify-between px-6 py-4">
                    {/* Logo & Title */}
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
                            <Activity size={24} className="text-white" />
                        </div>
                        <div>
                            <h1 className="text-xl font-bold">Stock Analysis System</h1>
                            <p className="text-xs text-slate-400">단타매매 전문 시스템 v2.0</p>
                        </div>
                    </div>

                    {/* Notification Bell + Monitor + Market Selector */}
                    <div className="flex items-center gap-3">
                        {/* Monitor Button */}
                        <div ref={monitorPanelRef} className="relative">
                            <button
                                onClick={() => setShowMonitor(v => !v)}
                                title="서버 모니터링"
                                className="relative p-1 rounded hover:bg-slate-700 transition-colors"
                            >
                                <Terminal size={20} className={showMonitor ? 'text-cyan-400' : 'text-slate-500'} />
                            </button>

                            {/* Monitor Panel */}
                            {showMonitor && (
                                <div className="absolute top-10 right-0 w-[560px] bg-slate-900 border border-slate-600 rounded-xl shadow-2xl z-50 flex flex-col overflow-hidden" style={{ maxHeight: '520px' }}>
                                    {/* Header */}
                                    <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700 shrink-0">
                                        <div className="flex items-center gap-3">
                                            <Terminal size={14} className="text-cyan-400" />
                                            <span className="text-sm font-semibold text-cyan-400">서버 모니터</span>
                                            {monitorStatus && (
                                                <span className="text-xs text-slate-400">
                                                    uptime {Math.floor(monitorStatus.uptime_seconds / 60)}m
                                                </span>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <button onClick={fetchMonitorData} title="새로고침" className="p-1 hover:text-white text-slate-400 transition-colors">
                                                <RefreshCw size={13} className={monitorLoading ? 'animate-spin' : ''} />
                                            </button>
                                            <button onClick={handleClearLogs} title="로그 지우기" className="p-1 hover:text-red-400 text-slate-400 transition-colors">
                                                <Trash2 size={13} />
                                            </button>
                                            <button onClick={() => setShowMonitor(false)} className="p-1 hover:text-white text-slate-400 transition-colors">
                                                <X size={13} />
                                            </button>
                                        </div>
                                    </div>

                                    {/* Task Status */}
                                    {monitorStatus && (
                                        <div className="flex items-center gap-4 px-4 py-2 border-b border-slate-700/60 bg-slate-800/50 shrink-0 text-xs">
                                            {Object.entries(monitorStatus.tasks).map(([name, st]) => (
                                                <div key={name} className="flex items-center gap-1.5">
                                                    <span className={`w-1.5 h-1.5 rounded-full ${st === 'running' ? 'bg-green-400' : st === 'not_started' ? 'bg-slate-500' : 'bg-red-400'}`} />
                                                    <span className="text-slate-400">{name}</span>
                                                    <span className={taskColor(st)}>{st}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    {/* Level Filter */}
                                    <div className="flex items-center gap-1 px-4 py-2 border-b border-slate-700/60 shrink-0">
                                        {(['DEBUG', 'INFO', 'WARNING', 'ERROR'] as const).map(lv => (
                                            <button
                                                key={lv}
                                                onClick={() => setMonitorLevel(lv)}
                                                className={`px-2 py-0.5 rounded text-xs font-mono transition-colors ${monitorLevel === lv ? 'bg-slate-600 text-white' : 'text-slate-500 hover:text-slate-300'}`}
                                            >
                                                {lv}
                                            </button>
                                        ))}
                                        <span className="ml-auto text-xs text-slate-600">{monitorLogs.length}줄</span>
                                    </div>

                                    {/* Log Output */}
                                    <div className="flex-1 overflow-y-auto font-mono text-xs p-3 space-y-0.5 bg-slate-950">
                                        {monitorLogs.length === 0 ? (
                                            <div className="text-slate-600 text-center py-8">로그 없음</div>
                                        ) : (
                                            monitorLogs.map((log, i) => (
                                                <div key={i} className="flex gap-2 leading-5">
                                                    <span className="text-slate-600 shrink-0">{log.ts}</span>
                                                    <span className={`shrink-0 w-14 ${logLevelColor(log.level)}`}>{log.level}</span>
                                                    <span className="text-slate-500 shrink-0 w-20 truncate">{log.logger}</span>
                                                    <span className="text-slate-300 break-all">{log.msg}</span>
                                                </div>
                                            ))
                                        )}
                                        <div ref={logsEndRef} />
                                    </div>
                                </div>
                            )}
                        </div>

                        <div ref={bellWrapperRef} className="relative">
                            <button
                                onClick={() => setShowAlertPanel(v => !v)}
                                title={pollError ? '신호 폴링 실패 — 네트워크를 확인하세요' : '알림 목록'}
                                className="relative p-1 rounded hover:bg-slate-700 transition-colors"
                            >
                                <Bell size={20} className={pollError ? 'text-red-400' : alertHistory.length > 0 ? 'text-green-400' : 'text-slate-500'} />
                                {pollError && (
                                    <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-xs font-bold rounded-full w-4 h-4 flex items-center justify-center leading-none">!</span>
                                )}
                                {!pollError && alertHistory.length > 0 && (
                                    <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-xs font-bold rounded-full w-4 h-4 flex items-center justify-center leading-none">
                                        {alertHistory.length}
                                    </span>
                                )}
                            </button>

                            {/* 전체 알림 패널 */}
                            {showAlertPanel && (
                                <div className="absolute top-10 right-0 w-80 bg-slate-800 border border-slate-600 rounded-xl shadow-2xl z-50 overflow-hidden">
                                    <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
                                        <span className="text-sm font-semibold">
                                            신호 알림 이력
                                            <span className="ml-1.5 text-xs text-slate-400 font-normal">
                                                {alertHistory.length}/10
                                            </span>
                                        </span>
                                        <button
                                            onClick={clearHistory}
                                            className="text-xs text-slate-400 hover:text-red-400 transition-colors"
                                        >
                                            모두 지우기
                                        </button>
                                    </div>
                                    {alertHistory.length === 0 ? (
                                        <div className="px-4 py-6 text-center text-sm text-slate-500">알림 없음</div>
                                    ) : (
                                        <div className="max-h-[420px] overflow-y-auto divide-y divide-slate-700/50">
                                            {alertHistory.map(alert => (
                                                <div key={alert.id} className="flex items-start gap-2 px-4 py-3 hover:bg-slate-700/40 transition-colors group">
                                                    {/* 클릭 → 신호 탭 이동 (이력은 유지) */}
                                                    <div
                                                        className="flex-1 min-w-0 cursor-pointer"
                                                        onClick={() => handleAlertNavClick(alert.code)}
                                                    >
                                                        <div className="flex items-center gap-1.5 mb-0.5">
                                                            <span className="font-semibold text-sm truncate">
                                                                {alert.name ? `${alert.name}(${alert.code})` : alert.code}
                                                            </span>
                                                        </div>
                                                        <div className="flex items-center gap-2 text-xs text-slate-400">
                                                            <span>
                                                                점수: <span className="text-white font-bold">{alert.score.toFixed(0)}</span>
                                                            </span>
                                                            <span className={`font-semibold ${alert.strength === 'high' ? 'text-green-400' : alert.strength === 'medium' ? 'text-yellow-400' : 'text-slate-400'}`}>
                                                                {alert.strength.toUpperCase()}
                                                            </span>
                                                            {alert.currentPrice && (
                                                                <span className="font-mono">
                                                                    {alert.market === 'US' ? '$' : ''}
                                                                    {alert.currentPrice.toLocaleString()}
                                                                    {alert.market === 'KR' ? '원' : ''}
                                                                </span>
                                                            )}
                                                        </div>
                                                        <div className="text-xs text-slate-500 mt-0.5">
                                                            {fmtAlertTime(alert.createdAt)}
                                                        </div>
                                                    </div>
                                                    {/* 개별 삭제 버튼 */}
                                                    <button
                                                        onClick={() => dismissHistory(alert.id)}
                                                        title="삭제"
                                                        className="mt-0.5 text-slate-600 hover:text-red-400 shrink-0 transition-colors opacity-0 group-hover:opacity-100"
                                                    >
                                                        <X size={14} />
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                        <div className="flex gap-2 bg-slate-800 rounded-lg p-1">
                            <button
                                onClick={() => handleMarketChange('KR')}
                                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                                    market === 'KR'
                                        ? 'bg-primary text-white'
                                        : 'text-slate-400 hover:text-slate-200'
                                }`}
                            >
                                🇰🇷 한국
                            </button>
                            <button
                                onClick={() => handleMarketChange('US')}
                                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                                    market === 'US'
                                        ? 'bg-primary text-white'
                                        : 'text-slate-400 hover:text-slate-200'
                                }`}
                            >
                                🇺🇸 미국
                            </button>
                        </div>
                    </div>
                </div>

                {/* Tab Navigation + Filter */}
                <div className="flex items-center justify-between px-6">
                    {/* Tabs */}
                    <div className="flex gap-1">
                        {tabs.map(tab => {
                            const Icon = tab.icon;
                            const isActive = activeTab === tab.id;
                            return (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`flex items-center gap-2 px-5 py-3 font-medium transition-colors relative ${
                                        isActive
                                            ? 'text-white'
                                            : 'text-slate-400 hover:text-slate-200'
                                    }`}
                                >
                                    <Icon size={18} className={isActive ? tab.color : ''} />
                                    <span>{tab.label}</span>
                                    {isActive && (
                                        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
                                    )}
                                </button>
                            );
                        })}
                    </div>

                    {/* Stock Filter - Only show on stocks tab */}
                    {activeTab === 'stocks' && (
                        <div className="flex items-center gap-4 pb-3">
                            {/* Price Filter Radio */}
                            <div className="flex items-center gap-3 text-sm">
                                <label className="flex items-center gap-1 cursor-pointer">
                                    <input
                                        type="radio"
                                        checked={stockFilter.priceFilter === 'all'}
                                        onChange={() => setStockFilter({ ...stockFilter, priceFilter: 'all' })}
                                        className="w-4 h-4"
                                    />
                                    <span className="text-slate-300">전체</span>
                                </label>
                                <label className="flex items-center gap-1 cursor-pointer">
                                    <input
                                        type="radio"
                                        checked={stockFilter.priceFilter === 'penny'}
                                        onChange={() => setStockFilter({ ...stockFilter, priceFilter: 'penny' })}
                                        className="w-4 h-4"
                                    />
                                    <span className="text-slate-300 inline-block w-24">{market === 'KR' ? '1,000원 미만' : '$1 미만'}</span>
                                </label>
                                <label className="flex items-center gap-1 cursor-pointer">
                                    <input
                                        type="radio"
                                        checked={stockFilter.priceFilter === 'range'}
                                        onChange={() => setStockFilter({ ...stockFilter, priceFilter: 'range' })}
                                        className="w-4 h-4"
                                    />
                                    <span className="text-slate-300">가격 범위</span>
                                </label>
                            </div>

                            {/* Price Range Inputs - 항상 동일한 크기 유지 */}
                            <div className="flex items-center gap-2">
                                <span className="text-slate-400 text-sm w-4 text-right shrink-0">
                                    {market === 'US' ? '$' : ''}
                                </span>
                                <input
                                    type="number"
                                    placeholder={market === 'KR' ? '최소' : 'From'}
                                    value={stockFilter.priceFrom || ''}
                                    onChange={(e) => setStockFilter({
                                        ...stockFilter,
                                        priceFrom: e.target.value ? Number(e.target.value) : undefined,
                                        priceFilter: 'range'
                                    })}
                                    disabled={stockFilter.priceFilter !== 'range'}
                                    className={`w-28 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-sm focus:outline-none focus:border-primary ${
                                        stockFilter.priceFilter !== 'range' ? 'opacity-50 cursor-not-allowed' : ''
                                    }`}
                                />
                                <span className="text-slate-400 text-xs w-4 shrink-0">
                                    {market === 'KR' ? '원' : ''}
                                </span>
                                <span className="text-slate-500">~</span>
                                <span className="text-slate-400 text-sm w-4 text-right shrink-0">
                                    {market === 'US' ? '$' : ''}
                                </span>
                                <input
                                    type="number"
                                    placeholder={market === 'KR' ? '최대' : 'To'}
                                    value={stockFilter.priceTo || ''}
                                    onChange={(e) => setStockFilter({
                                        ...stockFilter,
                                        priceTo: e.target.value ? Number(e.target.value) : undefined,
                                        priceFilter: 'range'
                                    })}
                                    disabled={stockFilter.priceFilter !== 'range'}
                                    className={`w-28 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-sm focus:outline-none focus:border-primary ${
                                        stockFilter.priceFilter !== 'range' ? 'opacity-50 cursor-not-allowed' : ''
                                    }`}
                                />
                                <span className="text-slate-400 text-xs w-4 shrink-0">
                                    {market === 'KR' ? '원' : ''}
                                </span>
                            </div>

                            {/* Stock Name Search - 엔터 또는 조회 버튼 */}
                            <div className="flex items-center gap-1">
                                <input
                                    type="text"
                                    placeholder="종목명 검색..."
                                    value={stockNameInput}
                                    onChange={(e) => setStockNameInput(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleStockNameSearch()}
                                    className="w-40 px-3 py-1 bg-slate-800 border border-slate-700 rounded text-sm focus:outline-none focus:border-primary"
                                />
                                <button
                                    onClick={handleStockNameSearch}
                                    className="px-2 py-1 bg-primary hover:bg-primary/80 rounded text-sm transition-colors flex items-center gap-1"
                                >
                                    <Search size={14} />
                                    <span>조회</span>
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </header>

            {/* Main Content Area */}
            <main className="flex-1 overflow-hidden p-6">
                <div className={`h-full ${activeTab === 'stocks' ? '' : 'hidden'}`}>
                    <StocksDashboard market={market} filter={stockFilter} />
                </div>
                <div className={`h-full ${activeTab === 'signals' ? '' : 'hidden'}`}>
                    <SignalsDashboard
                        market={market}
                        focusCode={focusSignalCode}
                        onFocusDone={() => setFocusSignalCode(undefined)}
                    />
                </div>
                <div className={`h-full ${activeTab === 'backtest' ? '' : 'hidden'}`}>
                    <BacktestDashboard market={market} optimizedParams={optimizedParams} />
                </div>
                <div className={`h-full ${activeTab === 'optimize' ? '' : 'hidden'}`}>
                    <OptimizeDashboard market={market} onApplyParams={handleApplyOptimizedParams} />
                </div>
                <div className={`h-full ${activeTab === 'paper' ? '' : 'hidden'}`}>
                    <PaperTradingDashboard
                        onNavigateToStock={(name: string) => {
                            setActiveTab('stocks');
                            setStockNameInput(name);
                            setStockFilter(f => ({ ...f, stockName: name }));
                        }}
                    />
                </div>
                <div className={`h-full ${activeTab === 'journal' ? '' : 'hidden'}`}>
                    <InvestmentJournalDashboard />
                </div>
                <div className={`h-full ${activeTab === 'watchlist' ? '' : 'hidden'}`}>
                    <WatchlistDashboard market={market} />
                </div>
            </main>

            {/* Signal Alert Toasts — 최대 3개 표시, 초과분은 벨 패널로 안내 */}
            {alerts.length > 0 && (
                <div className="fixed top-20 right-4 z-50 flex flex-col gap-2 w-72">
                    {alerts.slice(0, 3).map(alert => (
                        <div
                            key={alert.id}
                            className="bg-slate-800 border border-green-500/70 rounded-xl p-4 shadow-2xl cursor-pointer hover:border-green-400 transition-all"
                            onClick={() => handleAlertClick(alert.code, alert.id)}
                        >
                            <div className="flex items-start justify-between gap-2">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-1.5 mb-1.5">
                                        <Bell size={13} className="text-green-400 shrink-0" />
                                        <span className="text-xs font-semibold text-green-400">매수 신호 발생</span>
                                    </div>
                                    <div className="font-bold text-sm truncate">
                                        {alert.name ? `${alert.name}(${alert.code})` : alert.code}
                                    </div>
                                    {alert.currentPrice && (
                                        <div className="text-sm text-slate-300 mt-0.5 font-mono">
                                            {alert.market === 'US' ? '$' : ''}
                                            {alert.currentPrice.toLocaleString()}
                                            {alert.market === 'KR' ? '원' : ''}
                                        </div>
                                    )}
                                    <div className="flex items-center gap-2 mt-1.5">
                                        <span className="text-xs text-slate-400">
                                            점수: <span className="text-white font-bold">{alert.score.toFixed(0)}</span>
                                        </span>
                                        <span className={`text-xs font-semibold ${
                                            alert.strength === 'high' ? 'text-green-400' :
                                            alert.strength === 'medium' ? 'text-yellow-400' : 'text-slate-400'
                                        }`}>
                                            {alert.strength.toUpperCase()}
                                        </span>
                                    </div>
                                    <div className="mt-2">
                                        <span className="inline-block text-xs font-semibold text-green-400 bg-green-400/10 border border-green-400/30 rounded px-2 py-0.5">
                                            신호 보기 →
                                        </span>
                                    </div>
                                </div>
                                <button
                                    onClick={(e) => { e.stopPropagation(); dismissAlert(alert.id); }}
                                    className="text-slate-600 hover:text-slate-300 shrink-0 mt-0.5"
                                >
                                    <X size={14} />
                                </button>
                            </div>
                        </div>
                    ))}
                    {alerts.length > 3 && (
                        <button
                            onClick={() => setShowAlertPanel(true)}
                            className="text-center text-xs font-semibold text-green-400 bg-slate-800 border border-green-500/50 rounded-xl py-2 hover:border-green-400 transition-all"
                        >
                            +{alerts.length - 3}개 더 보기 →
                        </button>
                    )}
                </div>
            )}

            {/* Footer */}
            <footer className="border-t border-slate-700 bg-surface px-6 py-3">
                <div className="flex items-center justify-between text-xs text-slate-500">
                    <p>&copy; 2026 Stock Analysis System. Not financial advice.</p>
                    <div className="flex items-center gap-4">
                        <span>API: http://localhost:8000</span>
                        <a
                            href="http://localhost:8000/docs"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline"
                        >
                            API 문서
                        </a>
                    </div>
                </div>
            </footer>
        </div>
    );
}

export default App;
