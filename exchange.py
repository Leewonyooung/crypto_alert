"""거래소 API 래퍼"""
import time
import ccxt
import pandas as pd
from config import Config


class ExchangeClient:
    """거래소 클라이언트 (ccxt 기반)"""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self._client: ccxt.Exchange | None = None

    @property
    def client(self) -> ccxt.Exchange:
        """ccxt 클라이언트 (지연 초기화)"""
        if self._client is None:
            exchange_class = getattr(ccxt, self.config.EXCHANGE_ID)
            options = {
                "apiKey": self.config.API_KEY or None,
                "secret": self.config.API_SECRET or None,
                "sandbox": self.config.TESTNET,
                "enableRateLimit": True,
            }
            # Bybit: USDT-M 영구선물 거래
            if self.config.EXCHANGE_ID == "bybit":
                options["options"] = {"defaultType": "swap"}
            self._client = exchange_class(options)
        return self._client

    def fetch_ohlcv(
        self,
        symbol: str | None = None,
        timeframe: str = "1h",
        limit: int = 100,
        since: int | None = None,
    ) -> pd.DataFrame:
        """OHLCV(캔들) 데이터 조회"""
        symbol = symbol or self.config.SYMBOL
        ohlcv = self.client.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)

        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df

    def fetch_ohlcv_range(
        self,
        symbol: str | None = None,
        timeframe: str = "15m",
        start_ts: int | None = None,
        end_ts: int | None = None,
        limit_per_request: int = 1000,
    ) -> pd.DataFrame:
        """지정 기간 OHLCV 데이터 조회 (청크 단위)"""
        symbol = symbol or self.config.SYMBOL
        all_ohlcv = []
        since = start_ts
        max_iter = 1000

        for _ in range(max_iter):
            batch = self.client.fetch_ohlcv(symbol, timeframe, since=since, limit=limit_per_request)
            if not batch:
                break
            all_ohlcv.extend(batch)
            last_ts = batch[-1][0]
            if end_ts and last_ts >= end_ts:
                all_ohlcv = [c for c in all_ohlcv if c[0] <= end_ts]
                break
            since = last_ts + 1
            time.sleep(0.2)

        df = pd.DataFrame(
            all_ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
        df.set_index("timestamp", inplace=True)
        return df

    def get_balance(self, currency: str = "USDT") -> float:
        """잔고 조회 (선물: USDT 잔고)"""
        balance = self.client.fetch_balance()
        return float(balance.get("free", {}).get(currency, 0) or 0)

    def _get_position_size(self, side: str, symbol: str | None = None) -> float:
        """선물 포지션 수량 조회 (side: long | short)"""
        symbol = symbol or self.config.SYMBOL
        positions = self.client.fetch_positions([symbol])
        for pos in positions:
            if pos.get("symbol") == symbol and pos.get("side") == side:
                size = pos.get("contracts") or pos.get("contractSize") or pos.get("size") or 0
                return float(size) if size else 0.0
        return 0.0

    def get_long_position(self, symbol: str | None = None) -> float:
        """롱 포지션 수량"""
        return self._get_position_size("long", symbol)

    def get_short_position(self, symbol: str | None = None) -> float:
        """숏 포지션 수량"""
        return self._get_position_size("short", symbol)

    def create_market_buy_order(
        self,
        symbol: str | None = None,
        amount: float | None = None,
        cost: float | None = None,
    ) -> dict | None:
        """시장가 매수 주문 (실거래 시에만 실행)
        amount: 매수할 수량 (기준통화), cost: 매수할 금액 (견적통화, 예: USDT)
        """
        if self.config.MODE != "live":
            return {"simulated": True, "side": "buy"}
        symbol = symbol or self.config.SYMBOL
        if cost and not amount:
            ticker = self.client.fetch_ticker(symbol)
            price = ticker["last"]
            amount = cost / price
        return self.client.create_market_buy_order(symbol, amount)

    def create_market_sell_order(
        self,
        symbol: str | None = None,
        amount: float | None = None,
        cost: float | None = None,
    ) -> dict | None:
        """시장가 매도 주문 (롱 청산 또는 숏 진입)
        amount: 수량, cost: USDT 금액 (숏 진입 시)
        """
        if self.config.MODE != "live":
            return {"simulated": True, "side": "sell"}
        symbol = symbol or self.config.SYMBOL
        if cost and not amount:
            ticker = self.client.fetch_ticker(symbol)
            amount = cost / ticker["last"]
        return self.client.create_market_sell_order(symbol, amount)
