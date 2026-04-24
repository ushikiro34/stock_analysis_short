import asyncio
import os
import logging
import time
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class KISRestClient:
    BASE_URL = "https://openapi.koreainvestment.com:9443"

    def __init__(self):
        self.app_key = os.getenv("KIS_APP_KEY")
        self.app_secret = os.getenv("KIS_APP_SECRET")
        self._token: str | None = None
        self._token_expires: float = 0

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires:
            return self._token
        async with httpx.AsyncClient(verify=False) as client:
            res = await client.post(
                f"{self.BASE_URL}/oauth2/tokenP",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self.app_key,
                    "appsecret": self.app_secret,
                },
            )
            res.raise_for_status()
            data = res.json()
            self._token = data["access_token"]
            self._token_expires = time.time() + 23 * 3600
            logger.info("KIS access token obtained")
            return self._token

    async def get_minute_chart(self, code: str, until_hour: str = "155000") -> list[dict]:
        """KIS REST API로 분봉 데이터 조회 (최대 30개).

        Args:
            code: 종목 코드
            until_hour: 기준 시각 HHMMSS — 이 시각 이전 30봉 반환 (기본: 장 마감 155000)
        """
        token = await self._get_token()
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST03010200",
            "content-type": "application/json; charset=utf-8",
        }
        params = {
            "FID_ETC_CLS_CODE": "",
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_HOUR_1": until_hour,
            "FID_PW_DATA_INCU_YN": "N",
        }

        async with httpx.AsyncClient(verify=False) as client:
            res = await client.get(
                f"{self.BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
                headers=headers,
                params=params,
            )
            res.raise_for_status()
            data = res.json()

        output = data.get("output2", [])
        today = datetime.now().strftime("%Y-%m-%d")
        results = []
        for item in output:
            vol = int(item.get("cntg_vol", "0"))
            hour_str = item.get("stck_cntg_hour", "")
            if len(hour_str) < 6:
                continue
            time_str = f"{today}T{hour_str[:2]}:{hour_str[2:4]}:{hour_str[4:6]}"
            results.append({
                "time": time_str,
                "open": int(item.get("stck_oprc", "0")),
                "high": int(item.get("stck_hgpr", "0")),
                "low": int(item.get("stck_lwpr", "0")),
                "close": int(item.get("stck_prpr", "0")),
                "volume": vol,
            })

        results.reverse()  # 시간 오름차순으로
        return results

    async def get_full_day_minute_chart(self, code: str, since_hour: str = "090000") -> list[dict]:
        """오늘 since_hour 이후 전체 분봉을 페이지네이션으로 수집.

        KIS API는 1회 최대 30봉을 반환하므로,
        가장 오래된 봉 시각을 until_hour로 삼아 반복 호출하여 합산한다.

        Args:
            code: 종목 코드
            since_hour: 수집 시작 시각 HHMMSS (기본: 장 시작 090000)

        Returns:
            오름차순 정렬된 분봉 리스트
        """
        all_candles: list[dict] = []
        seen: set[str] = set()
        until = "160000"  # 장 마감 이후부터 역방향으로

        for _ in range(10):  # 최대 10회 호출 (300봉 ≈ 5시간 커버)
            batch = await self.get_minute_chart(code, until_hour=until)
            if not batch:
                break

            # 중복 제거 후 새 봉만 추출
            new = [c for c in batch if c["time"] not in seen]
            if not new:
                break

            for c in new:
                seen.add(c["time"])

            # 오래된 봉을 앞에 추가 (new는 오름차순, 그 전체가 기존보다 이전)
            all_candles = new + all_candles

            # 가장 오래된 봉 시각 → 다음 호출의 until 기준
            oldest = new[0]["time"]  # "YYYY-MM-DDTHH:MM:SS"
            oldest_hour = oldest[11:13] + oldest[14:16] + oldest[17:19]

            if oldest_hour <= since_hour:
                break

            until = oldest_hour
            await asyncio.sleep(0.2)  # API 과호출 방지

        # since_hour 이전 봉 제거
        def _to_hms(t: str) -> str:
            return t[11:13] + t[14:16] + t[17:19] if len(t) >= 19 else "000000"

        return [c for c in all_candles if _to_hms(c["time"]) >= since_hour]
    async def get_kr_fundamental(self, code: str) -> dict:
        """KIS REST API로 국내 주식 펀더멘털 데이터 조회 (PER, PBR, EPS, BPS)
        tr_id: FHKST01010100 - 주식현재가 시세
        FID_COND_MRKT_DIV_CODE=J : KOSPI/KOSDAQ 공통 코드
        """
        token = await self._get_token()
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010100",
            "content-type": "application/json; charset=utf-8",
        }
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
        }
        async with httpx.AsyncClient(verify=False) as client:
            res = await client.get(
                f"{self.BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
                headers=headers,
                params=params,
            )
            # 500 오류는 KIS 서버 일시 장애일 수 있으므로 1회 재시도
            if res.status_code == 500:
                import asyncio as _aio
                await _aio.sleep(1)
                res = await client.get(
                    f"{self.BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
                    headers=headers,
                    params=params,
                )
            res.raise_for_status()
            data = res.json()

        if data.get("rt_cd") != "0":
            logger.warning(f"[{code}] KIS fundamental error: {data.get('msg1')}")
            return {}

        out = data.get("output", {})
        try:
            per = float(out.get("per", 0) or 0)
            pbr = float(out.get("pbr", 0) or 0)
            eps = float(out.get("eps", 0) or 0)
            bps = float(out.get("bps", 0) or 0)
            roe = (eps / bps * 100) if bps > 0 else 0
            return {
                "per": per,
                "pbr": pbr,
                "roe": roe,
                "eps": eps,
                "bps": bps,
                "eps_growth": 0,
                "net_loss": bool(eps < 0),
                "high_debt": bool(pbr > 3.0),
            }
        except (ValueError, TypeError) as e:
            logger.error(f"[{code}] KIS fundamental parse error: {e}")
            return {}

    async def get_volume_rank(self, max_price: int = 20000, limit: int = 100, min_change_rate: float = 0.001) -> list[dict]:
        """KIS REST API로 거래량 상위 종목 조회
        min_change_rate: 최소 등락률 (기본 0.001 = 양봉만, -999 = 전체)
        """
        token = await self._get_token()
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHPST01720000",
            "content-type": "application/json; charset=utf-8",
        }

        all_results: list[dict] = []

        # KOSPI + KOSDAQ 모두 조회
        for mkt_code in ("J", "Q"):
            params = {
                "FID_COND_MRKT_DIV_CODE": mkt_code,
                "FID_COND_SCR_DIV_CODE": "20171",
                "FID_INPUT_ISCD": "0000",
                "FID_DIV_CLS_CODE": "0",
                "FID_BLNG_CLS_CODE": "0",
                "FID_TRGT_CLS_CODE": "111111111",
                "FID_TRGT_EXLS_CLS_CODE": "000000",
                "FID_INPUT_PRICE_1": "",
                "FID_INPUT_PRICE_2": str(max_price),
                "FID_VOL_CNT": "100000",
                "FID_INPUT_DATE_1": "",
                "FID_RANK_SORT_CLS_CODE": "0",
            }

            try:
                async with httpx.AsyncClient(verify=False) as client:
                    res = await client.get(
                        f"{self.BASE_URL}/uapi/domestic-stock/v1/quotations/volume-rank",
                        headers=headers,
                        params=params,
                    )
                    res.raise_for_status()
                    data = res.json()

                if data.get("rt_cd") != "0":
                    logger.warning(f"KIS volume rank error (mkt={mkt_code}): {data.get('msg1')}")
                    continue

                for item in data.get("output", []):
                    try:
                        price = int(item.get("stck_prpr", "0"))
                        if price <= 0 or price > max_price:
                            continue
                        change_rate = float(item.get("prdy_ctrt", "0"))
                        if change_rate < min_change_rate:
                            continue
                        name = item.get("hts_kor_isnm", "")
                        if any(kw in name for kw in (
                            "레버리지", "인버스", "ETN", "곱버스", "선물",
                            "KODEX", "TIGER", "KBSTAR", "ARIRANG", "HANARO",
                            "SOL", "ACE", "KOSEF", "FOCUS", "TRUE", "파워",
                            "스팩", "SPAC", "리츠", "REIT",
                        )):
                            continue
                        all_results.append({
                            "code": item.get("mksc_shrn_iscd", ""),
                            "name": item.get("hts_kor_isnm", ""),
                            "price": price,
                            "high": int(item.get("stck_hgpr", "0")),
                            "change_rate": round(change_rate, 2),
                            "volume": int(item.get("acml_vol", "0")),
                            "change_price": int(item.get("prdy_vrss", "0")),
                        })
                    except (ValueError, TypeError):
                        continue

            except Exception as e:
                logger.error(f"KIS volume rank error (mkt={mkt_code}): {e}")

        # 등락률 내림차순 정렬 후 limit 적용
        all_results.sort(key=lambda x: x["change_rate"], reverse=True)
        result = all_results[:limit]
        logger.info(f"KIS surge stocks: {len(result)}")
        return result


