import os
import logging
import asyncio
import time
import httpx
from datetime import datetime
from dotenv import load_dotenv
from pykrx import stock

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

    async def get_minute_chart(self, code: str, minute: int = 5) -> list[dict]:
        """KIS REST API로 분봉 데이터 조회 (최대 30개)"""
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
            "FID_INPUT_HOUR_1": "155000",
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
    async def get_volume_rank(self, max_price: int = 20000, limit: int = 20) -> list[dict]:
        """pykrx로 급등주 조회: 등락률 상위 + 가격 필터"""
        today = datetime.now().strftime("%Y%m%d")

        # pykrx는 동기 함수이므로 스레드에서 실행
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None, lambda: stock.get_market_ohlcv_by_ticker(today, market="ALL")
        )

        if df.empty:
            logger.warning("pykrx returned empty dataframe")
            return []

        # 필터: 가격 > 0, 가격 < max_price, 등락률 > 0
        filtered = df[
            (df["종가"] > 0) & (df["종가"] < max_price) & (df["등락률"] > 0)
        ]

        # 등락률 내림차순 정렬
        top = filtered.sort_values("등락률", ascending=False).head(limit)

        # 종목명 조회
        names = {}
        try:
            name_list = await loop.run_in_executor(
                None, lambda: {t: stock.get_market_ticker_name(t) for t in top.index}
            )
            names = name_list
        except Exception:
            pass

        results = []
        for ticker in top.index:
            row = top.loc[ticker]
            prev_close = int(row["종가"] - row["종가"] * row["등락률"] / (100 + row["등락률"]))
            change_price = int(row["종가"]) - prev_close
            results.append({
                "code": ticker,
                "name": names.get(ticker, ticker),
                "price": int(row["종가"]),
                "change_rate": round(float(row["등락률"]), 2),
                "volume": int(row["거래량"]),
                "change_price": change_price,
            })

        logger.info(f"Surge stocks found: {len(results)}")
        return results
