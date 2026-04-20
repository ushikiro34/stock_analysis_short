import { useState, useEffect, useCallback } from 'react';
import {
    RefreshCw, ExternalLink, ChevronDown, ChevronRight,
    Newspaper, FileText, Tag, Sparkles, AlertCircle,
    X, Star, TrendingUp, TrendingDown, ArrowRight, Check,
} from 'lucide-react';
import type { MorningBriefing, BriefingHistoryItem, BriefingCandidate, DartDisclosure, StockAnalysis, Market } from '../lib/api';
import { briefingApi, fetchStockAnalyze } from '../lib/api';

interface Props {
    isVisible: boolean;
    onNavigateToStock?: (name: string) => void;
}

// ── Watchlist localStorage ─────────────────────────────────────
const WATCHLIST_KEY = 'watchlist_v1';
interface WatchItem { code: string; market: Market; addedAt: string; name?: string; }

function loadWatchlist(): WatchItem[] {
    try { return JSON.parse(localStorage.getItem(WATCHLIST_KEY) || '[]'); }
    catch { return []; }
}
function addToWatchlist(code: string, name: string) {
    const items = loadWatchlist();
    if (items.some(i => i.code === code)) return false;
    items.push({ code, market: 'KR', addedAt: new Date().toISOString(), name });
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(items));
    return true;
}
function isInWatchlist(code: string) {
    return loadWatchlist().some(i => i.code === code);
}

// ── Helpers ───────────────────────────────────────────────────
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
const sourceLabel: Record<string, { label: string; cls: string }> = {
    dart:     { label: 'DART',   cls: 'bg-yellow-800/60 text-yellow-300' },
    theme:    { label: '테마',   cls: 'bg-purple-800/60 text-purple-300' },
    news_llm: { label: 'AI뉴스', cls: 'bg-blue-800/60 text-blue-300' },
};

