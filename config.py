"""거래 봇 설정 관리"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """설정 클래스"""
    # 거래소
    EXCHANGE_ID = os.getenv("EXCHANGE_ID", "bybit")
    API_KEY = os.getenv("API_KEY", "")
    API_SECRET = os.getenv("API_SECRET", "")

    # 거래
    SYMBOL = os.getenv("SYMBOL", "BTC/USDT")
    TESTNET = os.getenv("TESTNET", "false").lower() == "true"
    TRADE_AMOUNT_USDT = float(os.getenv("TRADE_AMOUNT_USDT", "10"))  # 1회 거래당 USDT

    # RSI 파라미터 (14기간, 70 과매수 / 30 과매도)
    RSI_PERIOD = int(os.getenv("RSI_PERIOD", 14))
    RSI_OVERSOLD = int(os.getenv("RSI_OVERSOLD", 30))
    RSI_OVERBOUGHT = int(os.getenv("RSI_OVERBOUGHT", 70))

    # 볼린저밴드 파라미터 (14기간, 상단 10% 이탈)
    BB_PERIOD = int(os.getenv("BB_PERIOD", 14))
    BB_BREAK_PCT = float(os.getenv("BB_BREAK_PCT", "0.05"))

    # 모드: paper(모의거래), live(실거래)
    MODE = os.getenv("MODE", "paper").lower()
