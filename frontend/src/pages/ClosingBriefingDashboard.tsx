import { useState, useEffect, useCallback } from 'react';
import {
    RefreshCw, ExternalLink, Sparkles, AlertCircle,
    TrendingUp, TrendingDown, BarChart2, FileText,
    ArrowRight, Star, Check, X,
} from 'lucide-react';
import { fetchStockAnalyze } from '../lib/api';
import type { StockAnalysis, Market } from '../lib/api';

const BASE_URL: string = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');

interface Props {
    isVisible: boolean;
    onNavigateToStock?: (code: string) => void;
}

// ── Types ────────────────────────────────────────────────────
interface MoverStock {
    code: string; name: string; price: number;
    change_rate: number; volume: number;
}
interface DartItem {
    corp_name: string; stock_code: string; report_nm: string;
    dart_type: string; rcept_dt: string; dart_url: string;
}
interface WatchCandidate {
    code: string; name: string; reason: string;
    type: string; source: string;
}
interface ClosingBriefing {
    briefing_date: string;
    surge_stocks: MoverStock[];
    fall_stocks: MoverStock[];
    upper_limit: MoverStock[];
    volume_top: MoverStock[];
    dart_items: DartItem[];
    watch_candidates: WatchCandidate[];
    total_candidates: number;
    ai_summary: string;
    generated_at: string | null;
}
interface HistoryItem {
    briefing_date: string; total_candidates: number;
    ai_summary: string; generated_at: string | null;
}

// ── Helpers ──────────────────────────────────────────────────
const dartTypeColor: Record<string, string> = {
    'CB발행':    'bg-yellow-900/50 text-yellow-300 border-yellow-700/50',
    'BW발행':    'bg-orange-900/50 text-orange-300 border-orange-700/50',
    '자사주취득': 'bg-green-900/50 text-green-300 border-green-700/50',
    '유상증자':   'bg-red-900/50 text-red-300 border-red-700/50',
    '대규모계약': 'bg-blue-900/50 text-blue-300 border-blue-700/50',
    '합병·인수':  'bg-purple-900/50 text-purple-300 border-purple-700/50',
    '실적발표':   'bg-cyan-900/50 text-cyan-300 border-cyan-700/50',
    '투자결정':   'bg-teal-900/50 text-teal-300 border-teal-700/50',
};
const candidateTypeColor: Record<string, string> = {
    '모멘텀': 'bg-red-900/40 text-red-300',
    '공시':   'bg-yellow-900/40 text-yellow-300',
    '테마':   'bg-purple-900/40 text-purple-300',
    '눌림목': 'bg-blue-900/40 text-blue-300',
    '기타':   'bg-slate-700 text-slate-300',
};

