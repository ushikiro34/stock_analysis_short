import asyncio
import json
import logging
import os
import requests
import websockets
from dotenv import load_dotenv
from .aggregator import Aggregator

load_dotenv()

# Korea Investment OpenAPI WebSocket URL
WS_URL = "ws://ops.koreainvestment.com:21000"

class KISWebSocketClient:
    def __init__(self, codes: list, aggregator: Aggregator):
        self.codes = codes
        self.aggregator = aggregator
        self.app_key = os.getenv("KIS_APP_KEY")
        self.app_secret = os.getenv("KIS_APP_SECRET")
        self.approval_key = None
        self.ws = None

    def get_approval_key(self) -> str:
        """APP_KEY + APP_SECRET으로 WebSocket 접속용 approval_key 발급"""
        url = "https://openapi.koreainvestment.com:9443/oauth2/Approval"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "secretkey": self.app_secret,
        }
        res = requests.post(url, json=body)
        res.raise_for_status()
        self.approval_key = res.json()["approval_key"]
        logging.info("Approval key obtained successfully")
        return self.approval_key

    async def connect(self):
        # approval_key 자동 발급
        self.get_approval_key()

        async with websockets.connect(WS_URL) as websocket:
            self.ws = websocket
            logging.info("Connected to KIS WebSocket")

            # Subscribe to each code
            for code in self.codes:
                await self.subscribe(code)
            
            async for message in websocket:
                await self.handle_message(message)

    async def subscribe(self, code: str):
        # KIS Subscription format (Simplified for example)
        # Real format requires more headers and specific tr_id
        payload = {
            "header": {
                "approval_key": self.approval_key,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": "H0STCNT0", # Real-time price
                    "tr_key": code
                }
            }
        }
        await self.ws.send(json.dumps(payload))
        logging.info(f"Subscribed to {code}")

    async def handle_message(self, message):
        # KIS message handling logic
        # Usually split by '|' if it's text data
        if message.startswith("0") or message.startswith("1"):
            # This is real-time data
            parts = message.split("|")
            if len(parts) > 3:
                data_part = parts[3]
                # Parse specific fields based on KIS spec
                # Example: code, price, volume, time
                # Here we mock the parsing
                await self.aggregator.process_tick(message)
        else:
            # Control message
            logging.info(f"Control message: {message}")

async def main():
    # Example usage
    agg = Aggregator()
    client = KISWebSocketClient(["005930", "000660"], agg)
    await client.connect()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
