"""기술적 지표 계산 모듈"""
import pandas as pd
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """RSI(상대강도지수) 계산"""
    rsi = RSIIndicator(close=df["close"], window=period)
    return rsi.rsi()


def calculate_bollinger_bands(df: pd.DataFrame, period: int = 14, std_dev: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """볼린저밴드 계산 (상단, 중간, 하단)"""
    bb = BollingerBands(close=df["close"], window=period, window_dev=std_dev)
    return bb.bollinger_hband(), bb.bollinger_mavg(), bb.bollinger_lband()


def add_indicators(
    df: pd.DataFrame,
    rsi_period: int = 14,
    bb_period: int = 14,
    rsi_only: bool = False,
) -> pd.DataFrame:
    """OHLCV 데이터에 RSI와(선택) 볼린저밴드 추가"""
    df = df.copy()

    df["rsi"] = calculate_rsi(df, rsi_period)
    if not rsi_only:
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = calculate_bollinger_bands(df, bb_period)

    return df
