import React from 'react';
import { TrendingUp, Shield, BarChart2, AlertCircle } from 'lucide-react';

interface ScoreCardProps {
    total: number;
    value: number;
    trend: number;
    stability: number;
    risk: number;
}

const ScoreCard: React.FC<ScoreCardProps> = ({ total, value, trend, stability, risk }) => {
    const getScoreColor = (s: number) => {
        if (s >= 80) return 'text-success';
        if (s >= 60) return 'text-warning';
        return 'text-danger';
    };

    return (
        <div className="bg-surface p-6 rounded-xl border border-slate-700 shadow-xl">
            <div className="flex justify-between items-center mb-6">
                <h3 className="text-xl font-bold text-slate-300">점수 요약</h3>
                <span className={`text-4xl font-extrabold ${getScoreColor(total)}`}>{total}점</span>
            </div>

            <div className="space-y-4">
                <ScoreItem icon={<BarChart2 size={20} />} label="가치" score={value} max={40} />
                <ScoreItem icon={<TrendingUp size={20} />} label="추세" score={trend} max={30} />
                <ScoreItem icon={<Shield size={20} />} label="안정성" score={stability} max={20} />
                <ScoreItem icon={<AlertCircle size={20} />} label="리스크" score={risk} max={10} isPenalty />
            </div>
        </div>
    );
};

const ScoreItem = ({ icon, label, score, max, isPenalty = false }: any) => (
    <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-slate-400">
            {icon}
            <span>{label}</span>
        </div>
        <div className="flex items-center gap-2">
            <span className={isPenalty ? 'text-danger' : 'text-slate-200'}>
                {isPenalty ? `-${score}` : score} / {max}
            </span>
            <div className="w-24 h-2 bg-slate-800 rounded-full overflow-hidden">
                <div
                    className={`h-full ${isPenalty ? 'bg-danger' : 'bg-primary'}`}
                    style={{ width: `${(score / max) * 100}%` }}
                />
            </div>
        </div>
    </div>
);

export default ScoreCard;
