import { useState, useEffect } from 'react';
import { Activity, Lock, Eye, EyeOff, AlertCircle } from 'lucide-react';

const BASE_URL: string = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');
const TOKEN_KEY = 'sa_auth_token';

export function getStoredToken(): string {
    return localStorage.getItem(TOKEN_KEY) ?? '';
}

function setStoredToken(token: string) {
    localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken() {
    localStorage.removeItem(TOKEN_KEY);
}

export async function checkTokenValid(): Promise<boolean> {
    const token = getStoredToken();
    if (!token) return false;
    try {
        const res = await fetch(`${BASE_URL}/auth/check?token=${encodeURIComponent(token)}`);
        const data = await res.json();
        return !!data.valid;
    } catch {
        return false;
    }
}

interface Props {
    onLogin: () => void;
}

export default function LoginPage({ onLogin }: Props) {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPw, setShowPw] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // 이미 유효한 토큰이 있으면 바로 통과
    useEffect(() => {
        checkTokenValid().then(valid => { if (valid) onLogin(); });
    }, [onLogin]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!username.trim() || !password) return;
        setLoading(true);
        setError('');
        try {
            const res = await fetch(`${BASE_URL}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: username.trim(), password }),
            });
            const data = await res.json();
            if (data.success && data.token) {
                setStoredToken(data.token);
                onLogin();
            } else {
                setError(data.message || '로그인 실패');
            }
        } catch {
            setError('서버에 연결할 수 없습니다.');
        }
        setLoading(false);
    };

    return (
        <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
            {/* 카드 */}
            <div className="w-full max-w-sm">
                {/* 로고 */}
                <div className="flex flex-col items-center mb-8">
                    <div className="w-14 h-14 bg-primary rounded-2xl flex items-center justify-center mb-3 shadow-lg shadow-primary/30">
                        <Activity size={28} className="text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-white">Stock Analysis</h1>
                    <p className="text-sm text-slate-500 mt-1">단타매매 전문 시스템</p>
                </div>

                {/* 폼 */}
                <div className="bg-surface border border-slate-700 rounded-2xl p-6 shadow-2xl">
                    <div className="flex items-center gap-2 mb-5">
                        <Lock size={15} className="text-slate-400" />
                        <span className="text-sm font-semibold text-slate-300">로그인</span>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-4">
                        {/* 아이디 */}
                        <div>
                            <label className="block text-xs text-slate-400 mb-1.5">아이디</label>
                            <input
                                type="text"
                                value={username}
                                onChange={e => setUsername(e.target.value)}
                                placeholder="아이디 입력"
                                autoComplete="username"
                                autoFocus
                                className="w-full px-3 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white
                                           placeholder-slate-500 focus:outline-none focus:border-primary transition-colors"
                            />
                        </div>

                        {/* 비밀번호 */}
                        <div>
                            <label className="block text-xs text-slate-400 mb-1.5">비밀번호</label>
                            <div className="relative">
                                <input
                                    type={showPw ? 'text' : 'password'}
                                    value={password}
                                    onChange={e => setPassword(e.target.value)}
                                    placeholder="비밀번호 입력"
                                    autoComplete="current-password"
                                    className="w-full px-3 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white
                                               placeholder-slate-500 focus:outline-none focus:border-primary transition-colors pr-10"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPw(v => !v)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                                    tabIndex={-1}
                                >
                                    {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                                </button>
                            </div>
                        </div>

                        {/* 에러 */}
                        {error && (
                            <div className="flex items-center gap-2 text-xs text-red-400 bg-red-900/20 border border-red-800/40 rounded-lg px-3 py-2">
                                <AlertCircle size={13} className="shrink-0" />
                                {error}
                            </div>
                        )}

                        {/* 버튼 */}
                        <button
                            type="submit"
                            disabled={loading || !username.trim() || !password}
                            className="w-full py-2.5 bg-primary hover:bg-primary/80 disabled:opacity-40 disabled:cursor-not-allowed
                                       text-white text-sm font-semibold rounded-lg transition-colors mt-2"
                        >
                            {loading ? '확인 중...' : '로그인'}
                        </button>
                    </form>
                </div>

                <p className="text-center text-xs text-slate-600 mt-4">
                    Stock Analysis System v2.0
                </p>
            </div>
        </div>
    );
}
