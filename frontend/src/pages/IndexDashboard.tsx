import { useState, useEffect } from 'react';
import {
    Activity, TrendingUp, BarChart3, PlayCircle, BookOpen,
    Star, Flame, Sunrise, Sunset, FileText, RefreshCw,
    ArrowUpRight, ArrowDownRight, Minus, ChevronRight
} from 'lucide-react';

const BASE_URL: string = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');

type TabId = 'stocks' | 'signals' | 'backtest' | 'optimize' | 'paper' | 'journal' | 'watchlist' | 'live' | 'briefing' | 'closing';

interface Props {
    onNavigate: (tab: TabId) => void;
}

interface PaperStatus {
    is_running: boolean;
    roi: number;
    total_value: number;
    cash: number;
    open_count: number;
    closed_today: number;
    initial_capital: number;
}

interface BriefingRow {
    briefing_date: string;
    total_candidates?: number;
    ai_summary?: string;
    generated_at?: string;
}

interface ClosingRow {
    briefing_date: string;
    total_candidates?: number;
    ai_summary?: string;
    generated_at?: string;
}

interface DartItem {
    code: string;
    name: string;
    dart_type?: string;
}

interface SurgeStock {
    code: string;
    name: string;
    change_rate: number;
    price: number;
}

async function fetchJson<T>(path: string): Promise<T> {
    const res = await fetch(`${BASE_URL}${path}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

function RoiBadge({ roi }: { roi: number }) {
    const pct = (roi * 100).toFixed(2);
    if (roi > 0.001) return (
        <span className="flex items-center gap-0.5 text-green-400 font-bold">
            <ArrowUpRight size={14} />{pct}%
        </span>
    );
    if (roi < -0.001) return (
        <span className="flex items-center gap-0.5 text-red-400 font-bold">
            <ArrowDownRight size={14} />{pct}%
        </span>
    );
    return (
        <span className="flex items-center gap-0.5 text-slate-400 font-bold">
            <Minus size={14} />{pct}%
        </span>
    );
}

function StatCard({
    label, value, sub, accent, onClick
}: {
    label: string; value: string | React.ReactNode; sub?: string; accent?: string; onClick?: () => void
}) {
    return (
        <div
            onClick={onClick}
            className={`bg-surface border border-slate-700 rounded-xl p-4 flex flex-col gap-1 ${onClick ? 'cursor-pointer hover:border-slate-500 transition-colors' : ''}`}
        >
            <span className="text-xs text-slate-500">{label}</span>
            <div className={`text-lg font-bold ${accent ?? 'text-white'}`}>{value}</div>
            {sub && <span className="text-xs text-slate-500">{sub}</span>}
        </div>
    );
}

function SectionHeader({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick?: () => void }) {
    return (
        <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
                {icon}
                <span className="text-sm font-semibold text-slate-200">{label}</span>
            </div>
            {onClick && (
                <button onClick={onClick} className="flex items-center gap-1 text-xs text-primary hover:underline">
                    자세히 <ChevronRight size={12} />
                </button>
            )}
        </div>
    );
}

export default function IndexDashboard({ onNavigate }: Props) {
    const [paper, setPaper] = useState<PaperStatus | null>(null);
    const [briefing, setBriefing] = useState<BriefingRow | null>(null);
    const [closing, setClosing] = useState<ClosingRow | null>(null);
    const [dartItems, setDartItems] = useState<DartItem[]>([]);
    const [surgeStocks, setSurgeStocks] = useState<SurgeStock[]>([]);
    const [loading, setLoading] = useState(true);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

    const load = async () => {
        setLoading(true);
        await Promise.allSettled([
            fetchJson<PaperStatus>('/paper/status').then(setPaper).catch(() => {}),
            fetchJson<{ items: BriefingRow[] }>('/briefing/history').then(d => setBriefing(d.items?.[0] ?? null)).catch(() => {}),
            fetchJson<{ items: ClosingRow[] }>('/briefing/closing/history').then(d => setClosing(d.items?.[0] ?? null)).catch(() => {}),
            fetchJson<{ items: DartItem[] }>('/stocks/dart-disclosures').then(d => setDartItems(d.items ?? [])).catch(() => {}),
            fetchJson<{ stocks: SurgeStock[] }>('/stocks/surge?market=KR').then(d => setSurgeStocks((d.stocks ?? []).slice(0, 5))).catch(() => {}),
        ]);
        setLastUpdated(new Date());
        setLoading(false);
    };

    useEffect(() => { load(); }, []);

    const fmtKRW = (v: number) => v >= 1_000_000
        ? `${(v / 1_000_000).toFixed(2)}백만원`
        : `${v.toLocaleString()}원`;

    const fmtDate = (s?: string) => s ? s.slice(0, 10) : '-';

    const shortSummary = (txt?: string) => {
        if (!txt) return null;
        const lines = txt.split('\n').filter(l => l.trim());
        return lines.slice(0, 3).join(' / ');
    };

    return (
        <div className="h-full overflow-y-auto space-y-6 pr-1">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-bold text-white">대시보드</h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                        {lastUpdated ? `마지막 업데이트: ${lastUpdated.toLocaleTimeString('ko-KR')}` : '데이터 로딩 중...'}
                    </p>
                </div>
                <button
                    onClick={load}
                    disabled={loading}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded-lg text-xs text-slate-300 transition-colors"
                >
                    <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
                    새로고침
                </button>
            </div>

            {/* ── 모의투자 요약 ── */}
            <section>
                <SectionHeader
                    icon={<PlayCircle size={15} className="text-cyan-400" />}
                    label="모의투자 현황"
                    onClick={() => onNavigate('paper')}
                />
                {paper ? (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <StatCard
                            label="상태"
                            value={paper.is_running ? '실행 중' : '정지됨'}
                            accent={paper.is_running ? 'text-green-400' : 'text-slate-400'}
                        />
                        <StatCard
                            label="수익률"
                            value={<RoiBadge roi={paper.roi} />}
                            sub={`원금 ${fmtKRW(paper.initial_capital)}`}
                        />
                        <StatCard
                            label="평가금액"
                            value={fmtKRW(paper.total_value)}
                            sub={`현금 ${fmtKRW(paper.cash)}`}
                        />
                        <StatCard
                            label="포지션"
                            value={`${paper.open_count}개`}
                            sub={`오늘 청산 ${paper.closed_today}건`}
                        />
                    </div>
                ) : (
                    <div className="text-xs text-slate-500 bg-surface border border-slate-700 rounded-xl p-4">모의투자 데이터 없음</div>
                )}
            </section>

            {/* ── 오늘의 급등주 ── */}
            <section>
                <SectionHeader
                    icon={<TrendingUp size={15} className="text-green-400" />}
                    label="오늘 급등주 TOP5"
                    onClick={() => onNavigate('stocks')}
                />
                {surgeStocks.length > 0 ? (
                    <div className="bg-surface border border-slate-700 rounded-xl overflow-hidden">
                        {surgeStocks.map((s, i) => (
                            <div key={s.code} className={`flex items-center justify-between px-4 py-2.5 ${i < surgeStocks.length - 1 ? 'border-b border-slate-700/60' : ''}`}>
                                <div className="flex items-center gap-3">
                                    <span className="text-xs text-slate-600 w-4">{i + 1}</span>
                                    <div>
                                        <span className="text-sm font-medium text-white">{s.name}</span>
                                        <span className="text-xs text-slate-500 ml-1.5">{s.code}</span>
                                    </div>
                                </div>
                                <div className="flex items-center gap-4">
                                    <span className="text-sm font-mono text-slate-300">{s.price.toLocaleString()}원</span>
                                    <span className={`text-sm font-bold ${s.change_rate > 0 ? 'text-red-400' : s.change_rate < 0 ? 'text-blue-400' : 'text-slate-400'}`}>
                                        {s.change_rate > 0 ? '+' : ''}{s.change_rate.toFixed(2)}%
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-xs text-slate-500 bg-surface border border-slate-700 rounded-xl p-4">급등주 데이터 없음</div>
                )}
            </section>

            {/* ── 브리핑 요약 ── */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* 장전 브리핑 */}
                <section>
                    <SectionHeader
                        icon={<Sunrise size={15} className="text-amber-400" />}
                        label="장전 브리핑"
                        onClick={() => onNavigate('briefing')}
                    />
                    <div className="bg-surface border border-slate-700 rounded-xl p-4 min-h-[100px]">
                        {briefing ? (
                            <>
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs text-slate-500">{fmtDate(briefing.briefing_date)}</span>
                                    {briefing.total_candidates != null && (
                                        <span className="text-xs bg-amber-400/10 text-amber-400 border border-amber-400/20 px-2 py-0.5 rounded-full">
                                            후보 {briefing.total_candidates}종
                                        </span>
                                    )}
                                </div>
                                {briefing.ai_summary ? (
                                    <p className="text-xs text-slate-300 leading-relaxed line-clamp-3">
                                        {shortSummary(briefing.ai_summary)}
                                    </p>
                                ) : (
                                    <p className="text-xs text-slate-500">요약 없음</p>
                                )}
                            </>
                        ) : (
                            <p className="text-xs text-slate-500">오늘 브리핑 없음</p>
                        )}
                    </div>
                </section>

                {/* 장마감 브리핑 */}
                <section>
                    <SectionHeader
                        icon={<Sunset size={15} className="text-orange-400" />}
                        label="장마감 분석"
                        onClick={() => onNavigate('closing')}
                    />
                    <div className="bg-surface border border-slate-700 rounded-xl p-4 min-h-[100px]">
                        {closing ? (
                            <>
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs text-slate-500">{fmtDate(closing.briefing_date)}</span>
                                    {closing.total_candidates != null && (
                                        <span className="text-xs bg-orange-400/10 text-orange-400 border border-orange-400/20 px-2 py-0.5 rounded-full">
                                            내일 주목 {closing.total_candidates}종
                                        </span>
                                    )}
                                </div>
                                {closing.ai_summary ? (
                                    <p className="text-xs text-slate-300 leading-relaxed line-clamp-3">
                                        {shortSummary(closing.ai_summary)}
                                    </p>
                                ) : (
                                    <p className="text-xs text-slate-500">요약 없음</p>
                                )}
                            </>
                        ) : (
                            <p className="text-xs text-slate-500">오늘 장마감 분석 없음</p>
                        )}
                    </div>
                </section>
            </div>

            {/* ── DART 공시 ── */}
            <section>
                <SectionHeader
                    icon={<FileText size={15} className="text-violet-400" />}
                    label={`오늘 DART 공시 (${dartItems.length}건)`}
                    onClick={() => onNavigate('closing')}
                />
                {dartItems.length > 0 ? (
                    <div className="bg-surface border border-slate-700 rounded-xl overflow-hidden">
                        {dartItems.slice(0, 6).map((d, i) => (
                            <div key={`${d.code}-${i}`} className={`flex items-center justify-between px-4 py-2.5 ${i < Math.min(dartItems.length, 6) - 1 ? 'border-b border-slate-700/60' : ''}`}>
                                <div>
                                    <span className="text-sm font-medium text-white">{d.name}</span>
                                    <span className="text-xs text-slate-500 ml-1.5">{d.code}</span>
                                </div>
                                {d.dart_type && (
                                    <span className="text-xs bg-violet-400/10 text-violet-300 border border-violet-400/20 px-2 py-0.5 rounded-full shrink-0">
                                        {d.dart_type}
                                    </span>
                                )}
                            </div>
                        ))}
                        {dartItems.length > 6 && (
                            <div className="px-4 py-2 text-xs text-slate-500 text-center border-t border-slate-700/60">
                                +{dartItems.length - 6}건 더 있음
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-xs text-slate-500 bg-surface border border-slate-700 rounded-xl p-4">오늘 공시 없음 (장 마감 후 생성)</div>
                )}
            </section>

            {/* ── 빠른 이동 ── */}
            <section>
                <SectionHeader icon={<Activity size={15} className="text-blue-400" />} label="빠른 이동" />
                <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                    {([
                        { id: 'stocks', label: '주식 분석', icon: Activity, color: 'text-blue-400' },
                        { id: 'signals', label: '매매 신호', icon: TrendingUp, color: 'text-green-400' },
                        { id: 'paper', label: '모의투자', icon: PlayCircle, color: 'text-cyan-400' },
                        { id: 'journal', label: '투자일지', icon: BookOpen, color: 'text-amber-400' },
                        { id: 'watchlist', label: '관심종목', icon: Star, color: 'text-yellow-400' },
                        { id: 'live', label: '실전매매', icon: Flame, color: 'text-red-400' },
                        { id: 'briefing', label: '장전브리핑', icon: Sunrise, color: 'text-amber-400' },
                        { id: 'closing', label: '장마감분석', icon: Sunset, color: 'text-orange-400' },
                        { id: 'backtest', label: '백테스팅', icon: BarChart3, color: 'text-purple-400' },
                    ] as { id: TabId; label: string; icon: React.ElementType; color: string }[]).map(t => {
                        const Icon = t.icon;
                        return (
                            <button
                                key={t.id}
                                onClick={() => onNavigate(t.id)}
                                className="flex flex-col items-center gap-1.5 py-3 bg-surface border border-slate-700 hover:border-slate-500 rounded-xl text-xs text-slate-400 hover:text-white transition-all"
                            >
                                <Icon size={18} className={t.color} />
                                <span>{t.label}</span>
                            </button>
                        );
                    })}
                </div>
            </section>
        </div>
    );
}
