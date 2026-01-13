# 🤖 알트코인 과매도 구간 알림 봇 (Bybit)

바이비트 API를 활용하여 4시간봉 기준 볼린저밴드 하단 및 RSI 과매도 구간 진입 시 알림을 제공하는 봇입니다.

## 📌 주요 기능

- **4시간봉 기준 분석**: 스윙 트레이딩에 적합한 타임프레임
- **볼린저밴드 하단 감지**: BB 하단 터치/돌파 및 근접(10% 이내) 감지
- **RSI 과매도 감지**: RSI 30 이하 과매도 구간 진입 감지
- **거래대금 필터**: 유동성이 충분한 코인만 분석 (기본 1천만 USDT 이상)
- **현물/선물 지원**: spot(현물) 또는 linear(USDT 무기한 선물) 선택 가능
- **중복 알림 방지**: 4시간 쿨다운으로 동일 코인 반복 알림 차단

## 🚀 설치 및 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# .env 파일 생성 (필수)
# .env.example 파일을 참고하여 .env 파일을 생성하고 설정값을 입력하세요
cp .env.example .env  # Linux/Mac
# 또는 Windows에서는 .env.example을 복사하여 .env로 이름 변경

# .env 파일 편집하여 필요한 값 설정
# 특히 TELEGRAM_BOT_TOKEN과 TELEGRAM_CHAT_ID는 필수입니다

# 실행
python alert_coin.py
```

## ⚙️ 환경변수 설정 (.env 파일)

모든 설정은 `.env` 파일을 통해 관리됩니다. `.env.example` 파일을 참고하여 `.env` 파일을 생성하세요.

### .env 파일 예시

프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 입력하세요:

```env
# 기본 설정
CHECK_INTERVAL=120
RSI_PERIOD=14
RSI_OVERSOLD=30
BB_PERIOD=20
BB_STD=2
MIN_VOLUME_USDT=1000000
CATEGORY=linear
EXCLUDE_COINS=USDC,USDT,DAI,TUSD

# 텔레그램 설정 (필수)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# 실행 모드 (선택)
SINGLE_SCAN=false
```

**중요**: `.env` 파일은 Git에 커밋하지 마세요! `.gitignore`에 추가되어 있습니다.

### 환경변수 목록

| 환경변수 | 기본값 | 설명 |
|---------|--------|------|
| `CHECK_INTERVAL` | 120 | 체크 주기 (초) |
| `RSI_PERIOD` | 14 | RSI 기간 |
| `RSI_OVERSOLD` | 30 | RSI 과매도 기준 |
| `BB_PERIOD` | 20 | 볼린저밴드 기간 |
| `BB_STD` | 2 | 볼린저밴드 표준편차 |
| `MIN_VOLUME_USDT` | 1000000 | 최소 24시간 거래대금 (USDT) |
| `CATEGORY` | linear | spot(현물) 또는 linear(USDT 무기한 선물) |
| `EXCLUDE_COINS` | USDC,USDT,DAI,TUSD | 제외할 코인 (쉼표로 구분) |
| `TELEGRAM_BOT_TOKEN` | - | 텔레그램 봇 토큰 (선택) |
| `TELEGRAM_CHAT_ID` | - | 텔레그램 채팅 ID (선택) |
| `SINGLE_SCAN` | false | true로 설정 시 1회 스캔 후 종료 |

## 📊 알림 예시

```
==================================================
🚨 과매도 신호 감지: XRP
==================================================
⏰ 시간: 2024-01-15 12:00:00
💰 현재가: 0.5234 USDT
📊 변화율: -3.45%

📈 기술적 지표:
   • RSI(14): 28.5
   • BB 위치: 5.2%
   • BB 하단: 0.5100
   • BB 중심: 0.5500
   • BB 상단: 0.5900

🎯 감지된 신호:
   ✓ RSI 과매도 (28.5)
   ✓ BB 하단 근접 (위치: 5.2%)
==================================================
```

## 📱 텔레그램 알림 연동

텔레그램으로 알림을 받으려면 `.env` 파일에 다음을 설정하세요:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### Chat ID 확인 방법

**개인 채팅:**
1. @userinfobot에게 메시지 전송
2. 반환된 ID 사용

**그룹 채팅:**
1. 그룹에 봇 추가
2. 그룹에서 봇에게 메시지 전송 (예: `/start`)
3. 브라우저에서 다음 URL 접속:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. JSON 응답에서 `"chat":{"id": -숫자}` 부분의 숫자 복사
5. `.env` 파일의 `TELEGRAM_CHAT_ID`에 설정

그룹 Chat ID는 보통 음수입니다 (예: `-1003642012390`).

## ⚠️ 주의사항

- **투자 조언이 아닙니다**: 이 봇은 기술적 지표를 기반으로 한 알림 도구일 뿐, 매수/매도 결정은 본인 판단에 따라야 합니다.
- **API 제한**: Bybit API는 초당 요청 수 제한이 있으므로, 코드에 적절한 딜레이가 포함되어 있습니다.
- **과매도 ≠ 반등**: 과매도 구간 진입이 반드시 가격 반등을 의미하지 않습니다. 추가 하락 가능성도 항상 존재합니다.

## 🔧 확장 아이디어

- Discord/Slack 웹훅 연동
- 데이터베이스 저장 (SQLite, MongoDB)
- 웹 대시보드 추가
- 바이낸스 등 해외 거래소 지원
- 추가 지표 (MACD, 스토캐스틱 등)