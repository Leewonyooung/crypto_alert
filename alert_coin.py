"""
비트코인/이더리움 RSI·HMA 200 돌파 알림 봇 (Bybit)
- 15분봉, 1시간봉, 4시간봉 기준
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


class BybitAPI:
    """바이비트 API 클래스"""

    BASE_URL = "https://api.bybit.com"

    @staticmethod
    def get_kline(symbol: str, interval: str, limit: int = 100, category: str = "linear") -> pd.DataFrame:
        """캔들 데이터 조회 (interval: 15=15분, 60=1시간, 240=4시간)"""
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

    def __init__(self, config: Dict, telegram_notifiers: Optional[Dict[str, 'TelegramNotifier']] = None):
        self.config = config
        self.telegram_notifiers = telegram_notifiers or {}
        # 캔들 하나당 알림 1회: (symbol, interval, candle_timestamp) -> 이미 알림 전송함
        self.alert_history: Dict[str, bool] = {}

    def _alert_key(self, symbol: str, interval: str, candle_datetime) -> str:
        """캔들 기준 알림 키 (동일 캔들에 대해 알림 1회만)"""
        ts = str(candle_datetime) if candle_datetime is not None else ""
        return f"{symbol}_{interval}_{ts}"

    def analyze_symbol_interval(self, symbol: str, interval: str, interval_name: str) -> Optional[Dict]:
        """
        RSI + HMA 200 돌파 감지 (종가 마감 기준)
        - 마지막 캔들(진행 중) 제외, 완전히 마감된 캔들만 사용
        - latest = 마지막 마감 캔들, prev = 그 이전 마감 캔들
        """
        category = self.config['category']
        df = BybitAPI.get_kline(symbol, interval=interval, limit=250, category=category)

        if df.empty or len(df) < 211:  # 마감 캔들 2개 + RSI/HMA 계산용
            return None

        df['rsi'] = TechnicalIndicators.calculate_rsi(
            df['close'], period=self.config['rsi_period']
        )
        df['hma_200'] = TechnicalIndicators.calculate_hma(df['close'], period=200)

        # 종가 마감 기준: 진행 중 캔들(df.iloc[-1]) 제외, 마감된 캔들만 사용
        latest = df.iloc[-2]   # 마지막 마감 캔들
        prev = df.iloc[-3]     # 그 이전 마감 캔들
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
            signals.append(f"HMA 200 상단 돌파 마감")
            if not signal_type:
                signal_type = "hma_above"

        # HMA 200 하단 돌파 (가격이 HMA 아래로 이탈)
        if price_prev >= hma_prev and price_now < hma_now:
            signals.append(f"HMA 200 하단 돌파 마감")
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

    def already_alerted_for_candle(self, symbol: str, interval: str, candle_datetime) -> bool:
        """해당 캔들에 대해 이미 알림을 보냈는지 확인 (캔들 하나당 알림 1회)"""
        key = self._alert_key(symbol, interval, candle_datetime)
        return key in self.alert_history

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
        """설정된 심볼·타임프레임 스캔"""
        logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 스캔 시작...")

        alerts = []
        for symbol in self.config["target_symbols"]:
            for interval, interval_name in self.config["target_intervals"]:
                try:
                    result = self.analyze_symbol_interval(symbol, interval, interval_name)
                    if result and not self.already_alerted_for_candle(symbol, interval, result['datetime']):
                        alerts.append(result)
                        self.alert_history[self._alert_key(symbol, interval, result['datetime'])] = True

                        msg = self.format_telegram_alert(result)
                        logger.info(msg)

                        # 봉별 해당 봇으로 전송 (15분봉→봇1, 1시간봉→봇3, 4시간봉→봇4)
                        notifier = self.telegram_notifiers.get(result["interval"])
                        if notifier:
                            if notifier.send_message(msg):
                                logger.info(f"✅ 텔레그램 알림 전송 완료 ({result['interval_name']})")
                            else:
                                logger.error(f"❌ 텔레그램 알림 전송 실패 ({result['interval_name']})")
                        else:
                            logger.warning(f"⚠️ {result['interval_name']} 봇 미연결 - 알림 전송 불가")

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
        print(f"  • 대상: {', '.join(self.config['target_symbols'])}")
        print(f"  • 타임프레임: {', '.join(n for _, n in self.config['target_intervals'])}")
        print(f"  • RSI 과매도: {self.config['rsi_oversold']} 이하 돌파")
        print(f"  • RSI 과매수: {self.config['rsi_overbought']} 이상 돌파")
        print(f"  • HMA 200: 상단/하단 돌파")
        print(f"  • 체크 주기: {self.config['check_interval']}초")
        if self.telegram_notifiers:
            print(f"  • 15분봉 알림: {'봇1' if '15' in self.telegram_notifiers else '미설정'}")
            print(f"  • 1시간봉 알림: {'봇3' if '60' in self.telegram_notifiers else '미설정'}")
            print(f"  • 4시간봉 알림: {'봇4' if '240' in self.telegram_notifiers else '미설정'}")
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

    def __init__(self, bot_token: str, chat_id: str, label: str = ""):
        self.bot_token = bot_token
        self.chat_id = str(chat_id).strip()
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.label = label or "알림"

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
        """연결 검증 (메시지 전송 없이 getChat으로 확인)"""
        url = f"{self.base_url}/getChat"
        try:
            response = requests.post(url, data={"chat_id": self.chat_id}, timeout=10)
            result = response.json()
            return response.status_code == 200 and result.get("ok")
        except Exception as e:
            logger.error(f"[{self.label}] 연결 확인 오류: {e}")
            return False

    def send_message(self, text: str) -> bool:
        url = f"{self.base_url}/sendMessage"
        data = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        try:
            response = requests.post(url, data=data, timeout=10)
            result = response.json()
            if response.status_code == 200 and result.get("ok"):
                return True
            err_desc = result.get("description", "Unknown")
            err_code = result.get("error_code", "")
            logger.error(f"[{self.label}] Telegram API 오류 [{err_code}]: {err_desc}")
            print(f"❌ [{self.label}] 전송 실패: {err_desc}")
            if "chat not found" in str(err_desc).lower() or "bot was blocked" in str(err_desc).lower():
                print(f"   → 그룹에 '{self.label}' 봇을 추가하고, 봇에게 /start 를 보내세요.")
            if "parse" in str(err_desc).lower():
                data["parse_mode"] = None
                response = requests.post(url, data=data, timeout=10)
                return response.status_code == 200 and response.json().get("ok")
            return False
        except Exception as e:
            logger.error(f"[{self.label}] Telegram error: {e}")
            print(f"❌ [{self.label}] 전송 오류: {e}")
            return False


if __name__ == "__main__":
    # ============================================================
    # 설정 (여기만 수정하세요)
    # ============================================================

    # 모니터링할 코인 (Bybit 심볼 형식)
    TARGET_SYMBOLS = ["BTCUSDT", "ETHUSDT"]

    # 분석할 타임프레임 (Bybit interval: "15"=15분, "60"=1시간, "240"=4시간)
    TARGET_INTERVALS = [
        ("15", "15분봉"),
        ("60", "1시간봉"),
        ("240", "4시간봉"),
    ]

    # 체크 주기 (초) - 15분/1시간/4시간봉 기준 60초 권장
    CHECK_INTERVAL = 60

    # RSI 설정
    RSI_PERIOD = 14
    RSI_OVERSOLD = 30   # 이 값 이하 돌파 시 과매도 알림
    RSI_OVERBOUGHT = 70  # 이 값 이상 돌파 시 과매수 알림

    # 거래소 (linear=USDT 무기한 선물, spot=현물)
    CATEGORY = "linear"

    # 텔레그램 설정 (봇 토큰은 @BotFather에서 발급)
    # Chat ID: 그룹에 봇 추가 후 /start 보내고, "auto"로 두면 자동 조회
    TELEGRAM_BOT_TOKEN = ""      # 봇1: 15분봉 알림용
    TELEGRAM_BOT_TOKEN_3 = ""    # 봇3: 1시간봉 알림용 (비워두면 비활성화)
    TELEGRAM_BOT_TOKEN_4 = ""    # 봇4: 4시간봉 알림용 (비워두면 비활성화)
    TELEGRAM_CHAT_ID = ""        # 그룹 Chat ID (예: -1001234567890) 또는 "auto"
    TELEGRAM_CHAT_ID_3 = ""      # 봇3용 별도 그룹 (비워두면 TELEGRAM_CHAT_ID 사용)
    TELEGRAM_CHAT_ID_4 = ""      # 봇4용 별도 그룹 (비워두면 TELEGRAM_CHAT_ID 사용)

    # 단일 스캔 모드 (True: 1회 스캔 후 종료, False: 반복 실행)
    SINGLE_SCAN = False

    # ============================================================
    # .env 덮어쓰기 (배포 시 .env에 설정하면 위 값을 덮어씁니다)
    # ============================================================

    if os.getenv("CHECK_INTERVAL"):
        CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL"))
    if os.getenv("RSI_PERIOD"):
        RSI_PERIOD = int(os.getenv("RSI_PERIOD"))
    if os.getenv("RSI_OVERSOLD"):
        RSI_OVERSOLD = float(os.getenv("RSI_OVERSOLD"))
    if os.getenv("RSI_OVERBOUGHT"):
        RSI_OVERBOUGHT = float(os.getenv("RSI_OVERBOUGHT"))
    if os.getenv("CATEGORY"):
        CATEGORY = os.getenv("CATEGORY")
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if os.getenv("TELEGRAM_BOT_TOKEN_3"):
        TELEGRAM_BOT_TOKEN_3 = os.getenv("TELEGRAM_BOT_TOKEN_3", "").strip()
    if os.getenv("TELEGRAM_BOT_TOKEN_4"):
        TELEGRAM_BOT_TOKEN_4 = os.getenv("TELEGRAM_BOT_TOKEN_4", "").strip()
    if os.getenv("TELEGRAM_CHAT_ID"):
        TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if os.getenv("TELEGRAM_CHAT_ID_3"):
        TELEGRAM_CHAT_ID_3 = os.getenv("TELEGRAM_CHAT_ID_3", "").strip() or TELEGRAM_CHAT_ID
    if os.getenv("TELEGRAM_CHAT_ID_4"):
        TELEGRAM_CHAT_ID_4 = os.getenv("TELEGRAM_CHAT_ID_4", "").strip() or TELEGRAM_CHAT_ID
    if os.getenv("SINGLE_SCAN"):
        SINGLE_SCAN = os.getenv("SINGLE_SCAN", "false").lower() == "true"

    # 텔레그램 설정 병합 (main 또는 .env에서)
    telegram_cfg = {}
    chat_id_3 = (TELEGRAM_CHAT_ID_3 or TELEGRAM_CHAT_ID).strip()
    chat_id_4 = (TELEGRAM_CHAT_ID_4 or TELEGRAM_CHAT_ID).strip()
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        telegram_cfg["telegram_15"] = {"bot_token": TELEGRAM_BOT_TOKEN, "chat_id": TELEGRAM_CHAT_ID}
        logger.info("✅ 텔레그램 봇1 (15분봉) 설정 완료")
    if TELEGRAM_BOT_TOKEN_3 and chat_id_3:
        telegram_cfg["telegram_60"] = {"bot_token": TELEGRAM_BOT_TOKEN_3, "chat_id": chat_id_3}
        logger.info("✅ 텔레그램 봇3 (1시간봉) 설정 완료")
    if TELEGRAM_BOT_TOKEN_4 and chat_id_4:
        telegram_cfg["telegram_240"] = {"bot_token": TELEGRAM_BOT_TOKEN_4, "chat_id": chat_id_4}
        logger.info("✅ 텔레그램 봇4 (4시간봉) 설정 완료")
    if not telegram_cfg:
        logger.warning("⚠️ 텔레그램 설정이 없습니다. 위 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID를 설정하세요.")

    # 전체 설정 병합 (main 설정 + .env 텔레그램)
    config = {
        "target_symbols": TARGET_SYMBOLS,
        "target_intervals": TARGET_INTERVALS,
        "check_interval": CHECK_INTERVAL,
        "rsi_period": RSI_PERIOD,
        "rsi_oversold": RSI_OVERSOLD,
        "rsi_overbought": RSI_OVERBOUGHT,
        "category": CATEGORY,
        **telegram_cfg,
    }

    # 텔레그램 봇 연결
    INTERVAL_LABELS = {"15": "15분봉", "60": "1시간봉", "240": "4시간봉"}
    telegram_notifiers: Dict[str, TelegramNotifier] = {}
    for key, interval in [("telegram_15", "15"), ("telegram_60", "60"), ("telegram_240", "240")]:
        if key not in config:
            continue
        cfg = config[key]
        bot_token = cfg["bot_token"]
        chat_id = cfg["chat_id"]

        if not chat_id or str(chat_id).lower() == "auto":
            label = INTERVAL_LABELS.get(interval, interval)
            print(f"🔍 {label} 봇 Chat ID 자동 검색 중...")
            found = TelegramNotifier.get_chat_id(bot_token)
            if found:
                chat_id = found
                print(f"✅ Chat ID: {chat_id}")
            else:
                print(f"❌ {label} 봇 Chat ID를 찾을 수 없습니다.")
                continue

        label = INTERVAL_LABELS.get(interval, interval)
        notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id, label=label)
        if notifier.test_connection():
            telegram_notifiers[interval] = notifier
            logger.info(f"✅ {label} 텔레그램 봇 연결 성공!")
        else:
            logger.error(f"⚠️ {label} 텔레그램 봇 연결 실패.")
            print(f"\n⚠️ {label} 봇이 그룹에 메시지를 보내지 못했습니다.")
            print(f"   해결: 1) 그룹에 봇 추가  2) 봇에게 /start 전송  3) 봇 토큰 확인\n")

    if not telegram_notifiers:
        print("⚠️ 텔레그램 알림이 비활성화됨 (봇 연결 실패). 위 오류를 확인하세요.\n")

    # 봇 실행
    bot = RSICrossoverBot(config=config, telegram_notifiers=telegram_notifiers)
    bot.run(single_scan=SINGLE_SCAN)