function fmtPrice(n: number) { return `${n.toLocaleString()}원`; }
function fmtPct(n: number) { return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`; }
function fmtTime(iso: string | null) {
    if (!iso) return '';
    return new Date(iso).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
}

// ── Watchlist helpers ────────────────────────────────────────
const WL_KEY = 'watchlist_v1';
function isInWL(code: string) {
    try { return JSON.parse(localStorage.getItem(WL_KEY) || '[]').some((i: { code: string }) => i.code === code); }
    catch { return false; }
}
function addToWL(code: string, name: string) {
    try {
        const items = JSON.parse(localStorage.getItem(WL_KEY) || '[]');
        if (items.some((i: { code: string }) => i.code === code)) return false;
        items.push({ code, market: 'KR', addedAt: new Date().toISOString(), name });
        localStorage.setItem(WL_KEY, JSON.stringify(items));
        return true;
    } catch { return false; }
}

// ── Stock Detail Modal ────────────────────────────────────────
function StockModal({ code, name, onClose, onNavigate }: {
    code: string; name: string;
    onClose: () => void; onNavigate?: (code: string) => void;
}) {
    const [data, setData] = useState<StockAnalysis | null>(null);
    const [loading, setLoading] = useState(true);
    const [err, setErr] = useState('');
    const [wlAdded, setWlAdded] = useState(() => isInWL(code));

    useEffect(() => {
        let cancelled = false;
        fetchStockAnalyze(code, 'KR')
            .then(d => { if (!cancelled) { setData(d); setLoading(false); } })
            .catch(e => { if (!cancelled) { setErr(String(e)); setLoading(false); } });
        return () => { cancelled = true; };
    }, [code]);

    const isUp = (data?.change_pct ?? 0) >= 0;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={e => e.target === e.currentTarget && onClose()}>
            <div className="bg-slate-900 border border-slate-600 rounded-2xl w-[480px] max-w-[95vw] shadow-2xl overflow-hidden">
                <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700">
                    <span className="font-bold text-white text-lg">{data?.name || name}
                        <span className="ml-2 text-sm text-slate-400 font-mono font-normal">{code}</span>
                    </span>
                    <button onClick={onClose} className="text-slate-500 hover:text-white p-1"><X size={18} /></button>
                </div>
                <div className="p-5">
                    {loading && <div className="flex justify-center py-12 text-slate-400"><RefreshCw size={20} className="animate-spin mr-2" />조회 중...</div>}
                    {err && <div className="text-red-400 text-sm py-6 text-center">{err}</div>}
                    {data && !loading && (
                        <>
                            <div className="flex items-end gap-3 mb-5">
                                <span className="text-3xl font-bold">{fmtPrice(data.current_price)}</span>
                                <span className={`flex items-center gap-1 text-lg font-semibold pb-0.5 ${isUp ? 'text-red-400' : 'text-blue-400'}`}>
                                    {isUp ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                                    {fmtPct(data.change_pct)}
                                </span>
                            </div>
                            <div className="grid grid-cols-2 gap-3 mb-4">
                                {[
                                    { label: '시가', value: fmtPrice(data.open) },
                                    { label: '고가', value: fmtPrice(data.high), cls: 'text-red-400' },
                                    { label: '저가', value: fmtPrice(data.low), cls: 'text-blue-400' },
                                    { label: '거래량', value: data.volume.toLocaleString() },
                                    { label: '거래량 비율', value: `${data.vol_ratio.toFixed(1)}x` },
                                    { label: '52주 고가', value: fmtPrice(data.high52w) },
                                ].map(({ label, value, cls }) => (
                                    <div key={label} className="bg-slate-800/60 rounded-lg px-3 py-2">
                                        <p className="text-xs text-slate-500 mb-0.5">{label}</p>
                                        <p className={`text-sm font-semibold ${cls ?? 'text-white'}`}>{value}</p>
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </div>
                <div className="flex gap-2 px-5 pb-5">
                    <button onClick={() => { addToWL(code, data?.name || name); setWlAdded(true); }} disabled={wlAdded}
                        className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${wlAdded ? 'bg-slate-700 text-green-400 cursor-default' : 'bg-slate-700 hover:bg-slate-600 text-slate-200'}`}>
                        {wlAdded ? <Check size={14} /> : <Star size={14} />}
                        {wlAdded ? '추가됨' : '관심종목'}
                    </button>
                    <button onClick={() => { onNavigate?.(code); onClose(); }}
                        className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 bg-primary hover:bg-primary/80 text-white text-sm font-medium rounded-lg transition-colors">
                        <ArrowRight size={14} /> 주식 분석 바로가기
                    </button>
                </div>
            </div>
        </div>
    );
}

