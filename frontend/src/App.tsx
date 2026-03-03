import { useState } from 'react';
import { TrendingUp, Activity, BarChart3, Settings } from 'lucide-react';
import type { Market } from './lib/api';

// Import page components
import StocksDashboard from './pages/StocksDashboard';
import SignalsDashboard from './pages/SignalsDashboard';
import BacktestDashboard from './pages/BacktestDashboard';
import OptimizeDashboard from './pages/OptimizeDashboard';

type Tab = 'stocks' | 'signals' | 'backtest' | 'optimize';

export type PriceFilter = 'all' | 'penny' | 'range';

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

                    {/* Market Selector */}
                    <div className="flex gap-2 bg-slate-800 rounded-lg p-1">
                        <button
                            onClick={() => setMarket('KR')}
                            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                                market === 'KR'
                                    ? 'bg-primary text-white'
                                    : 'text-slate-400 hover:text-slate-200'
                            }`}
                        >
                            🇰🇷 한국
                        </button>
                        <button
                            onClick={() => setMarket('US')}
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
                                    <span className="text-slate-300">$1 미만</span>
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

                            {/* Price Range Inputs - Always visible */}
                            <div className="flex items-center gap-2">
                                <input
                                    type="number"
                                    placeholder="From"
                                    value={stockFilter.priceFrom || ''}
                                    onChange={(e) => setStockFilter({
                                        ...stockFilter,
                                        priceFrom: e.target.value ? Number(e.target.value) : undefined,
                                        priceFilter: 'range'
                                    })}
                                    disabled={stockFilter.priceFilter !== 'range'}
                                    className={`w-24 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-sm focus:outline-none focus:border-primary ${
                                        stockFilter.priceFilter !== 'range' ? 'opacity-50 cursor-not-allowed' : ''
                                    }`}
                                />
                                <span className="text-slate-500">~</span>
                                <input
                                    type="number"
                                    placeholder="To"
                                    value={stockFilter.priceTo || ''}
                                    onChange={(e) => setStockFilter({
                                        ...stockFilter,
                                        priceTo: e.target.value ? Number(e.target.value) : undefined,
                                        priceFilter: 'range'
                                    })}
                                    disabled={stockFilter.priceFilter !== 'range'}
                                    className={`w-24 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-sm focus:outline-none focus:border-primary ${
                                        stockFilter.priceFilter !== 'range' ? 'opacity-50 cursor-not-allowed' : ''
                                    }`}
                                />
                            </div>

                            {/* Stock Name Search */}
                            <input
                                type="text"
                                placeholder="종목명 검색..."
                                value={stockFilter.stockName}
                                onChange={(e) => setStockFilter({ ...stockFilter, stockName: e.target.value })}
                                className="w-48 px-3 py-1 bg-slate-800 border border-slate-700 rounded text-sm focus:outline-none focus:border-primary"
                            />
                        </div>
                    )}
                </div>
            </header>

            {/* Main Content Area */}
            <main className="flex-1 overflow-hidden p-6">
                {activeTab === 'stocks' && <StocksDashboard market={market} filter={stockFilter} />}
                {activeTab === 'signals' && <SignalsDashboard market={market} />}
                {activeTab === 'backtest' && <BacktestDashboard market={market} />}
                {activeTab === 'optimize' && <OptimizeDashboard market={market} />}
            </main>

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
