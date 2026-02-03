"""
비트코인/이더리움 RSI·HMA 200 돌파 알림 봇 (Bybit)
- 5분봉, 15분봉 기준
- RSI 30 이하 돌파 → 과매도 구간 알림
- RSI 70 이상 돌파 → 과매수 구간 알림
- HMA 200일선 상단/하단 돌파 → 추세 전환 알림
- 텔레그램으로 실시간 알림 전송
"""

import requests
import pandas as pd
import numpy as np
import time
import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# 모니터링 대상: 비트코인, 이더리움
TARGET_SYMBOLS = ["BTCUSDT", "ETHUSDT"]

# Bybit interval: 5=5분, 15=15분
TARGET_INTERVALS = [
    ("5", "5분봉"),
    ("15", "15분봉"),
]


def load_config_from_env() -> Dict:
    """환경변수에서 설정값을 로드합니다."""
    required_vars = [
        "CHECK_INTERVAL", "RSI_PERIOD", "RSI_OVERSOLD", "RSI_OVERBOUGHT",
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print("❌ 필수 환경변수가 설정되지 않았습니다:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n.env 파일을 생성하고 필요한 환경변수를 설정하세요.")
        sys.exit(1)

    config = {
        "check_interval": int(os.getenv("CHECK_INTERVAL", "60")),
        "rsi_period": int(os.getenv("RSI_PERIOD", "14")),
        "rsi_oversold": float(os.getenv("RSI_OVERSOLD", "30")),
        "rsi_overbought": float(os.getenv("RSI_OVERBOUGHT", "70")),
        "category": os.getenv("CATEGORY", "linear"),
    }

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if telegram_bot_token and telegram_chat_id:
        config["telegram"] = {
            "bot_token": telegram_bot_token,
            "chat_id": telegram_chat_id
        }
        logger.info(f"✅ 텔레그램 설정 완료 (Chat ID: {telegram_chat_id})")
    else:
        logger.warning("⚠️ 텔레그램 설정이 완료되지 않았습니다.")

    return config


class BybitAPI:
    """바이비트 API 클래스"""

    BASE_URL = "https://api.bybit.com"

    @staticmethod
    def get_kline(symbol: str, interval: str, limit: int = 100, category: str = "linear") -> pd.DataFrame:
        """캔들 데이터 조회 (interval: 5=5분, 15=15분)"""
        url = f"{BybitAPI.BASE_URL}/v5/market/kline"
        params = {
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        response = requests.get(url, params=params)
        data = response.json()

        if data.get("retCode") != 0:
            logger.error(f"Error fetching {symbol}: {data.get('retMsg')}")
            return pd.DataFrame()

        klines = data.get("result", {}).get("list", [])
        if not klines:
            return pd.DataFrame()

        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'
        ])
        df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.iloc[::-1].reset_index(drop=True)
        return df


class TechnicalIndicators:
    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI 계산"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_wma(prices: pd.Series, period: int) -> pd.Series:
        """WMA (Weighted Moving Average) 계산"""
        weights = np.arange(1, period + 1, dtype=float)
        return prices.rolling(window=period).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )

    @staticmethod
    def calculate_hma(prices: pd.Series, period: int = 200) -> pd.Series:
        """HMA (Hull Moving Average) 계산 - HMA = WMA(2*WMA(n/2) - WMA(n), sqrt(n))"""
        half_period = period // 2
        sqrt_period = int(round(np.sqrt(period)))
        wma_half = TechnicalIndicators.calculate_wma(prices, half_period)
        wma_full = TechnicalIndicators.calculate_wma(prices, period)
        raw_hma = 2 * wma_half - wma_full
        return TechnicalIndicators.calculate_wma(raw_hma, sqrt_period)