// ── Mover Table ───────────────────────────────────────────────
function MoverTable({ stocks, onSelect, emptyMsg }: {
    stocks: MoverStock[]; onSelect: (s: MoverStock) => void; emptyMsg: string;
}) {
    if (stocks.length === 0)
        return <p className="text-slate-500 text-sm text-center py-6">{emptyMsg}</p>;
    return (
        <div className="space-y-1.5">
            {stocks.map((s, i) => {
                const up = s.change_rate >= 0;
                return (
                    <button key={i} onClick={() => onSelect(s)}
                        className="w-full flex items-center gap-3 px-3 py-2 bg-slate-800/60 hover:bg-slate-800 rounded-lg transition-colors text-left">
                        <span className="text-xs text-slate-500 w-4 shrink-0">{i + 1}</span>
                        <div className="flex-1 min-w-0">
                            <span className="text-sm font-medium text-white truncate block">{s.name}</span>
                            <span className="text-xs text-slate-500 font-mono">{s.code}</span>
                        </div>
                        <div className="text-right shrink-0">
                            <div className={`text-sm font-bold ${up ? 'text-red-400' : 'text-blue-400'}`}>
                                {fmtPct(s.change_rate)}
                            </div>
                            <div className="text-xs text-slate-500">{fmtPrice(s.price)}</div>
                        </div>
                    </button>
                );
            })}
        </div>
    );
}

