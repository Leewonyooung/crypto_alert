"""
Bybit API로 USDT 선물 알트코인 스캔
- 5분봉, RSI(14) < 20, 24h 거래량 2M USDT 이상만
- 5분마다 반복 스캔
- 텔레그램 채널의 특정 주제(Topic)로 알림 전송 가능
"""
import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

from exchange import ExchangeClient
from indicators import add_indicators

load_dotenv()


# 스캔 설정
TIMEFRAME = "5m"
RSI_PERIOD = 14
RSI_THRESHOLD = 20
MIN_VOLUME_USDT = 2_000_000   # 24h 거래량 2M USDT 이상
OHLCV_LIMIT = 50
# Bybit: 600 req/5초(IP당). 스캔당 load_markets(1) + fetch_tickers(1) + N×fetch_ohlcv → 0.01~0.02초 권장
SLEEP_BETWEEN_SYMBOLS = 0.2    # 최소 ~0.01(공격적) ~ 0.05(안전). 0.01이면 스캔당 약 2~5초
# 반복 주기(초). 기본 5분. Bybit 한계 고려 시 최소 5~10초까지 가능 (SLEEP_BETWEEN_SYMBOLS도 줄여야 함)
INTERVAL_SECONDS = int(os.getenv("ALT_LONG_INTERVAL_SECONDS", "300"))
INCLUDE_BTC = False            # False = 알트만


def get_usdt_perpetual_symbols(exchange: ExchangeClient) -> list[str]:
    """Bybit USDT 마진 영구선물(linear swap) 심볼 목록 조회"""
    client = exchange.client
    client.load_markets()
    symbols = []
    for sid, m in client.markets.items():
        if m.get("type") != "swap":
            continue
        if m.get("quote") == "USDT" or ":USDT" in sid:
            symbols.append(sid)
    return sorted(set(symbols))


def filter_by_volume(exchange: ExchangeClient, symbols: list[str], min_volume: float) -> list[str]:
    """24h 거래량이 min_volume USDT 이상인 심볼만 반환"""
    client = exchange.client
    try:
        tickers = client.fetch_tickers()
    except Exception:
        return symbols
    symbol_set = set(symbols)
    out = []
    for sid, t in tickers.items():
        if sid not in symbol_set:
            continue
        vol = float(t.get("quoteVolume") or t.get("volume") or 0)
        if vol >= min_volume:
            out.append(sid)
    return sorted(out)


def scan_symbol_rsi(
    exchange: ExchangeClient,
    symbol: str,
    timeframe: str = TIMEFRAME,
    limit: int = OHLCV_LIMIT,
    rsi_period: int = RSI_PERIOD,
) -> float | None:
    """한 심볼에 대해 최근 RSI(14) 값 반환. 실패 시 None."""
    try:
        df = exchange.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
        if df is None or len(df) < rsi_period + 1:
            return None
        df = add_indicators(df, rsi_period=rsi_period, bb_period=rsi_period, rsi_only=True)
        return float(df["rsi"].iloc[-1])
    except Exception:
        return None


def run_scan() -> list[tuple[str, float]]:
    """거래량 2M 이상 심볼만 스캔해 RSI < threshold 인 코인 목록 반환."""
    exchange = ExchangeClient()
    symbols = get_usdt_perpetual_symbols(exchange)
    if not INCLUDE_BTC:
        symbols = [s for s in symbols if "BTC/USDT" not in s and "BTC/USDT:USDT" not in s]

    symbols = filter_by_volume(exchange, symbols, MIN_VOLUME_USDT)
    print(f"총 {len(symbols)}개 심볼 스캔 (거래량 >={MIN_VOLUME_USDT/1e6:.0f}M USDT, 봉: {TIMEFRAME}, RSI({RSI_PERIOD}) < {RSI_THRESHOLD})")
    print("=" * 60)

    oversold: list[tuple[str, float]] = []
    for i, symbol in enumerate(symbols, 1):
        rsi = scan_symbol_rsi(exchange, symbol, timeframe=TIMEFRAME, rsi_period=RSI_PERIOD)
        if rsi is not None and rsi < RSI_THRESHOLD:
            oversold.append((symbol, rsi))
            print(f"  [발견] {symbol}  RSI = {rsi:.2f}")
        if i % 20 == 0:
            print(f"  ... 진행 {i}/{len(symbols)}")
        time.sleep(SLEEP_BETWEEN_SYMBOLS)

    return sorted(oversold, key=lambda x: x[1])


def print_result(result: list[tuple[str, float]]):
    """스캔 결과를 터미널에 출력"""
    print("\n" + "=" * 60)
    print("스캔 결과: RSI(14) <", RSI_THRESHOLD, "인 코인")
    print("=" * 60)
    if not result:
        print("  해당 조건 코인 없음.")
    else:
        for symbol, rsi in result:
            print(f"  {symbol}  RSI = {rsi:.2f}")
    print("=" * 60)


# ----- 텔레그램 (특정 주제로 전송) -----
def _telegram_env():
    """alt-long용 텔레그램 설정. 주제(Topic)에 보내려면 TELEGRAM_ALT_LONG_TOPIC_ID 필요."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN_ALT_LONG", "").strip() or os.getenv("TELEGRAM_BOT_TOKEN_ALT_SHORT", "").strip()
    chat_id = os.getenv("TELEGRAM_ALT_LONG_CHAT_ID", "").strip() or os.getenv("TELEGRAM_CHAT_ID", "").strip()
    topic_id_raw = os.getenv("TELEGRAM_ALT_LONG_TOPIC_ID", "").strip()
    topic_id = int(topic_id_raw) if topic_id_raw.isdigit() else None
    return bot_token, chat_id, topic_id


def send_telegram_to_topic(text: str) -> bool:
    """
    텔레그램 채널의 특정 주제(Topic)로 메시지 전송.
    .env: TELEGRAM_BOT_TOKEN_ALT_LONG, TELEGRAM_ALT_LONG_CHAT_ID, TELEGRAM_ALT_LONG_TOPIC_ID
    """
    bot_token, chat_id, topic_id = _telegram_env()
    if not bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if topic_id is not None:
        data["message_thread_id"] = topic_id
    try:
        r = requests.post(url, data=data, timeout=10)
        ok = r.status_code == 200 and r.json().get("ok")
        if not ok:
            print("❌ 텔레그램 전송 실패:", r.json().get("description", r.text))
        return ok
    except Exception as e:
        print("❌ 텔레그램 오류:", e)
        return False


def format_alert_message(result: list[tuple[str, float]]) -> str:
    """RSI 과매도 스캔 결과를 텔레그램용 HTML 메시지로 포맷"""
    lines = [
        f"<b>📈 Alt Long (5분봉 RSI &lt; {RSI_THRESHOLD})</b>",
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        "",
    ]
    if not result:
        lines.append("해당 조건 코인 없음.")
    else:
        for symbol, rsi in result:
            lines.append(f"• {symbol}  RSI = {rsi:.2f}")
    return "\n".join(lines)


def main():
    while True:
        interval_desc = f"{INTERVAL_SECONDS}s" if INTERVAL_SECONDS < 60 else f"{INTERVAL_SECONDS // 60}분"
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 스캔 시작 (다음 스캔: {interval_desc} 후)")
        result = run_scan()
        print_result(result)
        if result:
            bot_token, chat_id, topic_id = _telegram_env()
            if bot_token and chat_id:
                msg = format_alert_message(result)
                if send_telegram_to_topic(msg):
                    print("✅ 텔레그램 알림 전송 완료")
        print(f"\n{interval_desc} 후 재스캔...")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
