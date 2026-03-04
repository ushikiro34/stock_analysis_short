import { useState, useEffect, useRef } from 'react';
import { TrendingUp, Activity, BarChart3, Settings, Search, Bell, X } from 'lucide-react';
import type { Market } from './lib/api';
import { scanSignals } from './lib/api';

// Import page components
import StocksDashboard from './pages/StocksDashboard';
import SignalsDashboard from './pages/SignalsDashboard';
import BacktestDashboard from './pages/BacktestDashboard';
import OptimizeDashboard from './pages/OptimizeDashboard';

type Tab = 'stocks' | 'signals' | 'backtest' | 'optimize';

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

function App() {
    const [activeTab, setActiveTab] = useState<Tab>('stocks');
    const [market, setMarket] = useState<Market>('KR');

    // Stock filter state
    const [stockFilter, setStockFilter] = useState<StockFilter>({
        priceFilter: 'all',
        priceFrom: undefined,
        priceTo: undefined,
        stockName: ''
    });

    const handleMarketChange = (m: Market) => {
        setMarket(m);
        // 시장 변경 시 가격 필터 초기화 (원/달러 혼용 방지)
        setStockFilter(f => ({ ...f, priceFilter: 'all', priceFrom: undefined, priceTo: undefined }));
    };

    // ── Signal Alert System ────────────────────────────────────
    const [alerts, setAlerts] = useState<SignalAlert[]>([]);
    const [focusSignalCode, setFocusSignalCode] = useState<string | undefined>();
    const seenKeysRef = useRef(new Set<string>());
    const isFirstPollRef = useRef(true);

    const dismissAlert = (id: string) => setAlerts(prev => prev.filter(a => a.id !== id));

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
                        setAlerts(prev => [...newAlerts, ...prev].slice(0, 5));
                        newAlerts.forEach(alert => {
                            setTimeout(() => setAlerts(prev => prev.filter(a => a.id !== alert.id)), 8000);
                        });
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
            } catch { /* 폴링 오류 무시 */ }
        };

        poll();
        const interval = setInterval(poll, 120000);
        return () => clearInterval(interval);
    }, [market]);

    // 종목명 검색 - 엔터 또는 조회 버튼으로만 실행
    const [stockNameInput, setStockNameInput] = useState('');
    const handleStockNameSearch = () => {
        setStockFilter(f => ({ ...f, stockName: stockNameInput }));
    };

    const tabs = [
        { id: 'stocks' as Tab, label: '주식 분석', icon: Activity, color: 'text-blue-400' },
        { id: 'signals' as Tab, label: '매매 신호', icon: TrendingUp, color: 'text-green-400' },
        { id: 'backtest' as Tab, label: '백테스팅', icon: BarChart3, color: 'text-purple-400' },
        { id: 'optimize' as Tab, label: '최적화', icon: Settings, color: 'text-orange-400' }
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

                    {/* Notification Bell + Market Selector */}
                    <div className="flex items-center gap-3">
                        <div className="relative">
                            <Bell size={20} className={alerts.length > 0 ? 'text-green-400' : 'text-slate-500'} />
                            {alerts.length > 0 && (
                                <span className="absolute -top-1.5 -right-1.5 bg-red-500 text-white text-xs font-bold rounded-full w-4 h-4 flex items-center justify-center leading-none">
                                    {alerts.length}
                                </span>
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
                {activeTab === 'stocks' && <StocksDashboard market={market} filter={stockFilter} />}
                {activeTab === 'signals' && (
                    <SignalsDashboard
                        market={market}
                        focusCode={focusSignalCode}
                        onFocusDone={() => setFocusSignalCode(undefined)}
                    />
                )}
                {activeTab === 'backtest' && <BacktestDashboard market={market} />}
                {activeTab === 'optimize' && <OptimizeDashboard market={market} />}
            </main>

            {/* Signal Alert Toasts */}
            {alerts.length > 0 && (
                <div className="fixed top-20 right-4 z-50 flex flex-col gap-2 w-72">
                    {alerts.map(alert => (
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
                                    <div className="text-xs text-slate-500 mt-1">탭하여 신호 확인 →</div>
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
