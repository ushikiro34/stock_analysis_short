import { useState } from 'react';
import { TrendingUp, Loader2, Search } from 'lucide-react';
import type { SurgeStock, Market } from '../lib/api';

interface SurgeListProps {
    stocks: SurgeStock[];
    selectedCode: string | null;
    onSelect: (code: string) => void;
    onManualSelect: (code: string) => void;
    loading: boolean;
    market: Market;
}

export default function SurgeList({ stocks, selectedCode, onSelect, onManualSelect, loading, market }: SurgeListProps) {
    const [manualCode, setManualCode] = useState('');

    const formatVolume = (v: number) => {
        if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
        if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
        return String(v);
    };

    const handleManualSearch = (e: React.FormEvent) => {
        e.preventDefault();
        if (manualCode.trim()) {
            onManualSelect(manualCode.trim().toUpperCase());
            setManualCode('');
        }
    };

    return (
        <div className="h-full flex flex-col">
            <div className="flex items-center gap-2 mb-4 px-1">
                <TrendingUp className="text-danger" size={20} />
                <h2 className="text-lg font-bold text-slate-200">
                    {market === 'US' ? 'Top Gainers' : '급등주'}
                </h2>
                <span className="text-xs text-slate-500 ml-auto">
                    {market === 'US' ? 'US Stocks' : '2만원 미만'}
                </span>
            </div>

            {/* Manual Stock Code Input */}
            <form onSubmit={handleManualSearch} className="mb-3 px-1">
                <div className="relative">
                    <input
                        type="text"
                        value={manualCode}
                        onChange={(e) => setManualCode(e.target.value)}
                        placeholder={market === 'US' ? 'Enter code (e.g. TPET)' : '종목코드 입력'}
                        className="w-full px-3 py-2 pl-9 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:border-primary text-slate-200 placeholder-slate-500"
                    />
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={14} />
                </div>
            </form>

            {loading && stocks.length === 0 ? (
                <div className="flex items-center justify-center py-12">
                    <Loader2 className="animate-spin text-slate-500" size={24} />
                </div>
            ) : stocks.length === 0 ? (
                <div className="text-center py-12 text-slate-500 text-sm">
                    {market === 'US' ? 'No data available.' : '급등주 데이터가 없습니다.'}
                    <br />
                    <span className="text-xs">
                        {market === 'US' ? 'Check market hours (EST).' : '장 운영시간을 확인하세요.'}
                    </span>
                </div>
            ) : (
                <div className="space-y-1">
                    {stocks.map((stock, idx) => (
                        <button
                            key={stock.code}
                            onClick={() => onSelect(stock.code)}
                            className={`w-full text-left px-3 py-2.5 rounded-lg transition-all ${
                                selectedCode === stock.code
                                    ? 'bg-primary/20 border border-primary/40'
                                    : 'hover:bg-slate-800/60 border border-transparent'
                            }`}
                        >
                            <div className="flex items-center justify-between">
                                <div className="min-w-0">
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs text-slate-500 w-5">{idx + 1}</span>
                                        <span className="font-medium text-slate-200 truncate text-sm">{stock.name}</span>
                                    </div>
                                    <div className="flex items-center gap-2 mt-0.5 ml-7">
                                        <span className="text-xs text-slate-500">{stock.code}</span>
                                        <span className="text-xs text-slate-600">vol {formatVolume(stock.volume)}</span>
                                    </div>
                                </div>
                                <div className="text-right shrink-0 ml-2">
                                    <div className="text-sm font-mono text-slate-200">
                                        {market === 'US' ? '$' : ''}{stock.price.toLocaleString()}{market === 'KR' ? '원' : ''}
                                    </div>
                                    <div className={`text-xs font-mono ${stock.change_rate > 0 ? 'text-danger' : 'text-blue-400'}`}>
                                        {stock.change_rate > 0 ? '+' : ''}{stock.change_rate.toFixed(2)}%
                                    </div>
                                </div>
                            </div>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
