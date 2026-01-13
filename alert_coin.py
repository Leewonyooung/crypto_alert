"""
알트코인 과매도/과매수 구간 알림 봇 (Bybit 버전)
- 4시간봉 기준
- 볼린저밴드 하단/상단 터치/돌파 감지
- RSI 30 이하 과매도 구간 감지
- RSI 70 이상 과매수 구간 감지
"""

import requests
import pandas as pd
import numpy as np
import time
import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import json
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드 (로컬 환경에서만)
# CloudType에서는 환경변수를 직접 사용하므로 .env 파일이 없어도 됨
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # CloudType에서 로그 확인용
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# 환경변수에서 설정값 로드
# ============================================
def load_config_from_env() -> Dict:
    """환경변수에서 설정값을 로드합니다 (.env 파일 사용)."""
    # 필수 환경변수 확인
    required_vars = [
        "CHECK_INTERVAL", "RSI_PERIOD", "RSI_OVERSOLD", "RSI_OVERBOUGHT",
        "MIN_VOLUME_USDT", "CATEGORY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print("❌ 필수 환경변수가 설정되지 않았습니다:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n.env 파일을 생성하고 필요한 환경변수를 설정하세요.")
        print("예시는 .env.example 파일을 참고하세요.")
        sys.exit(1)
    
    config = {
        "check_interval": int(os.getenv("CHECK_INTERVAL")),
        "rsi_period": int(os.getenv("RSI_PERIOD")),
        "rsi_oversold": float(os.getenv("RSI_OVERSOLD")),
        "rsi_overbought": float(os.getenv("RSI_OVERBOUGHT")),
        "min_volume_usdt": float(os.getenv("MIN_VOLUME_USDT")),
        "category": os.getenv("CATEGORY"),  # spot 또는 linear
        "exclude_coins": os.getenv("EXCLUDE_COINS", "USDC,USDT,DAI,TUSD").split(","),
    }
    
    # 텔레그램 설정
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
        if not telegram_bot_token:
            logger.warning("   TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
        if not telegram_chat_id:
            logger.warning("   TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
    
    return config

# 기본 설정값 (환경변수가 없을 경우 사용)
CONFIG = {
    "check_interval": 120,          # 체크 주기 (초) - 2분마다
    "rsi_period": 14,               # RSI 기간
    "rsi_oversold": 30,             # RSI 과매도 기준
    "bb_period": 20,                # 볼린저밴드 기간
    "bb_std": 2,                    # 볼린저밴드 표준편차
    "min_volume_usdt": 1_000_000,  # 최소 24시간 거래대금 (1천만 USDT)
    "category": "linear",             # spot(현물) 또는 linear(USDT 무기한 선물)
    "exclude_coins": ["USDC", "USDT", "DAI", "TUSD"],  # 제외할 코인 (스테이블코인)
}


class BybitAPI:
    """바이비트 API 클래스"""
    
    BASE_URL = "https://api.bybit.com"
    
    @staticmethod
    def get_instruments(category: str = "spot") -> List[Dict]:
        """
        거래 가능한 심볼 목록 조회
        category: spot(현물), linear(USDT 무기한), inverse(코인 무기한)
        """
        url = f"{BybitAPI.BASE_URL}/v5/market/instruments-info"
        params = {"category": category}
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get("retCode") != 0:
            print(f"Error: {data.get('retMsg')}")
            return []
        
        instruments = data.get("result", {}).get("list", [])
        
        # USDT 마켓만 필터링
        usdt_instruments = [
            inst for inst in instruments 
            if inst.get("quoteCoin") == "USDT" or inst.get("symbol", "").endswith("USDT")
        ]
        
        return usdt_instruments
    
    @staticmethod
    def get_kline(symbol: str, interval: str = "240", limit: int = 200, category: str = "spot") -> pd.DataFrame:
        """
        캔들(K-line) 데이터 조회
        interval: 1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M
        """
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
            print(f"Error fetching {symbol}: {data.get('retMsg')}")
            return pd.DataFrame()
        
        klines = data.get("result", {}).get("list", [])
        
        if not klines:
            return pd.DataFrame()
        
        # 바이비트 kline 형식: [startTime, open, high, low, close, volume, turnover]
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'
        ])
        
        # 데이터 타입 변환
        df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 시간순 정렬 (최신 -> 과거 순으로 오므로 역순)
        df = df.iloc[::-1].reset_index(drop=True)
        
        return df
    
    @staticmethod
    def get_tickers(category: str = "spot") -> List[Dict]:
        """전체 심볼 현재가 및 거래량 조회"""
        url = f"{BybitAPI.BASE_URL}/v5/market/tickers"
        params = {"category": category}
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get("retCode") != 0:
            print(f"Error: {data.get('retMsg')}")
            return []
        
        return data.get("result", {}).get("list", [])


class TechnicalIndicators:
    """기술적 지표 계산 클래스"""
    
    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI 계산"""
        delta = prices.diff()
        
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        
        avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """볼린저밴드 계산 (상단, 중심, 하단)"""
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return upper, middle, lower
    
    @staticmethod
    def calculate_bb_position(price: float, lower: float, upper: float) -> float:
        """볼린저밴드 내 위치 (0~100, 0=하단, 100=상단)"""
        if upper == lower:
            return 50
        return ((price - lower) / (upper - lower)) * 100


class OversoldAlertBot:
    """과매도 구간 알림 봇"""
    
    def __init__(self, config: Dict = None, telegram_notifier: Optional['TelegramNotifier'] = None):
        self.config = config or CONFIG
        self.alert_history = {}  # 알림 중복 방지용
        self.telegram_notifier = telegram_notifier
        
    def get_active_symbols(self) -> List[str]:
        """활성 심볼 목록 조회 (거래대금 필터 적용)"""
        category = self.config['category']
        
        # 티커 정보 조회
        tickers = BybitAPI.get_tickers(category)
        
        active_symbols = []
        
        for ticker in tickers:
            symbol = ticker.get("symbol", "")
            
            # USDT 마켓만
            if not symbol.endswith("USDT"):
                continue
            
            # 스테이블코인 제외
            base_coin = symbol.replace("USDT", "")
            if base_coin in self.config['exclude_coins']:
                continue
            
            # 거래대금 필터 (24시간 거래대금)
            turnover_24h = float(ticker.get("turnover24h", 0))
            if turnover_24h >= self.config['min_volume_usdt']:
                active_symbols.append(symbol)
        
        return active_symbols
    
    def analyze_coin(self, symbol: str) -> Dict:
        """개별 코인 분석 (RSI만 신호 판단, 볼린저밴드는 참고용)"""
        category = self.config['category']
        
        # 4시간봉 데이터 조회 (interval=240)
        df = BybitAPI.get_kline(symbol, interval="240", limit=100, category=category)
        
        if df.empty or len(df) < self.config['rsi_period']:
            return None
        
        # RSI 계산
        df['rsi'] = TechnicalIndicators.calculate_rsi(
            df['close'], 
            period=self.config['rsi_period']
        )
        
        # 볼린저밴드 계산 (메시지 표시용, 신호 판단에는 사용 안 함)
        bb_period = 20  # 기본값
        bb_std = 2  # 기본값
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = TechnicalIndicators.calculate_bollinger_bands(
            df['close'],
            period=bb_period,
            std_dev=bb_std
        )
        
        # 최신 데이터
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # 볼린저밴드 위치 계산 (메시지 표시용)
        bb_position = TechnicalIndicators.calculate_bb_position(
            latest['close'], 
            latest['bb_lower'], 
            latest['bb_upper']
        )
        
        # 신호 판단 (RSI만 사용)
        signals = []
        signal_type = None  # "oversold" 또는 "overbought"
        
        # RSI 과매도
        if latest['rsi'] <= self.config['rsi_oversold']:
            signals.append(f"RSI 과매도 ({latest['rsi']:.1f})")
            signal_type = "oversold"
        
        # RSI 과매수
        if latest['rsi'] >= self.config['rsi_overbought']:
            signals.append(f"RSI 과매수 ({latest['rsi']:.1f})")
            signal_type = "overbought"
        
        if not signals:
            return None
        
        return {
            'symbol': symbol,
            'base_coin': symbol.replace("USDT", ""),
            'price': latest['close'],
            'rsi': latest['rsi'],
            'bb_lower': latest['bb_lower'],
            'bb_middle': latest['bb_middle'],
            'bb_upper': latest['bb_upper'],
            'bb_position': bb_position,
            'signals': signals,
            'signal_type': signal_type,  # "oversold" 또는 "overbought"
            'datetime': latest['timestamp'],
            'change_rate': ((latest['close'] - prev['close']) / prev['close']) * 100 if prev['close'] > 0 else 0
        }
    
    def check_alert_cooldown(self, symbol: str, cooldown_hours: int = 4) -> bool:
        """알림 쿨다운 체크 (중복 알림 방지)"""
        if symbol not in self.alert_history:
            return True
        
        last_alert = self.alert_history[symbol]
        elapsed = (datetime.now() - last_alert).total_seconds() / 3600
        
        return elapsed >= cooldown_hours
    
    def format_alert(self, result: Dict) -> str:
        """알림 메시지 포맷 (콘솔용)"""
        signal_type = result.get('signal_type', 'unknown')
        if signal_type == 'oversold':
            title = f"🔻 과매도 신호 감지: {result['base_coin']}"
        elif signal_type == 'overbought':
            title = f"🔺 과매수 신호 감지: {result['base_coin']}"
        else:
            title = f"🚨 신호 감지: {result['base_coin']}"
        
        lines = [
            "=" * 50,
            title,
            "=" * 50,
            f"⏰ 시간: {result['datetime']}",
            f"💰 현재가: {result['price']:.4f} USDT",
            f"📊 변화율: {result['change_rate']:+.2f}%",
            "",
            "📈 기술적 지표:",
            f"   • RSI(14): {result['rsi']:.1f}",
            f"   • BB 위치: {result['bb_position']:.1f}%",
            f"   • BB 하단: {result['bb_lower']:.4f}",
            f"   • BB 중심: {result['bb_middle']:.4f}",
            f"   • BB 상단: {result['bb_upper']:.4f}",
            "",
            "🎯 감지된 신호:",
        ]
        
        for signal in result['signals']:
            lines.append(f"   ✓ {signal}")
        
        lines.append("=" * 50)
        
        return "\n".join(lines)
    
    def format_telegram_alert(self, result: Dict) -> str:
        """텔레그램용 알림 메시지 포맷 (HTML 형식)"""
        signal_type = result.get('signal_type', 'unknown')
        change_emoji = "📈" if result['change_rate'] >= 0 else "📉"
        
        if signal_type == 'oversold':
            title = f"🔻 <b>과매도 신호 감지: {result['base_coin']}</b>"
        elif signal_type == 'overbought':
            title = f"🔺 <b>과매수 신호 감지: {result['base_coin']}</b>"
        else:
            title = f"🚨 <b>신호 감지: {result['base_coin']}</b>"
        
        lines = [
            title,
            "",
            f"⏰ 시간: <code>{result['datetime']}</code>",
            f"💰 현재가: <code>{result['price']:.4f} USDT</code>",
            f"{change_emoji} 변화율: <code>{result['change_rate']:+.2f}%</code>",
            "",
            "<b>기술적 지표:</b>",
            f"• RSI(14): <code>{result['rsi']:.1f}</code>",
            f"• BB 위치: <code>{result['bb_position']:.1f}%</code>",
            f"• BB 하단: <code>{result['bb_lower']:.4f}</code>",
            f"• BB 중심: <code>{result['bb_middle']:.4f}</code>",
            f"• BB 상단: <code>{result['bb_upper']:.4f}</code>",
            "",
            "<b>감지된 신호:</b>",
        ]
        
        for signal in result['signals']:
            lines.append(f"✓ {signal}")
        
        return "\n".join(lines)
    
    def scan_all_symbols(self) -> List[Dict]:
        """전체 심볼 스캔"""
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 마켓 스캔 시작...")
        
        symbols = self.get_active_symbols()
        print(f"활성 심볼 수: {len(symbols)}개")
        
        alert_coins = []
        
        for i, symbol in enumerate(symbols):
            try:
                result = self.analyze_coin(symbol)
                
                if result and self.check_alert_cooldown(symbol):
                    alert_coins.append(result)
                    self.alert_history[symbol] = datetime.now()
                    
                    # 알림 출력
                    alert_message = self.format_alert(result)
                    print(alert_message)
                    
                    # 텔레그램 알림 전송 (설정된 경우)
                    if self.telegram_notifier:
                        telegram_message = self.format_telegram_alert(result)
                        success = self.telegram_notifier.send_message(telegram_message)
                        if success:
                            print("✅ 텔레그램 알림 전송 완료")
                        else:
                            print("❌ 텔레그램 알림 전송 실패")
                
                # 진행률 표시 (10개마다)
                if (i + 1) % 10 == 0:
                    print(f"진행: {i+1}/{len(symbols)}")
                
                time.sleep(0.1)  # API 제한 방지
                
            except Exception as e:
                logger.warning(f"Error analyzing {symbol}: {e}")
                continue
        
        return alert_coins
    
    def run(self, single_scan: bool = False):
        """봇 실행"""
        category_name = "현물" if self.config['category'] == "spot" else "USDT 무기한 선물"
        
        print("=" * 60)
        print("🤖 알트코인 과매도/과매수 구간 알림 봇 (Bybit)")
        print("=" * 60)
        print(f"설정:")
        print(f"  • 거래소: Bybit ({category_name})")
        print(f"  • 타임프레임: 4시간봉")
        print(f"  • RSI 과매도 기준: {self.config['rsi_oversold']} 이하")
        print(f"  • RSI 과매수 기준: {self.config['rsi_overbought']} 이상")
        print(f"  • 최소 거래대금: {self.config['min_volume_usdt']/1e6:.0f}M USDT")
        print(f"  • 체크 주기: {self.config['check_interval']}초")
        print("=" * 60)
        
        if single_scan:
            # 1회 스캔
            results = self.scan_all_symbols()
            print(f"\n스캔 완료! 신호 감지 코인 {len(results)}개")
            return results
        
        # 연속 실행
        while True:
            try:
                results = self.scan_all_symbols()
                print(f"\n스캔 완료! 신호 감지 코인 {len(results)}개")
                print(f"다음 스캔까지 {self.config['check_interval']}초 대기...")
                time.sleep(self.config['check_interval'])
                
            except KeyboardInterrupt:
                logger.info("\n봇 종료")
                break
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
                time.sleep(60)


class TelegramNotifier:
    """텔레그램 알림 클래스 (선택적)"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    @staticmethod
    def get_chat_id(bot_token: str) -> Optional[str]:
        """
        텔레그램 봇의 최근 업데이트에서 Chat ID를 가져옵니다.
        그룹에 봇을 추가한 후, 그룹에서 봇에게 메시지를 보내면 Chat ID를 확인할 수 있습니다.
        """
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        try:
            response = requests.get(url, timeout=10)
            result = response.json()
            
            if result.get("ok") and result.get("result"):
                updates = result["result"]
                if updates:
                    # 그룹/슈퍼그룹 Chat ID 우선 검색
                    for update in reversed(updates):  # 최신부터 검색
                        if "message" in update:
                            chat = update["message"]["chat"]
                            chat_type = chat.get("type", "")
                            # 그룹 또는 슈퍼그룹만 반환
                            if chat_type in ["group", "supergroup"]:
                                chat_id = str(chat["id"])
                                chat_title = chat.get("title", "Unknown")
                                print(f"📱 발견된 그룹:")
                                print(f"   이름: {chat_title}")
                                print(f"   타입: {chat_type}")
                                print(f"   Chat ID: {chat_id}")
                                return chat_id
                        # my_chat_member 업데이트도 확인 (봇이 그룹에 추가될 때)
                        elif "my_chat_member" in update:
                            chat = update["my_chat_member"]["chat"]
                            chat_type = chat.get("type", "")
                            if chat_type in ["group", "supergroup"]:
                                chat_id = str(chat["id"])
                                chat_title = chat.get("title", "Unknown")
                                print(f"📱 발견된 그룹:")
                                print(f"   이름: {chat_title}")
                                print(f"   타입: {chat_type}")
                                print(f"   Chat ID: {chat_id}")
                                return chat_id
            return None
        except Exception as e:
            print(f"❌ Chat ID 조회 오류: {e}")
            return None
    
    def test_connection(self) -> bool:
        """텔레그램 연결 테스트"""
        test_message = "🤖 알트코인 과매도 알림 봇이 시작되었습니다!"
        return self.send_message(test_message)
    
    def send_message(self, text: str) -> bool:
        """메시지 전송"""
        url = f"{self.base_url}/sendMessage"
        
        # Chat ID를 문자열로 변환 (숫자여도 문자열로 전송 가능)
        chat_id = str(self.chat_id).strip()
        
        # 디버깅: Chat ID 로깅 (민감 정보이므로 마스킹)
        logger.debug(f"텔레그램 메시지 전송 시도 (Chat ID: {chat_id[:5]}...)")
        
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"  # HTML 형식 사용
        }
        
        try:
            response = requests.post(url, data=data, timeout=10)
            result = response.json()
            
            if response.status_code == 200 and result.get("ok"):
                logger.info("✅ 텔레그램 메시지 전송 성공")
                return True
            else:
                error_msg = result.get('description', 'Unknown error')
                error_code = result.get('error_code', 'N/A')
                logger.error(f"❌ Telegram API error [{error_code}]: {error_msg}")
                logger.error(f"   Chat ID: {chat_id}")
                
                # "chat not found" 에러인 경우 상세 정보 제공
                if "chat not found" in error_msg.lower() or error_code == 400:
                    logger.error("   가능한 원인:")
                    logger.error("   1. 봇이 그룹에 추가되지 않았습니다")
                    logger.error("   2. Chat ID가 잘못되었습니다")
                    logger.error("   3. 그룹이 삭제되었거나 봇이 제거되었습니다")
                    logger.error("   해결 방법:")
                    logger.error("   1. 그룹에 봇을 추가하세요")
                    logger.error("   2. 그룹에서 봇에게 메시지를 보내세요 (예: /start)")
                    logger.error("   3. 환경변수 TELEGRAM_CHAT_ID를 확인하세요")
                
                # HTML 파싱 오류인 경우 일반 텍스트로 재시도
                if "parse" in error_msg.lower() or "html" in error_msg.lower():
                    logger.info("   일반 텍스트로 재시도 중...")
                    data["parse_mode"] = None
                    response = requests.post(url, data=data, timeout=10)
                    result = response.json()
                    if response.status_code == 200 and result.get("ok"):
                        logger.info("✅ 텔레그램 메시지 전송 성공 (일반 텍스트)")
                        return True
                return False
        except requests.exceptions.Timeout:
            logger.error("❌ Telegram error: 요청 시간 초과")
            return False
        except Exception as e:
            logger.error(f"❌ Telegram error: {e}", exc_info=True)
            return False