function fmtPrice(n: number) { return `${n.toLocaleString()}원`; }
function fmtPct(n: number) { return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`; }

// ── Stock Info Modal ──────────────────────────────────────────
interface StockModalProps {
    code: string;
    name: string;
    onClose: () => void;
    onNavigateToStock?: (name: string) => void;
}

function StockInfoModal({ code, name, onClose, onNavigateToStock }: StockModalProps) {
    const [data, setData] = useState<StockAnalysis | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [watchAdded, setWatchAdded] = useState(() => isInWatchlist(code));

    useEffect(() => {
        let cancelled = false;
        (async () => {
            setLoading(true);
            try {
                const res = await fetchStockAnalyze(code, 'KR');
                if (!cancelled) setData(res);
            } catch (e: unknown) {
                if (!cancelled) setError(e instanceof Error ? e.message : '조회 실패');
            }
            if (!cancelled) setLoading(false);
        })();
        return () => { cancelled = true; };
    }, [code]);

    const handleAddWatchlist = () => {
        const stockName = data?.name || name;
        const added = addToWatchlist(code, stockName);
        if (added) setWatchAdded(true);
    };

    const handleGoToStock = () => {
        const stockName = data?.name || name;
        onNavigateToStock?.(stockName);
        onClose();
    };

    const isUp = (data?.change_pct ?? 0) >= 0;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={e => e.target === e.currentTarget && onClose()}>
            <div className="bg-slate-900 border border-slate-600 rounded-2xl w-[480px] max-w-[95vw] shadow-2xl overflow-hidden">
                {/* 헤더 */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700">
                    <div className="flex items-center gap-3">
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="font-bold text-white text-lg">
                                    {data?.name || name}
                                </span>
                                <span className="text-sm text-slate-400 font-mono">{code}</span>
                            </div>
                        </div>
                    </div>
                    <button onClick={onClose}
                        className="text-slate-500 hover:text-white transition-colors p-1">
                        <X size={18} />
                    </button>
                </div>

                {/* 본문 */}
                <div className="p-5">
                    {loading && (
                        <div className="flex items-center justify-center py-12 text-slate-400">
                            <RefreshCw size={20} className="animate-spin mr-2" /> 조회 중...
                        </div>
                    )}
                    {error && (
                        <div className="flex items-center gap-2 text-red-400 py-6 justify-center">
                            <AlertCircle size={16} /> {error}
                        </div>
                    )}
                    {data && !loading && (
                        <>
                            {/* 현재가 + 등락률 */}
                            <div className="flex items-end gap-3 mb-5">
                                <span className="text-3xl font-bold text-white">
                                    {fmtPrice(data.current_price)}
                                </span>
                                <span className={`flex items-center gap-1 text-lg font-semibold pb-0.5 ${isUp ? 'text-red-400' : 'text-blue-400'}`}>
                                    {isUp ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                                    {fmtPct(data.change_pct)}
                                </span>
                            </div>

                            {/* 시고저 + 거래량 */}
                            <div className="grid grid-cols-2 gap-3 mb-4">
                                {[
                                    { label: '시가',   value: fmtPrice(data.open) },
                                    { label: '고가',   value: fmtPrice(data.high),   cls: 'text-red-400' },
                                    { label: '저가',   value: fmtPrice(data.low),    cls: 'text-blue-400' },
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

                            {/* 이동평균 */}
                            <div className="grid grid-cols-4 gap-2 mb-4">
                                {[
                                    { label: 'MA5',   vs: data.vs_ma5_pct },
                                    { label: 'MA20',  vs: data.vs_ma20_pct },
                                    { label: 'MA60',  vs: data.vs_ma60_pct },
                                ].map(({ label, vs }) => (
                                    <div key={label} className="bg-slate-800/40 rounded-lg px-2.5 py-2 text-center col-span-1">
                                        <p className="text-xs text-slate-500">{label}</p>
                                        <p className={`text-xs font-semibold mt-0.5 ${vs >= 0 ? 'text-red-400' : 'text-blue-400'}`}>
                                            {fmtPct(vs)}
                                        </p>
                                    </div>
                                ))}
                                <div className="bg-slate-800/40 rounded-lg px-2.5 py-2 text-center col-span-1">
                                    <p className="text-xs text-slate-500">신호</p>
                                    <p className={`text-xs font-bold mt-0.5 ${
                                        data.signal === 'BUY' ? 'text-green-400' :
                                        data.signal === 'SELL' ? 'text-red-400' : 'text-slate-400'
                                    }`}>{data.signal}</p>
                                </div>
                            </div>

                            {/* 신호 이유 (최대 3개) */}
                            {data.signal_reasons.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 mb-1">
                                    {data.signal_reasons.slice(0, 4).map((r, i) => (
                                        <span key={i} className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full border border-slate-700">
                                            {r}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </>
                    )}
                </div>

                {/* 하단 버튼 */}
                <div className="flex gap-2 px-5 pb-5">
                    <button
                        onClick={handleAddWatchlist}
                        disabled={watchAdded}
                        className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                            watchAdded
                                ? 'bg-slate-700 text-green-400 cursor-default'
                                : 'bg-slate-700 hover:bg-slate-600 text-slate-200'
                        }`}
                    >
                        {watchAdded ? <Check size={14} /> : <Star size={14} />}
                        {watchAdded ? '관심종목 추가됨' : '관심종목 추가'}
                    </button>
                    <button
                        onClick={handleGoToStock}
                        className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 bg-primary hover:bg-primary/80 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                        <ArrowRight size={14} />
                        주식 분석 바로가기
                    </button>
                </div>
            </div>
        </div>
    );
}

// ── DART Card ────────────────────────────────────────────────
function DartCard({ items }: { items: DartDisclosure[] }) {
    if (items.length === 0)
        return <p className="text-slate-500 text-sm text-center py-8">당일 관련 공시 없음</p>;

    return (
        <div className="space-y-2">
            {items.map((item, i) => (
                <div key={i} className="flex items-start gap-3 p-3 bg-slate-800/60 rounded-lg">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className="font-semibold text-sm text-white">{item.corp_name}</span>
                            <span className="font-mono text-xs text-slate-400">{item.stock_code}</span>
                            <span className={`text-xs px-1.5 py-0.5 rounded border ${dartTypeColor[item.dart_type] ?? 'bg-slate-700 text-slate-300 border-slate-600'}`}>
                                {item.dart_type}
                            </span>
                        </div>
                        <p className="text-xs text-slate-400 truncate">{item.report_nm}</p>
                        <p className="text-xs text-slate-600 mt-0.5">{item.rcept_dt}</p>
                    </div>
                    {item.dart_url && (
                        <a href={item.dart_url} target="_blank" rel="noopener noreferrer"
                            className="shrink-0 text-slate-500 hover:text-blue-400 transition-colors mt-1">
                            <ExternalLink size={14} />
                        </a>
                    )}
                </div>
            ))}
        </div>
    );
}