# ── 앱 전역 싱글턴 (토큰 캐시 공유) ─────────────────────────
_default_client: KISRestClient | None = None


def get_kis_client() -> KISRestClient:
    """전역 KISRestClient 싱글턴 반환 — 토큰을 앱 전체에서 공유"""
    global _default_client
    if _default_client is None:
        _default_client = KISRestClient()
    return _default_client


# ════════════════════════════════════════════════════════════════
# 실전 주문/잔고 API
# ════════════════════════════════════════════════════════════════

class KISOrderClient:
    """KIS 실전 주문 클라이언트 (계좌번호 필요)"""

    BASE_URL = "https://openapi.koreainvestment.com:9443"

    def __init__(self):
        self.app_key    = os.getenv("KIS_APP_KEY")
        self.app_secret = os.getenv("KIS_APP_SECRET")
        self.cano       = os.getenv("KIS_CANO")           # 계좌번호 앞 8자리
        self.acnt_prdt  = os.getenv("KIS_ACNT_PRDT_CD", "01")
        self._token: str | None = None
        self._token_expires: float = 0

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires:
            return self._token
        async with httpx.AsyncClient(verify=False) as client:
            res = await client.post(
                f"{self.BASE_URL}/oauth2/tokenP",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self.app_key,
                    "appsecret": self.app_secret,
                },
            )
            res.raise_for_status()
            data = res.json()
            self._token = data["access_token"]
            self._token_expires = time.time() + 23 * 3600
            return self._token

    def _order_headers(self, tr_id: str) -> dict:
        return {
            "authorization": f"Bearer {self._token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "content-type": "application/json; charset=utf-8",
        }

    # ── 매수 주문 ─────────────────────────────────────────────

    async def place_buy_order(self, code: str, qty: int, price: int = 0) -> dict:
        """시장가(price=0) 또는 지정가 매수.

        Returns:
            {"order_no": str, "order_time": str} 또는 에러 시 raise
        """
        await self._get_token()
        # price=0 → 시장가(tr_id TTTC0802U), price>0 → 지정가(TTTC0801U)
        if price == 0:
            tr_id = "TTTC0802U"
            ord_dvsn = "01"   # 시장가
            ord_unpr = "0"
        else:
            tr_id = "TTTC0801U"
            ord_dvsn = "00"   # 지정가
            ord_unpr = str(price)

        body = {
            "CANO": self.cano,
            "ACNT_PRDT_CD": self.acnt_prdt,
            "PDNO": code,
            "ORD_DVSN": ord_dvsn,
            "ORD_QTY": str(qty),
            "ORD_UNPR": ord_unpr,
        }
        async with httpx.AsyncClient(verify=False) as client:
            res = await client.post(
                f"{self.BASE_URL}/uapi/domestic-stock/v1/trading/order-cash",
                headers=self._order_headers(tr_id),
                json=body,
            )
            res.raise_for_status()
            data = res.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(f"[KIS] 매수 주문 실패 {code}: {data.get('msg1')}")

        out = data.get("output", {})
        logger.info(f"[KIS] BUY {code} x{qty} @ {'시장가' if price==0 else price} → 주문번호 {out.get('ODNO')}")
        return {"order_no": out.get("ODNO", ""), "order_time": out.get("ORD_TMD", "")}

    # ── 매도 주문 ─────────────────────────────────────────────

    async def place_sell_order(self, code: str, qty: int, price: int = 0) -> dict:
        """시장가(price=0) 또는 지정가 매도."""
        await self._get_token()
        if price == 0:
            tr_id = "TTTC0801U"
            ord_dvsn = "01"
            ord_unpr = "0"
        else:
            tr_id = "TTTC0801U"
            ord_dvsn = "00"
            ord_unpr = str(price)

        body = {
            "CANO": self.cano,
            "ACNT_PRDT_CD": self.acnt_prdt,
            "PDNO": code,
            "ORD_DVSN": ord_dvsn,
            "ORD_QTY": str(qty),
            "ORD_UNPR": ord_unpr,
            "SLL_TYPE": "01",   # 매도 구분
        }
        async with httpx.AsyncClient(verify=False) as client:
            res = await client.post(
                f"{self.BASE_URL}/uapi/domestic-stock/v1/trading/order-cash",
                headers=self._order_headers(tr_id),
                json=body,
            )
            res.raise_for_status()
            data = res.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(f"[KIS] 매도 주문 실패 {code}: {data.get('msg1')}")

        out = data.get("output", {})
        logger.info(f"[KIS] SELL {code} x{qty} @ {'시장가' if price==0 else price} → 주문번호 {out.get('ODNO')}")
        return {"order_no": out.get("ODNO", ""), "order_time": out.get("ORD_TMD", "")}

    # ── 주문 취소 ─────────────────────────────────────────────

    async def cancel_order(self, order_no: str, code: str, qty: int) -> bool:
        """미체결 주문 취소."""
        await self._get_token()
        body = {
            "CANO": self.cano,
            "ACNT_PRDT_CD": self.acnt_prdt,
            "KRX_FWDG_ORD_ORGNO": "",
            "ORGN_ODNO": order_no,
            "PDNO": code,
            "ORD_DVSN": "00",
            "RVSE_CNCL_DVSN_CD": "02",   # 02=취소
            "ORD_QTY": str(qty),
            "ORD_UNPR": "0",
            "QTY_ALL_ORD_YN": "Y",
        }
        async with httpx.AsyncClient(verify=False) as client:
            res = await client.post(
                f"{self.BASE_URL}/uapi/domestic-stock/v1/trading/order-rvsecncl",
                headers=self._order_headers("TTTC0803U"),
                json=body,
            )
            res.raise_for_status()
            data = res.json()

        ok = data.get("rt_cd") == "0"
        logger.info(f"[KIS] CANCEL 주문{order_no} {'성공' if ok else '실패: ' + data.get('msg1','')}")
        return ok

    # ── 잔고 조회 ─────────────────────────────────────────────

    async def get_balance(self) -> dict:
        """실제 보유 종목 및 예수금 조회.

        Returns:
            {
                "cash": 주문가능현금,
                "total_eval": 총평가금액,
                "positions": [{"code", "name", "qty", "avg_price", "current_price", "pnl_pct"}, ...]
            }
        """
        await self._get_token()
        params = {
            "CANO": self.cano,
            "ACNT_PRDT_CD": self.acnt_prdt,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        async with httpx.AsyncClient(verify=False) as client:
            res = await client.get(
                f"{self.BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance",
                headers=self._order_headers("TTTC8434R"),
                params=params,
            )
            res.raise_for_status()
            data = res.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(f"[KIS] 잔고 조회 실패: {data.get('msg1')}")

        output1 = data.get("output1", [])   # 보유 종목
        output2 = data.get("output2", [{}]) # 계좌 요약

        positions = []
        for item in output1:
            qty = int(item.get("hldg_qty", "0"))
            if qty <= 0:
                continue
            positions.append({
                "code":          item.get("pdno", ""),
                "name":          item.get("prdt_name", ""),
                "qty":           qty,
                "avg_price":     float(item.get("pchs_avg_pric", "0")),
                "current_price": float(item.get("prpr", "0")),
                "pnl_pct":       float(item.get("evlu_pfls_rt", "0")),
            })

        summary = output2[0] if output2 else {}
        return {
            "cash":       float(summary.get("dnca_tot_amt", "0")),
            "total_eval": float(summary.get("tot_evlu_amt", "0")),
            "positions":  positions,
        }

    # ── 체결 확인 ─────────────────────────────────────────────

    async def get_order_status(self, order_no: str) -> dict:
        """주문 체결 여부 조회.

        Returns:
            {"filled": bool, "filled_qty": int, "avg_price": float}
        """
        await self._get_token()
        params = {
            "CANO": self.cano,
            "ACNT_PRDT_CD": self.acnt_prdt,
            "INQR_STRT_DT": datetime.now().strftime("%Y%m%d"),
            "INQR_END_DT":  datetime.now().strftime("%Y%m%d"),
            "SLL_BUY_DVSN_CD": "00",
            "INQR_DVSN": "00",
            "PDNO": "",
            "CCLD_DVSN": "00",
            "ORD_GNO_BRNO": "",
            "ODNO": order_no,
            "INQR_DVSN_3": "00",
            "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        async with httpx.AsyncClient(verify=False) as client:
            res = await client.get(
                f"{self.BASE_URL}/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
                headers=self._order_headers("TTTC8001R"),
                params=params,
            )
            res.raise_for_status()
            data = res.json()

        for item in data.get("output1", []):
            if item.get("odno") == order_no:
                filled_qty = int(item.get("tot_ccld_qty", "0"))
                return {
                    "filled":     filled_qty > 0,
                    "filled_qty": filled_qty,
                    "avg_price":  float(item.get("avg_prvs", "0")),
                    "status":     item.get("ord_stts", ""),
                }
        return {"filled": False, "filled_qty": 0, "avg_price": 0.0, "status": "unknown"}


# ── 싱글턴 ───────────────────────────────────────────────────
_order_client: KISOrderClient | None = None


def get_kis_order_client() -> KISOrderClient:
    """실전 주문 클라이언트 싱글턴"""
    global _order_client
    if _order_client is None:
        _order_client = KISOrderClient()
    return _order_client
