# TODO - 미구현 기능 및 향후 계획

마지막 업데이트: 2026-04-24

---

## 🔴 High Priority

### 1. 백테스팅 슬리피지 모델
- 현재: 체결가 = 신호 발생 시점 종가 (슬리피지 0 가정 → 과도하게 낙관적)
- 목표: 현실적인 체결가 시뮬레이션
- 구현 포인트:
  - 매수: 다음 캔들 시가 + 0.1~0.3% 슬리피지
  - 매도: 다음 캔들 시가 − 0.1~0.3% 슬리피지 (or 지정가 vs 시가 중 불리한 쪽)
  - 설정값으로 슬리피지율 조정 가능하게
- 관련 파일: `backend/core/backtest/engine.py`

### 2. Telegram 알림 연동
- 현재: 브라우저 Notification API (브라우저 실행 중에만 작동)
- 목표: Telegram Bot으로 서버 → 사용자 알림 (백그라운드 상시)
- 적용 시점: 모의투자 안정화 후 실전 매매 개시 시 동시 적용
- 구현 포인트:
  - `python-telegram-bot` 라이브러리 추가
  - `.env`에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 추가
  - BUY 신호 발생 / 모의투자 체결 / 손절 시 메시지 전송
- 관련 파일: `backend/core/paper_engine.py`, `backend/core/signal_service.py`

---

## 🟡 Medium Priority

### 3. 보유 포지션 컵앤핸들 상태 실시간 추적
- 현재: `cup_handle_status`는 진입 시점 1회만 저장 (이후 업데이트 없음)
- 문제: 장 중에 패턴이 이미 완성됐는지, 진행 중인지 알 수 없음
- 목표: `paper_engine.tick()` 루프에서 오픈 포지션 컵앤핸들 상태 재분석 후 DB 업데이트
- 구현 포인트:
  - 청산 체크 후 `generate_entry_signal(pos.code)` 호출 → `breakout_status` 갱신
  - `PaperTrade` OPEN 행의 `cup_handle_status` 컬럼 업데이트
  - 프론트 포지션 카드에 현재 상태 표시 (fresh/pre/forming/expired)
- 검토 필요: API 호출 부하 (포지션 수 × 5분 주기)
- 적용 시점: 다음주 장 중 패턴 동작 확인 후 결정

### 4. 종목 스코어 고도화
- `eps_growth` 현재 항상 0 (단일 시점 데이터라 계산 불가)
- 분기별 EPS 비교를 위한 히스토리 데이터 수집 필요
- KIS `FHKST01010100` 응답에 분기 데이터 없음 → 별도 API 필요

### 5. Finviz 백그라운드 자동 갱신 (보류)
- 현재: 요청 시 갱신 (캐시 TTL 5분)
- 보류 이유: Rate Limit (분당 10회) 제약, 현재 캐시 방식으로 충분
- 구현 시 고려사항:
  - `app.on_event("startup")`에 백그라운드 태스크 추가
  - Finviz 전략별 순차 갱신 (간격 6초 이상 유지)

---

## 🟢 Low Priority / 장기 계획

### 6. 실전 자동매매 연동
- KIS 실전계좌 주문 API 연동 (모의투자 → 실전)
- 관련 KIS tr_id: `TTTC0802U` (매수), `TTTC0801U` (매도)
- ⚠️ 주의: 실제 자금 운용, 충분한 검증 후 도입

### 7. 머신러닝 신호 개선
- 현재 규칙 기반(Rule-based) → ML 보조 필터 추가
- 방향: XGBoost / LightGBM으로 BUY 신호 정밀도 향상
- 필요 데이터: 과거 신호 발생 → 실제 수익률 레이블링 (충분한 거래 이력 필요)

### 8. 미국 시장 모의투자 지원
- 현재 Paper Trading: KR 전용 (KIS API 의존)
- US 시장용: yfinance 기반 가격 조회로 교체 필요
- 관련 파일: `backend/core/paper_engine.py` `_get_current_price()`

### 9. WebSocket 실시간 체결 (KR)
- 현재: 5분 polling 방식
- 목표: KIS WebSocket으로 실시간 체결가 수신
- 관련 KIS tr_id: `H0STCNT0` (실시간 체결)

---

## ✅ 완료된 항목 (참고용)

| 기능 | 완료 시점 |
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
| 모의투자 일괄청산 기능 | 2026-04-24 |
| 장 마감 후 매수신호 차단 (백엔드+프론트) | 2026-04-24 |
| 추격차단(chase_blocked) 종목 진입 버그 수정 | 2026-04-24 |
| 당일 손절 종목 재진입 쿨다운 | 2026-04-24 |
