# Stock Analysis System - 설치 및 세팅 가이드

새 PC에서 프로젝트를 동일하게 세팅하기 위한 단계별 가이드입니다.

---

## 📋 목차

1. [사전 요구사항](#1-사전-요구사항)
2. [저장소 클론](#2-저장소-클론)
3. [환경 변수 설정](#3-환경-변수-설정)
4. [백엔드 설치 및 실행](#4-백엔드-설치-및-실행)
5. [프론트엔드 설치 및 실행](#5-프론트엔드-설치-및-실행)
6. [API 키 발급 방법](#6-api-키-발급-방법)
7. [트러블슈팅](#7-트러블슈팅)

---

## 1. 사전 요구사항

| 도구 | 최소 버전 | 확인 명령 |
|------|-----------|-----------|
| Python | 3.10 이상 | `python --version` |
| Node.js | 18 이상 | `node --version` |
| npm | 9 이상 | `npm --version` |
| Git | 최신 권장 | `git --version` |

> **Windows 사용자**: Python은 [python.org](https://www.python.org/downloads/)에서 설치 시 "Add Python to PATH" 반드시 체크

---

## 2. 저장소 클론

```bash
git clone <repository-url> stock_analysis_short
cd stock_analysis_short
```

---

## 3. 환경 변수 설정

프로젝트 루트(`stock_analysis_short/`)에 `.env` 파일을 생성합니다.

```bash
# .env.example 파일을 복사 후 수정
cp .env.example .env
```

`.env` 파일 내용:

```env
# ── Database (Supabase PostgreSQL) ───────────────────────────
# Supabase Dashboard → Settings → Database → Connection string (URI)
DATABASE_URL=postgresql+asyncpg://postgres.[project-ref]:[YOUR-PASSWORD]@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres

# ── Korea Investment OpenAPI ─────────────────────────────────
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
KIS_APPROVAL_KEY=your_approval_key

# ── Frontend ─────────────────────────────────────────────────
VITE_API_URL=http://localhost:8000
```

> 각 값 발급 방법은 [API 키 발급 방법](#6-api-키-발급-방법) 참조

---

## 4. 백엔드 설치 및 실행

### 4-1. 가상환경 생성 및 활성화

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

### 4-2. 의존성 설치

```bash
pip install -r backend/requirements.txt
```

**설치되는 주요 패키지:**
- `fastapi` + `uvicorn` — API 서버
- `sqlalchemy[asyncio]` + `asyncpg` — 비동기 DB 연결
- `pykrx` — 한국 주식 OHLCV 데이터
- `yfinance` — 미국 주식 데이터
- `pandas`, `numpy` — 데이터 처리

### 4-3. 백엔드 서버 실행

```bash
uvicorn backend.api.main:app --reload --port 8000
```

성공 시 터미널에 다음과 같이 출력됩니다:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [...]
```

API 문서 확인: http://localhost:8000/docs

---

## 5. 프론트엔드 설치 및 실행

새 터미널을 열고 진행합니다.

```bash
cd frontend
npm install
npm run dev
```

성공 시 출력:
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
```

브라우저에서 http://localhost:5173 접속

---

## 6. API 키 발급 방법

### Supabase (DATABASE_URL)

1. [supabase.com](https://supabase.com) → 프로젝트 접속
2. 좌측 메뉴 **Settings → Database**
3. **Connection string** 섹션에서 **URI** 탭 선택
4. `[YOUR-PASSWORD]` 부분을 실제 DB 비밀번호로 교체
5. Connection string 앞부분 `postgresql://` → `postgresql+asyncpg://` 로 변경 필요

### KIS (한국투자증권) OpenAPI

**KIS_APP_KEY / KIS_APP_SECRET:**
1. [securities.koreainvestment.com/main/](https://securities.koreainvestment.com/main/) 접속
2. 로그인 → **OpenAPI → KIS Developers**
3. **앱 생성** → APP KEY / APP SECRET 발급
4. 모의투자 또는 실전투자 계정 연결

**KIS_APPROVAL_KEY:**
- WebSocket 연결용 승인 키
- KIS 앱 발급 후 API 호출로 자동 취득 가능
- 또는 KIS Developers 포털에서 별도 발급

> ⚠️ **중요**: KIS API 토큰은 **하루 1회 발급**이 제한됩니다.
> 서버 재시작 시 기존 토큰이 메모리에서 사라지므로, 하루에 여러 번 재시작하면 403 오류가 발생할 수 있습니다.
> 이 경우 익일 재시도하거나 모의투자 앱 키로 전환하세요.

---

## 7. 트러블슈팅

### ❌ KR 시장 신호 스캔이 빈 배열 반환

**증상**: `/signals/scan?market=KR` → `[]`

**원인**: KIS API 토큰 403 오류 (1일 1회 발급 제한)

**해결**:
- 동일한 앱 키로 하루에 서버를 여러 번 재시작했을 경우 발생
- 익일까지 대기 후 서버 1회만 시작
- 또는 KIS 모의투자용 별도 앱 키 사용

---

### ❌ KR 기술적 지표가 조회되지 않음

**증상**: `/stocks/{code}/score?market=KR` → `"technical": {}`

**원인**: `pykrx` 라이브러리 설치 누락 또는 import 오류

**해결**:
```bash
pip install pykrx
```

---

### ❌ 프론트엔드 빌드 오류 (TypeScript)

**증상**: `npm run build` 시 `api.ts` 관련 타입 오류

**원인**: `frontend/src/lib/api.ts` 파일이 없는 경우 (`.gitignore` 이슈로 과거에 누락되었던 파일, v2.3.1에서 수정됨)

**해결**: 최신 코드로 pull 후 재시도
```bash
git pull origin main
cd frontend && npm run build
```

---

### ❌ `DATABASE_URL` 연결 실패

**증상**: 서버 시작 시 `asyncpg` 연결 오류

**확인 사항**:
- `.env` 파일이 프로젝트 루트에 있는지 확인
- `postgresql://` → `postgresql+asyncpg://` 접두사 확인
- Supabase 프로젝트가 활성화 상태인지 확인
- 비밀번호에 특수문자가 있다면 URL 인코딩 필요 (`@` → `%40`)

---

### ❌ `pykrx` 데이터 조회 오류

**증상**: 한국 주식 OHLCV 조회 시 오류

**해결**:
```bash
pip install --upgrade pykrx
```

한국 거래소(KRX) 서버 점검 시간(오전 6~8시 등)에는 일시적으로 실패할 수 있습니다.

---

## 📁 프로젝트 구조 요약

```
stock_analysis_short/
├── .env                    ← 환경 변수 (직접 생성 필요)
├── .env.example            ← 환경 변수 템플릿
├── backend/
│   ├── api/
│   │   ├── main.py         ← FastAPI 앱 진입점
│   │   └── routers/        ← API 라우터들
│   ├── core/               ← 비즈니스 로직 (signal, score, paper engine)
│   ├── kis/                ← KIS API 클라이언트 (싱글턴)
│   ├── models/             ← SQLAlchemy DB 모델
│   └── requirements.txt    ← Python 의존성
└── frontend/
    ├── src/
    │   ├── lib/api.ts      ← 백엔드 API 호출 함수 모음
    │   └── pages/          ← 각 탭 컴포넌트
    └── package.json        ← Node.js 의존성
```

---

## ✅ 정상 동작 확인

백엔드와 프론트엔드를 모두 실행한 후:

```bash
# 미국 급등주 조회
curl http://localhost:8000/stocks/surge?market=US

# 한국 급등주 조회
curl http://localhost:8000/stocks/surge?market=KR

# 신호 스캔
curl http://localhost:8000/signals/scan?market=US

# 모의투자 상태
curl http://localhost:8000/paper/status
```

각 API가 정상 응답하면 세팅이 완료된 것입니다.