if __name__ == "__main__":
    # 환경변수에서 설정 로드
    config = load_config_from_env()
    
    # 텔레그램 알림 설정
    telegram_notifier = None
    if "telegram" in config:
        bot_token = config["telegram"]["bot_token"]
        chat_id = config["telegram"]["chat_id"]
        
        # Chat ID가 없거나 "auto"인 경우 자동으로 찾기 시도
        if not chat_id or chat_id.lower() == "auto":
            print("🔍 그룹 Chat ID 자동 검색 중...")
            print("   (그룹에 봇을 추가하고 그룹에서 봇에게 메시지를 보낸 후 실행하세요)")
            found_chat_id = TelegramNotifier.get_chat_id(bot_token)
            if found_chat_id:
                chat_id = found_chat_id
                print(f"✅ Chat ID 자동 설정: {chat_id}")
            else:
                print("⚠️ Chat ID를 자동으로 찾을 수 없습니다.")
                print("   수동으로 설정하려면:")
                print("   1. 그룹에 봇을 추가")
                print("   2. 그룹에서 봇에게 메시지 전송 (예: /start)")
                print("   3. 브라우저에서 다음 URL 접속:")
                print(f"      https://api.telegram.org/bot{bot_token}/getUpdates")
                print("   4. 'chat':{'id': -숫자} 부분의 숫자를 복사")
                print("   5. 환경변수 TELEGRAM_CHAT_ID에 설정")
                sys.exit(1)
        
        # Chat ID 검증 (공백 제거)
        chat_id = str(chat_id).strip()
        
        # Chat ID가 숫자 또는 음수인지 확인
        try:
            # 숫자로 변환 가능한지 확인 (음수 포함)
            test_id = int(chat_id)
            logger.info(f"Chat ID 검증 완료: {test_id}")
        except ValueError:
            logger.warning(f"⚠️ Chat ID가 숫자 형식이 아닙니다: {chat_id}")
            logger.warning("   Chat ID는 숫자여야 합니다 (예: -1001234567890)")
        
        telegram_notifier = TelegramNotifier(
            bot_token=bot_token,
            chat_id=chat_id
        )
        logger.info("✅ 텔레그램 알림이 활성화되었습니다.")
        # 연결 테스트
        logger.info("📡 텔레그램 연결 테스트 중...")
        if telegram_notifier.test_connection():
            logger.info("✅ 텔레그램 연결 성공! 테스트 메시지를 확인하세요.")
        else:
            logger.error("⚠️ 텔레그램 연결 실패. 봇 토큰과 Chat ID를 확인하세요.")
            logger.error("   그룹 Chat ID는 보통 음수입니다 (예: -1001234567890)")
            logger.error("   CloudType 환경변수에서 TELEGRAM_CHAT_ID를 확인하세요.")
    
    # 봇 인스턴스 생성
    bot = OversoldAlertBot(config=config, telegram_notifier=telegram_notifier)
    
    # 단일 스캔 모드 (환경변수 SINGLE_SCAN=true인 경우)
    single_scan = os.getenv("SINGLE_SCAN", "false").lower() == "true"
    
    if single_scan:
        print("🔍 단일 스캔 모드로 실행합니다...")
        results = bot.run(single_scan=True)
    else:
        # 연속 실행
        bot.run()