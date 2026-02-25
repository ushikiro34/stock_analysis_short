import React from 'react';
import { TrendingUp, Loader2 } from 'lucide-react';
import type { SurgeStock, Market } from '../lib/api';

interface SurgeListProps {
    stocks: SurgeStock[];
    selectedCode: string | null;
    onSelect: (code: string) => void;
    loading: boolean;
    market: Market;
}

const SurgeList: React.FC<SurgeListProps> = ({ stocks, selectedCode, onSelect, loading, market }) => {
    const formatVolume = (v: number) => {
        if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
        if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
        return String(v);
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
};

export default SurgeList;
