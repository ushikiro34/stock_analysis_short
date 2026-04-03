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

    async def get_volume_rank(self, max_price: int = 20000, limit: int = 100) -> list[dict]:
        """KIS REST API로 거래량 상위 급등주 조회"""
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
                        if change_rate <= 0:
                            continue
                        name = item.get("hts_kor_isnm", "")
                        if any(kw in name for kw in ("레버리지", "인버스", "ETN", "곱버스", "선물")):
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
