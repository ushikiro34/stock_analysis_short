import React from 'react';
import { AlertTriangle } from 'lucide-react';

interface RiskCardProps {
    warnings: string[];
}

const RiskCard: React.FC<RiskCardProps> = ({ warnings }) => {
    return (
        <div className="bg-surface p-6 rounded-xl border border-slate-700 shadow-xl">
            <h3 className="text-xl font-bold text-slate-300 mb-4 flex items-center gap-2">
                <AlertTriangle className="text-warning" />
                리스크 경고
            </h3>

            {warnings.length > 0 ? (
                <ul className="space-y-3">
                    {warnings.map((w, i) => (
                        <li key={i} className="flex items-start gap-2 text-slate-400 bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                            <span className="text-warning font-bold">•</span>
                            {w}
                        </li>
                    ))}
                </ul>
            ) : (
                <div className="text-success text-center py-4 bg-success/10 rounded-lg border border-success/20">
                    탐지된 주요 리스크가 없습니다.
                </div>
            )}
        </div>
    );
};

export default RiskCard;
