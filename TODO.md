# TODO - 미구현 기능 및 향후 계획

마지막 업데이트: 2026-03-05 (v2.3.1 기준)

---

## 🔴 High Priority

### 1. Telegram 알림 연동
- 현재: 브라우저 Notification API (사용자 허용 필요, 브라우저 실행 중에만 작동)
- 목표: Telegram Bot을 통해 서버→사용자 알림 (백그라운드 상시 전송)
- 관련 파일: `backend/core/paper_engine.py`, `backend/core/signal_service.py`
- 구현 포인트:
  - `python-telegram-bot` 라이브러리 추가
  - `.env`에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 추가
  - BUY 신호 발생 / 모의투자 체결 시 메시지 전송

---

## 🟡 Medium Priority

### 2. Finviz 백그라운드 자동 갱신 (보류 중)
- 현재: 요청 시 갱신 (캐시 TTL 5분)
- 목표: 서버 시작 시 백그라운드에서 주기적 갱신
- 보류 이유: 시스템 부하 우려, Rate Limit (분당 10회) 제약
- 구현 시 고려사항:
  - `app.on_event("startup")`에 백그라운드 태스크 추가
  - Finviz 전략별 순차 갱신 (간격 6초 이상 유지)

### 3. 백테스팅 고도화
- Monte Carlo 시뮬레이션 추가 (랜덤 샘플링으로 전략 강건성 검증)
- 슬리피지 모델 추가 (매수/매도 시 체결가 현실화)
- 복수 전략 동시 비교 (전략 A vs B 병렬 실행)
- 관련 파일: `backend/core/backtest/engine.py`

### 4. 종목 스코어 고도화
- `eps_growth` 현재 항상 0 (단일 시점 데이터라 계산 불가)
- 분기별 EPS 비교를 위한 히스토리 데이터 수집 필요
- KIS `FHKST01010100` 응답에 분기 데이터 없음 → 별도 API 필요

---

## 🟢 Low Priority / 장기 계획

### 5. 실제 자동매매 연동
- KIS 실전계좌 주문 API 연동 (모의투자 → 실전)
- 관련 KIS tr_id: `TTTC0802U` (매수), `TTTC0801U` (매도)
- ⚠️ 주의: 실제 자금 운용, 충분한 검증 후 도입

### 6. 머신러닝 신호 개선
- 현재 규칙 기반(Rule-based) 신호 → ML 보조 필터 추가
- 방향: XGBoost / LightGBM으로 BUY 신호 정밀도 향상
- 필요 데이터: 과거 신호 발생 → 실제 수익률 레이블링

### 7. 미국 시장 모의투자 지원
- 현재 Paper Trading: KR 전용 (KIS API 의존)
- US 시장용: yfinance 기반 가격 조회로 교체 필요
- 관련 파일: `backend/core/paper_engine.py` `_get_current_price()`

### 8. WebSocket 실시간 체결 (KR)
- 현재: 5분 polling 방식
- 목표: KIS WebSocket (`ws://ops.koreainvestment.com:31000`)으로 실시간 체결가 수신
- 관련 KIS tr_id: `H0STCNT0` (실시간 체결)

---

## ✅ 완료된 항목 (참고용)

| 기능 | 완료 버전 |
|------|----------|
| 진입/청산 신호 로직 (4대 전략) | v2.0.0 |
| 백테스팅 엔진 + 파라미터 최적화 | v2.0.0 |
| RSI 골든크로스 전략 | v2.1.0 |
| Finviz 스크리너 통합 (500개+) | v2.1.0 |
| 섹터 모니터링 | v2.1.0 |
| 페니스탁 거래량 패턴 필터 | v2.1.0 |
| KIS REST API 전환 (급등주, 펀더멘털) | v2.2.0 |
| 브라우저 매매신호 알림 시스템 | v2.2.0 |
| 모의투자 시뮬레이션 (Paper Trading) | v2.3.0 |
| KISRestClient 싱글턴 (토큰 공유) | v2.3.1 |