class RSICrossoverBot:
    """RSI 30/70 돌파 알림 봇 (BTC, ETH 전용)"""

    def __init__(self, config: Dict, telegram_notifier: Optional['TelegramNotifier'] = None):
        self.config = config
        self.telegram_notifier = telegram_notifier
        # 알림 중복 방지: (symbol, interval) -> 마지막 알림 시간
        self.alert_history: Dict[str, datetime] = {}

    def _alert_key(self, symbol: str, interval: str) -> str:
        return f"{symbol}_{interval}"

    def analyze_symbol_interval(self, symbol: str, interval: str, interval_name: str) -> Optional[Dict]:
        """
        RSI + HMA 200 돌파 감지
        - RSI: 30 이하 과매도, 70 이상 과매수
        - HMA 200: 가격 상단 돌파(상승), 하단 돌파(하락)
        """
        category = self.config['category']
        # HMA 200 계산을 위해 250개 캔들 필요
        df = BybitAPI.get_kline(symbol, interval=interval, limit=250, category=category)

        if df.empty or len(df) < 210:  # RSI 14 + HMA 200 여유
            return None

        df['rsi'] = TechnicalIndicators.calculate_rsi(
            df['close'], period=self.config['rsi_period']
        )
        df['hma_200'] = TechnicalIndicators.calculate_hma(df['close'], period=200)

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        rsi_now = latest['rsi']
        rsi_prev = prev['rsi']
        price_now = latest['close']
        price_prev = prev['close']
        hma_now = latest['hma_200']
        hma_prev = prev['hma_200']

        if pd.isna(rsi_now) or pd.isna(rsi_prev) or pd.isna(hma_now) or pd.isna(hma_prev):
            return None

        signals = []
        signal_type = None

        # RSI 30 이하 돌파 (과매도)
        if rsi_prev > self.config['rsi_oversold'] and rsi_now <= self.config['rsi_oversold']:
            signals.append(f"RSI 30 이하 돌파 (과매도) - {rsi_prev:.1f} → {rsi_now:.1f}")
            signal_type = "oversold"

        # RSI 70 이상 돌파 (과매수)
        if rsi_prev < self.config['rsi_overbought'] and rsi_now >= self.config['rsi_overbought']:
            signals.append(f"RSI 70 이상 돌파 (과매수) - {rsi_prev:.1f} → {rsi_now:.1f}")
            signal_type = "overbought"

        # HMA 200 상단 돌파 (가격이 HMA 위로 돌파)
        if price_prev <= hma_prev and price_now > hma_now:
            signals.append(f"HMA 200 상단 돌파 - 가격이 HMA 위로 이탈")
            if not signal_type:
                signal_type = "hma_above"

        # HMA 200 하단 돌파 (가격이 HMA 아래로 이탈)
        if price_prev >= hma_prev and price_now < hma_now:
            signals.append(f"HMA 200 하단 돌파 - 가격이 HMA 아래로 이탈")
            if not signal_type:
                signal_type = "hma_below"

        if not signals:
            return None

        # HMA 200 대비 상단/하단
        hma_position = "상단" if price_now > hma_now else "하단"

        return {
            'symbol': symbol,
            'base_coin': symbol.replace("USDT", ""),
            'interval': interval,
            'interval_name': interval_name,
            'price': price_now,
            'rsi': rsi_now,
            'rsi_prev': rsi_prev,
            'hma_200': hma_now,
            'hma_position': hma_position,
            'signals': signals,
            'signal_type': signal_type,
            'datetime': latest['timestamp'],
        }

    def check_alert_cooldown(self, symbol: str, interval: str, cooldown_minutes: int = 30) -> bool:
        """알림 쿨다운 (같은 심볼·같은 봉에서 중복 방지)"""
        key = self._alert_key(symbol, interval)
        if key not in self.alert_history:
            return True
        elapsed = (datetime.now() - self.alert_history[key]).total_seconds() / 60
        return elapsed >= cooldown_minutes

    def format_telegram_alert(self, result: Dict) -> str:
        """텔레그램용 알림 메시지 (변화율 제외, RSI·HMA 200 상단/하단 포함)"""
        signal_type = result.get('signal_type', 'unknown')

        if signal_type == 'oversold':
            title = f"🔻 <b>과매도 돌파: {result['base_coin']} ({result['interval_name']})</b>"
        elif signal_type == 'overbought':
            title = f"🔺 <b>과매수 돌파: {result['base_coin']} ({result['interval_name']})</b>"
        elif signal_type == 'hma_above':
            title = f"📈 <b>HMA 200 상단 돌파: {result['base_coin']} ({result['interval_name']})</b>"
        elif signal_type == 'hma_below':
            title = f"📉 <b>HMA 200 하단 돌파: {result['base_coin']} ({result['interval_name']})</b>"
        else:
            title = f"🚨 <b>신호 감지: {result['base_coin']} ({result['interval_name']})</b>"

        lines = [
            title,
            "",
            f"⏰ 시간: <code>{result['datetime']}</code>",
            f"💰 현재가: <code>{result['price']:.2f} USDT</code>",
            "",
            f"📊 RSI: <code>{result['rsi_prev']:.1f} → {result['rsi']:.1f}</code>",
            f"📐 HMA 200 대비: <b>{result['hma_position']}</b> (HMA: <code>{result['hma_200']:.2f}</code>)",
            "",
            "<b>감지된 신호:</b>",
        ]
        for signal in result['signals']:
            lines.append(f"✓ {signal}")
        return "\n".join(lines)

    def scan(self) -> List[Dict]:
        """BTC, ETH의 5분봉·15분봉 스캔"""
        logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 스캔 시작...")

        alerts = []
        for symbol in TARGET_SYMBOLS:
            for interval, interval_name in TARGET_INTERVALS:
                try:
                    result = self.analyze_symbol_interval(symbol, interval, interval_name)
                    if result and self.check_alert_cooldown(symbol, interval):
                        alerts.append(result)
                        self.alert_history[self._alert_key(symbol, interval)] = datetime.now()

                        msg = self.format_telegram_alert(result)
                        logger.info(msg)

                        if self.telegram_notifier:
                            if self.telegram_notifier.send_message(msg):
                                logger.info("✅ 텔레그램 알림 전송 완료")
                            else:
                                logger.error("❌ 텔레그램 알림 전송 실패")

                    time.sleep(0.2)
                except Exception as e:
                    logger.warning(f"Error {symbol} {interval_name}: {e}")

        return alerts

    def run(self, single_scan: bool = False):
        """봇 실행"""
        print("=" * 60)
        print("🤖 BTC/ETH RSI·HMA 200 돌파 알림 봇")
        print("=" * 60)
        print("설정:")
        print(f"  • 대상: {', '.join(TARGET_SYMBOLS)}")
        print(f"  • 타임프레임: 5분봉, 15분봉")
        print(f"  • RSI 과매도: {self.config['rsi_oversold']} 이하 돌파")
        print(f"  • RSI 과매수: {self.config['rsi_overbought']} 이상 돌파")
        print(f"  • HMA 200: 상단/하단 돌파")
        print(f"  • 체크 주기: {self.config['check_interval']}초")
        print("=" * 60)

        if single_scan:
            results = self.scan()
            print(f"\n스캔 완료! 신호 {len(results)}건")
            return results

        while True:
            try:
                results = self.scan()
                print(f"\n스캔 완료! 신호 {len(results)}건")
                print(f"다음 스캔까지 {self.config['check_interval']}초 대기...")
                time.sleep(self.config['check_interval'])
            except KeyboardInterrupt:
                logger.info("\n봇 종료")
                break
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
                time.sleep(60)