// ── API calls ─────────────────────────────────────────────────
async function fetchClosingToday(): Promise<ClosingBriefing> {
    const res = await fetch(`${BASE_URL}/briefing/closing/today`);
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json();
}
async function fetchClosingByDate(date: string): Promise<ClosingBriefing> {
    const res = await fetch(`${BASE_URL}/briefing/closing/${date}`);
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json();
}
async function fetchClosingHistory(): Promise<HistoryItem[]> {
    const res = await fetch(`${BASE_URL}/briefing/closing/history`);
    if (!res.ok) return [];
    return res.json();
}
async function generateClosing(date: string, force: boolean): Promise<ClosingBriefing> {
    const res = await fetch(`${BASE_URL}/briefing/closing/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date, force }),
    });
    if (!res.ok) throw new Error(`생성 실패 (${res.status})`);
    return res.json();
}

// ── Main ──────────────────────────────────────────────────────
export default function ClosingBriefingDashboard({ isVisible, onNavigateToStock }: Props) {
    const [briefing, setBriefing] = useState<ClosingBriefing | null>(null);
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [error, setError] = useState('');
    const [selectedDate, setSelectedDate] = useState('');
    const [modal, setModal] = useState<{ code: string; name: string } | null>(null);
    const [moverTab, setMoverTab] = useState<'surge' | 'fall' | 'upper' | 'volume'>('surge');

    const load = useCallback(async (date?: string) => {
        setLoading(true); setError('');
        try {
            const data = date ? await fetchClosingByDate(date) : await fetchClosingToday();
            setBriefing(data);
        } catch {
            setBriefing(null);
            setError(date ? `${date} 장마감 브리핑 없음` : '오늘 브리핑 미생성 (15:40 이후 자동 생성)');
        }
        setLoading(false);
    }, []);

    useEffect(() => {
        if (!isVisible) return;
        load();
        fetchClosingHistory().then(setHistory).catch(() => {});
    }, [isVisible, load]);

    const handleGenerate = async (force = false) => {
        setGenerating(true); setError('');
        try {
            const data = await generateClosing(selectedDate, force);
            setBriefing(data);
            fetchClosingHistory().then(setHistory).catch(() => {});
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : '생성 실패');
        }
        setGenerating(false);
    };

    const currentMovers = briefing
        ? moverTab === 'surge' ? briefing.surge_stocks
          : moverTab === 'fall' ? briefing.fall_stocks
          : moverTab === 'upper' ? briefing.upper_limit
          : briefing.volume_top
        : [];

    const moverTabs = briefing ? [
        { key: 'surge' as const, label: `급등 ${briefing.surge_stocks.length}` },
        { key: 'fall' as const,  label: `급락 ${briefing.fall_stocks.length}` },
        { key: 'upper' as const, label: `상한가 ${briefing.upper_limit.length}` },
        { key: 'volume' as const, label: `거래량 ${briefing.volume_top.length}` },
    ] : [];

    return (
        <div className="h-full flex flex-col overflow-hidden">
            {modal && (
                <StockModal code={modal.code} name={modal.name}
                    onClose={() => setModal(null)}
                    onNavigate={onNavigateToStock} />
            )}

            {/* 헤더 */}
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3 shrink-0">
                <div className="flex flex-col gap-0.5 md:flex-row md:items-center md:gap-3">
                    <h2 className="text-base font-bold text-white">장마감 분석</h2>
                    {briefing && (
                        <span className="text-xs text-slate-400">
                            {briefing.briefing_date}
                            {briefing.generated_at && (
                                <span className="ml-1 text-green-400">생성완료 {fmtTime(briefing.generated_at)}</span>
                            )}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                    {history.length > 0 && (
                        <select value={selectedDate} onChange={e => { setSelectedDate(e.target.value); load(e.target.value || undefined); }}
                            className="px-2 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-primary max-w-[120px]">
                            <option value="">오늘</option>
                            {history.map(h => (
                                <option key={h.briefing_date} value={h.briefing_date}>
                                    {h.briefing_date} ({h.total_candidates}개)
                                </option>
                            ))}
                        </select>
                    )}
                    <button onClick={() => load(selectedDate || undefined)} disabled={loading}
                        className="p-1.5 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-white transition-colors">
                        <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                    </button>
                    <button onClick={() => handleGenerate(!!briefing)} disabled={generating}
                        className="flex items-center gap-1 px-2.5 py-1.5 bg-orange-600 hover:bg-orange-500 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50">
                        <Sparkles size={12} className={generating ? 'animate-pulse' : ''} />
                        {generating ? '생성 중...' : briefing ? '재생성' : '분석 생성'}
                    </button>
                </div>
            </div>

            {error && (
                <div className="flex items-center gap-2 mb-4 px-4 py-3 bg-slate-800/60 border border-slate-700 rounded-lg text-sm text-slate-400 shrink-0">
                    <AlertCircle size={15} className="text-orange-400 shrink-0" /> {error}
                </div>
            )}

            {!briefing && !loading && !error && (
                <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
                    브리핑 없음 — "분석 생성" 버튼으로 수동 생성하거나 15:40 이후 자동 생성됩니다.
                </div>
            )}

            {briefing && (
                <>
                    {/* AI 요약 */}
                    {briefing.ai_summary && (
                        <div className="mb-3 p-4 bg-orange-950/30 border border-orange-800/40 rounded-xl shrink-0">
                            <div className="flex items-center gap-2 mb-2">
                                <Sparkles size={14} className="text-orange-400" />
                                <span className="text-xs font-semibold text-orange-400">AI 내일 전망</span>
                            </div>
                            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{briefing.ai_summary}</p>
                        </div>
                    )}

                    {/* 3분할 */}
                    <div className="flex-1 overflow-hidden grid grid-cols-1 gap-3 md:grid-cols-3 md:gap-4 min-h-0">

                        {/* 오늘 주목 종목 */}
                        <div className="bg-slate-900/60 border border-slate-700/60 rounded-xl flex flex-col overflow-hidden">
                            <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-700/60 shrink-0">
                                <BarChart2 size={15} className="text-red-400" />
                                <span className="text-sm font-semibold text-white">오늘 주목 종목</span>
                            </div>
                            <div className="flex gap-1 px-3 pt-2 shrink-0">
                                {moverTabs.map(t => (
                                    <button key={t.key} onClick={() => setMoverTab(t.key)}
                                        className={`px-2 py-0.5 text-xs rounded transition-colors ${moverTab === t.key ? 'bg-slate-600 text-white' : 'text-slate-500 hover:text-slate-300'}`}>
                                        {t.label}
                                    </button>
                                ))}
                            </div>
                            <div className="flex-1 overflow-y-auto p-3">
                                <MoverTable stocks={currentMovers}
                                    onSelect={s => setModal({ code: s.code, name: s.name })}
                                    emptyMsg="해당 종목 없음" />
                            </div>
                        </div>

                        {/* 내일 주목 종목 */}
                        <div className="bg-slate-900/60 border border-slate-700/60 rounded-xl flex flex-col overflow-hidden">
                            <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-700/60 shrink-0">
                                <TrendingUp size={15} className="text-green-400" />
                                <span className="text-sm font-semibold text-white">내일 주목 종목</span>
                                <span className="ml-auto text-xs bg-green-900/50 text-green-300 px-2 py-0.5 rounded-full">
                                    {briefing.total_candidates}개
                                </span>
                            </div>
                            <div className="flex-1 overflow-y-auto p-3">
                                {briefing.watch_candidates.length === 0 ? (
                                    <p className="text-slate-500 text-sm text-center py-6">AI 추천 종목 없음</p>
                                ) : (
                                    <div className="space-y-2">
                                        {briefing.watch_candidates.map((c, i) => {
                                            const hasCode = c.code?.length === 6;
                                            const typeCls = candidateTypeColor[c.type] ?? candidateTypeColor['기타'];
                                            return (
                                                <div key={i} className="p-3 bg-slate-800/60 rounded-lg hover:bg-slate-800 transition-colors">
                                                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                                                        {hasCode ? (
                                                            <button onClick={() => setModal({ code: c.code, name: c.name })}
                                                                className="font-mono text-xs text-blue-400 bg-slate-700 hover:bg-blue-900/40 px-1.5 py-0.5 rounded border border-slate-600 hover:border-blue-700 transition-colors">
                                                                {c.code}
                                                            </button>
                                                        ) : (
                                                            <span className="font-mono text-xs text-slate-500 bg-slate-700/50 px-1.5 py-0.5 rounded">{c.code || '미상'}</span>
                                                        )}
                                                        <span className="font-semibold text-sm text-white">{c.name}</span>
                                                        <span className={`text-xs px-1.5 py-0.5 rounded ${typeCls}`}>{c.type}</span>
                                                    </div>
                                                    <p className="text-xs text-slate-400 leading-relaxed">{c.reason}</p>
                                                    {hasCode && (
                                                        <button onClick={() => { onNavigateToStock?.(c.code); }}
                                                            className="mt-1.5 flex items-center gap-1 text-xs text-slate-500 hover:text-white transition-colors">
                                                            <ArrowRight size={11} /> 주식 분석 이동
                                                        </button>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* DART 공시 */}
                        <div className="bg-slate-900/60 border border-slate-700/60 rounded-xl flex flex-col overflow-hidden">
                            <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-700/60 shrink-0">
                                <FileText size={15} className="text-yellow-400" />
                                <span className="text-sm font-semibold text-white">오늘 공시</span>
                                <span className="ml-auto text-xs bg-yellow-900/50 text-yellow-300 px-2 py-0.5 rounded-full">
                                    {briefing.dart_items.length}건
                                </span>
                            </div>
                            <div className="flex-1 overflow-y-auto p-3">
                                {briefing.dart_items.length === 0 ? (
                                    <p className="text-slate-500 text-sm text-center py-6">공시 없음</p>
                                ) : (
                                    <div className="space-y-2">
                                        {briefing.dart_items.map((d, i) => (
                                            <div key={i} className="flex items-start gap-3 p-3 bg-slate-800/60 rounded-lg">
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                                                        <span className="font-semibold text-sm text-white">{d.corp_name}</span>
                                                        <span className="font-mono text-xs text-slate-400">{d.stock_code}</span>
                                                        <span className={`text-xs px-1.5 py-0.5 rounded border ${dartTypeColor[d.dart_type] ?? 'bg-slate-700 text-slate-300 border-slate-600'}`}>
                                                            {d.dart_type}
                                                        </span>
                                                    </div>
                                                    <p className="text-xs text-slate-400 truncate">{d.report_nm}</p>
                                                    <p className="text-xs text-slate-600 mt-0.5">{d.rcept_dt}</p>
                                                </div>
                                                {d.dart_url && (
                                                    <a href={d.dart_url} target="_blank" rel="noopener noreferrer"
                                                        className="shrink-0 text-slate-500 hover:text-blue-400 transition-colors mt-1">
                                                        <ExternalLink size={14} />
                                                    </a>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