// ── Candidate Card ────────────────────────────────────────────
interface CandidateCardProps {
    candidates: BriefingCandidate[];
    onSelectStock: (code: string, name: string) => void;
}

function CandidateCard({ candidates, onSelectStock }: CandidateCardProps) {
    const [filter, setFilter] = useState<'all' | 'dart' | 'theme' | 'news_llm'>('all');

    const filtered = filter === 'all' ? candidates : candidates.filter(c => c.source === filter);

    const tabs = [
        { key: 'all',      label: `전체 ${candidates.length}` },
        { key: 'dart',     label: `DART ${candidates.filter(c => c.source === 'dart').length}` },
        { key: 'theme',    label: `테마 ${candidates.filter(c => c.source === 'theme').length}` },
        { key: 'news_llm', label: `AI뉴스 ${candidates.filter(c => c.source === 'news_llm').length}` },
    ] as const;

    return (
        <div>
            <div className="flex gap-1 mb-3">
                {tabs.map(t => (
                    <button key={t.key}
                        onClick={() => setFilter(t.key)}
                        className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                            filter === t.key
                                ? 'bg-slate-600 text-white'
                                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                        }`}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            {filtered.length === 0 ? (
                <p className="text-slate-500 text-sm text-center py-6">후보 종목 없음</p>
            ) : (
                <div className="space-y-2">
                    {filtered.map((c, i) => {
                        const src = sourceLabel[c.source] ?? { label: c.source, cls: 'bg-slate-700 text-slate-300' };
                        const hasCode = c.code && c.code.length === 6;
                        return (
                            <div key={i} className="flex items-start gap-3 p-3 bg-slate-800/60 rounded-lg hover:bg-slate-800 transition-colors">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                                        {/* 클릭 가능한 종목코드 */}
                                        {hasCode ? (
                                            <button
                                                onClick={() => onSelectStock(c.code, c.name)}
                                                className="font-mono text-xs text-blue-400 bg-slate-700 hover:bg-blue-900/40 hover:text-blue-300 px-1.5 py-0.5 rounded border border-slate-600 hover:border-blue-700 transition-colors cursor-pointer"
                                                title="종목 정보 보기"
                                            >
                                                {c.code}
                                            </button>
                                        ) : (
                                            <span className="font-mono text-xs text-slate-500 bg-slate-700/50 px-1.5 py-0.5 rounded">
                                                {c.code || '코드미상'}
                                            </span>
                                        )}
                                        <span className="font-semibold text-sm text-white">{c.name}</span>
                                        <span className={`text-xs px-1.5 py-0.5 rounded ${src.cls}`}>
                                            {src.label}
                                        </span>
                                        {c.theme_name && (
                                            <span className="text-xs text-purple-400">{c.theme_name}</span>
                                        )}
                                        {c.dart_type && (
                                            <span className={`text-xs px-1.5 py-0.5 rounded border ${dartTypeColor[c.dart_type] ?? 'bg-slate-700 text-slate-300 border-slate-600'}`}>
                                                {c.dart_type}
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-xs text-slate-400 leading-relaxed">{c.reason}</p>
                                </div>
                                <div className="flex items-center gap-1.5 shrink-0">
                                    {c.dart_url && (
                                        <a href={c.dart_url} target="_blank" rel="noopener noreferrer"
                                            className="text-slate-500 hover:text-blue-400 transition-colors">
                                            <ExternalLink size={14} />
                                        </a>
                                    )}
                                    {hasCode && (
                                        <button
                                            onClick={() => onSelectStock(c.code, c.name)}
                                            className="text-slate-500 hover:text-white transition-colors"
                                            title="종목 상세"
                                        >
                                            <TrendingUp size={14} />
                                        </button>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

// ── Theme Card ────────────────────────────────────────────────
function ThemeCard({ themes }: { themes: Record<string, string[]> }) {
    const [expanded, setExpanded] = useState<Set<string>>(new Set());
    const themeEntries = Object.entries(themes);

    if (themeEntries.length === 0)
        return <p className="text-slate-500 text-sm text-center py-8">감지된 테마 없음</p>;

    const toggle = (name: string) =>
        setExpanded(prev => {
            const next = new Set(prev);
            next.has(name) ? next.delete(name) : next.add(name);
            return next;
        });

    return (
        <div className="space-y-2">
            {themeEntries.map(([theme, codes]) => (
                <div key={theme} className="bg-slate-800/60 rounded-lg overflow-hidden">
                    <button
                        onClick={() => toggle(theme)}
                        className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-slate-700/40 transition-colors"
                    >
                        <div className="flex items-center gap-2">
                            <Tag size={13} className="text-purple-400" />
                            <span className="text-sm font-medium text-white">{theme}</span>
                            <span className="text-xs text-slate-500">{codes.length}종목</span>
                        </div>
                        {expanded.has(theme)
                            ? <ChevronDown size={14} className="text-slate-400" />
                            : <ChevronRight size={14} className="text-slate-400" />
                        }
                    </button>
                    {expanded.has(theme) && (
                        <div className="px-3 pb-3 flex flex-wrap gap-1.5">
                            {codes.map(code => (
                                <span key={code}
                                    className="text-xs font-mono bg-slate-700 text-slate-300 px-2 py-0.5 rounded">
                                    {code}
                                </span>
                            ))}
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
}

// ── Main Component ────────────────────────────────────────────
export default function MorningBriefingDashboard({ isVisible, onNavigateToStock }: Props) {
    const [briefing, setBriefing] = useState<MorningBriefing | null>(null);
    const [history, setHistory] = useState<BriefingHistoryItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [error, setError] = useState('');
    const [selectedDate, setSelectedDate] = useState('');

    // 종목 상세 모달
    const [modalStock, setModalStock] = useState<{ code: string; name: string } | null>(null);

    const loadBriefing = useCallback(async (date?: string) => {
        setLoading(true);
        setError('');
        try {
            const data = date ? await briefingApi.getByDate(date) : await briefingApi.getToday();
            setBriefing(data);
        } catch {
            setBriefing(null);
            setError(date ? `${date} 브리핑 없음` : '오늘 브리핑 미생성 (08:20 이후 자동 생성)');
        }
        setLoading(false);
    }, []);

    const loadHistory = useCallback(async () => {
        try {
            const data = await briefingApi.getHistory(20);
            setHistory(data);
        } catch { /* silent */ }
    }, []);

    useEffect(() => {
        if (!isVisible) return;
        loadBriefing();
        loadHistory();
    }, [isVisible, loadBriefing, loadHistory]);

    // 08:00~09:30 사이 자동 폴링 (5분)
    useEffect(() => {
        if (!isVisible) return;
        const isPreOpen = () => {
            const now = new Date();
            const kstMin = (now.getUTCHours() * 60 + now.getUTCMinutes() + 9 * 60) % (24 * 60);
            return kstMin >= 8 * 60 && kstMin <= 9 * 60 + 30;
        };
        if (!isPreOpen()) return;
        const iv = setInterval(() => loadBriefing(selectedDate || undefined), 5 * 60 * 1000);
        return () => clearInterval(iv);
    }, [isVisible, selectedDate, loadBriefing]);

    const handleGenerate = async (force = false) => {
        setGenerating(true);
        setError('');
        try {
            const data = await briefingApi.generate(selectedDate, force);
            setBriefing(data);
            await loadHistory();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : '생성 실패');
        }
        setGenerating(false);
    };

    const handleDateSelect = (date: string) => {
        setSelectedDate(date);
        loadBriefing(date);
    };

    const fmtTime = (iso: string | null) => {
        if (!iso) return '';
        return new Date(iso).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
    };

    return (
        <div className="h-full flex flex-col overflow-hidden">
            {/* 모달 */}
            {modalStock && (
                <StockInfoModal
                    code={modalStock.code}
                    name={modalStock.name}
                    onClose={() => setModalStock(null)}
                    onNavigateToStock={onNavigateToStock}
                />
            )}

            {/* 헤더 */}
            <div className="flex items-center justify-between mb-4 shrink-0">
                <div className="flex items-center gap-3">
                    <h2 className="text-lg font-bold text-white">장전 브리핑</h2>
                    {briefing && (
                        <span className="text-sm text-slate-400">
                            {briefing.briefing_date}
                            {briefing.generated_at && (
                                <span className="ml-1.5 text-xs text-green-400">
                                    생성완료 {fmtTime(briefing.generated_at)}
                                </span>
                            )}
                        </span>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    {history.length > 0 && (
                        <select
                            value={selectedDate}
                            onChange={e => handleDateSelect(e.target.value)}
                            className="px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-primary"
                        >
                            <option value="">오늘</option>
                            {history.map(h => (
                                <option key={h.briefing_date} value={h.briefing_date}>
                                    {h.briefing_date} ({h.total_candidates}개)
                                </option>
                            ))}
                        </select>
                    )}
                    <button onClick={() => loadBriefing(selectedDate || undefined)} disabled={loading}
                        className="p-1.5 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                        title="새로고침">
                        <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
                    </button>
                    <button onClick={() => handleGenerate(!!briefing)} disabled={generating}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50">
                        <Sparkles size={13} className={generating ? 'animate-pulse' : ''} />
                        {generating ? '생성 중...' : briefing ? '재생성' : '브리핑 생성'}
                    </button>
                </div>
            </div>

            {/* 에러/안내 */}
            {error && (
                <div className="flex items-center gap-2 mb-4 px-4 py-3 bg-slate-800/60 border border-slate-700 rounded-lg text-sm text-slate-400 shrink-0">
                    <AlertCircle size={15} className="text-amber-400 shrink-0" />
                    {error}
                </div>
            )}

            {!briefing && !loading && !error && (
                <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
                    브리핑 데이터 없음 — "브리핑 생성" 버튼으로 수동 생성하거나 08:20 이후 자동 생성됩니다.
                </div>
            )}

            {briefing && (
                <>
                    {/* AI 요약 */}
                    {briefing.ai_summary && (
                        <div className="mb-4 p-4 bg-amber-950/30 border border-amber-800/40 rounded-xl shrink-0">
                            <div className="flex items-center gap-2 mb-2">
                                <Sparkles size={14} className="text-amber-400" />
                                <span className="text-xs font-semibold text-amber-400">AI 장전 요약</span>
                            </div>
                            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                                {briefing.ai_summary}
                            </p>
                        </div>
                    )}

                    {/* 3분할 카드 */}
                    <div className="flex-1 overflow-hidden grid grid-cols-3 gap-4 min-h-0">
                        {/* DART 공시 */}
                        <div className="bg-slate-900/60 border border-slate-700/60 rounded-xl flex flex-col overflow-hidden">
                            <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-700/60 shrink-0">
                                <FileText size={15} className="text-yellow-400" />
                                <span className="text-sm font-semibold text-white">DART 공시</span>
                                <span className="ml-auto text-xs bg-yellow-900/50 text-yellow-300 px-2 py-0.5 rounded-full">
                                    {briefing.dart_count}건
                                </span>
                            </div>
                            <div className="flex-1 overflow-y-auto p-3">
                                <DartCard items={briefing.dart_items} />
                            </div>
                        </div>

                        {/* AI 후보 종목 */}
                        <div className="bg-slate-900/60 border border-slate-700/60 rounded-xl flex flex-col overflow-hidden">
                            <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-700/60 shrink-0">
                                <Newspaper size={15} className="text-blue-400" />
                                <span className="text-sm font-semibold text-white">급등 후보 종목</span>
                                <span className="ml-auto text-xs text-slate-500 text-[10px]">코드 클릭 → 상세</span>
                                <span className="text-xs bg-blue-900/50 text-blue-300 px-2 py-0.5 rounded-full">
                                    {briefing.total_candidates}개
                                </span>
                            </div>
                            <div className="flex-1 overflow-y-auto p-3">
                                <CandidateCard
                                    candidates={briefing.all_candidates}
                                    onSelectStock={(code, name) => setModalStock({ code, name })}
                                />
                            </div>
                        </div>

                        {/* 테마 스캔 */}
                        <div className="bg-slate-900/60 border border-slate-700/60 rounded-xl flex flex-col overflow-hidden">
                            <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-700/60 shrink-0">
                                <Tag size={15} className="text-purple-400" />
                                <span className="text-sm font-semibold text-white">감지된 테마</span>
                                <span className="ml-auto text-xs bg-purple-900/50 text-purple-300 px-2 py-0.5 rounded-full">
                                    {Object.keys(briefing.themes_detected).length}개
                                </span>
                            </div>
                            <div className="flex-1 overflow-y-auto p-3">
                                <ThemeCard themes={briefing.themes_detected} />
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