class TelegramNotifier:
    """텔레그램 알림 클래스"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = str(chat_id).strip()
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    @staticmethod
    def get_chat_id(bot_token: str) -> Optional[str]:
        """그룹 Chat ID 자동 조회 (그룹에 봇 추가 후 메시지 보낸 뒤 실행)"""
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        try:
            response = requests.get(url, timeout=10)
            result = response.json()
            if result.get("ok") and result.get("result"):
                for update in reversed(result["result"]):
                    if "message" in update:
                        chat = update["message"]["chat"]
                        if chat.get("type") in ["group", "supergroup"]:
                            return str(chat["id"])
                    elif "my_chat_member" in update:
                        chat = update["my_chat_member"]["chat"]
                        if chat.get("type") in ["group", "supergroup"]:
                            return str(chat["id"])
        except Exception as e:
            logger.error(f"Chat ID 조회 오류: {e}")
        return None

    def test_connection(self) -> bool:
        return self.send_message("🤖 BTC/ETH RSI 알림 봇이 시작되었습니다!")

    def send_message(self, text: str) -> bool:
        url = f"{self.base_url}/sendMessage"
        data = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        try:
            response = requests.post(url, data=data, timeout=10)
            result = response.json()
            if response.status_code == 200 and result.get("ok"):
                return True
            logger.error(f"Telegram API error: {result.get('description', 'Unknown')}")
            if "parse" in str(result.get("description", "")).lower():
                data["parse_mode"] = None
                response = requests.post(url, data=data, timeout=10)
                return response.status_code == 200 and response.json().get("ok")
            return False
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False


if __name__ == "__main__":
    config = load_config_from_env()

    telegram_notifier = None
    if "telegram" in config:
        bot_token = config["telegram"]["bot_token"]
        chat_id = config["telegram"]["chat_id"]

        if not chat_id or chat_id.lower() == "auto":
            print("🔍 그룹 Chat ID 자동 검색 중...")
            found = TelegramNotifier.get_chat_id(bot_token)
            if found:
                chat_id = found
                print(f"✅ Chat ID: {chat_id}")
            else:
                print("❌ Chat ID를 찾을 수 없습니다. 그룹에 봇 추가 후 메시지를 보내세요.")
                sys.exit(1)

        telegram_notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
        if telegram_notifier.test_connection():
            logger.info("✅ 텔레그램 연결 성공!")
        else:
            logger.error("⚠️ 텔레그램 연결 실패. 토큰과 Chat ID를 확인하세요.")

    bot = RSICrossoverBot(config=config, telegram_notifier=telegram_notifier)
    single_scan = os.getenv("SINGLE_SCAN", "false").lower() == "true"

    if single_scan:
        bot.run(single_scan=True)
    else:
        bot.run()
