# 🤖 비트코인/이더리움 RSI·HMA 200 돌파 알림 봇 (Bybit)

바이비트 API를 활용하여 BTC, ETH의 5분봉·15분봉 기준 RSI 과매도/과매수 및 HMA 200 돌파 신호를 텔레그램으로 알림하는 봇입니다.

## 📌 주요 기능

- **5분봉·15분봉 기준 분석**: 단기/중기 트레이딩에 적합한 타임프레임
- **RSI 30 이하 돌파**: 과매도 구간 진입 알림
- **RSI 70 이상 돌파**: 과매수 구간 진입 알림
- **HMA 200 상단 돌파**: 가격이 HMA 200 위로 돌파 시 추세 전환 알림
- **HMA 200 하단 돌파**: 가격이 HMA 200 아래로 이탈 시 추세 전환 알림
- **5분봉/15분봉 분리 알림**: 각 타임프레임별로 다른 텔레그램 봇으로 전송 가능
- **중복 알림 방지**: 신호 타입별 15분 쿨다운으로 반복 알림 차단

## 🚀 설치 및 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# .env 파일 생성 후 설정값 입력
# TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID는 필수입니다

# 실행
python alert_coin.py
```

## ⚙️ 설정 방법

모든 설정은 `alert_coin.py`의 `main()` 함수 상단 **설정 섹션**에서 변경할 수 있습니다. 코딩 지식 없이 값만 수정하면 됩니다.

### 설정 섹션 위치

`alert_coin.py` 파일을 열고 `if __name__ == "__main__":` 아래의 **설정 (여기만 수정하세요)** 블록을 찾아 수정하세요.

> **배포 시**: CloudType 등에서 `.env`에 `CHECK_INTERVAL`, `RSI_OVERSOLD` 등을 설정하면 main() 기본값을 덮어씁니다.

### 설정 항목

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `TARGET_SYMBOLS` | `["BTCUSDT", "ETHUSDT"]` | 모니터링할 코인 (Bybit 심볼 형식) |
| `TARGET_INTERVALS` | 5분봉, 15분봉 | 분석할 타임프레임 |
| `CHECK_INTERVAL` | 60 | 체크 주기 (초) |
| `RSI_PERIOD` | 14 | RSI 기간 |
| `RSI_OVERSOLD` | 30 | RSI 과매도 기준 (이하 돌파 시 알림) |
| `RSI_OVERBOUGHT` | 70 | RSI 과매수 기준 (이상 돌파 시 알림) |
| `CATEGORY` | linear | spot(현물) 또는 linear(USDT 무기한 선물) |
| `ALERT_COOLDOWN_MINUTES` | 15 | 동일 신호 재알림 쿨다운 (분) |
| `TELEGRAM_BOT_TOKEN` | - | 15분봉 알림용 봇 토큰 |
| `TELEGRAM_BOT_TOKEN_2` | - | 5분봉 알림용 봇 토큰 (선택) |
| `TELEGRAM_CHAT_ID` | - | 그룹 Chat ID 또는 "auto" |
| `TELEGRAM_CHAT_ID_2` | - | 봇2용 별도 그룹 (선택) |
| `SINGLE_SCAN` | False | True: 1회 스캔 후 종료 |

### 텔레그램 설정

**방법 1: main()에서 직접 설정 (권장)**  
`alert_coin.py`의 설정 블록에서 다음 값을 채우세요:

```python
TELEGRAM_BOT_TOKEN = "1234567890:ABCdef..."   # 봇1: 15분봉
TELEGRAM_BOT_TOKEN_2 = ""                     # 봇2: 5분봉 (비워두면 비활성화)
TELEGRAM_CHAT_ID = "-1001234567890"           # 또는 "auto" (자동 조회)
TELEGRAM_CHAT_ID_2 = ""                       # 봇2용 별도 그룹
```

**방법 2: .env 파일 사용 (배포 시)**  
`.env`에 설정하면 main() 값을 덮어씁니다. 토큰을 Git에 올리지 않으려면 .env를 사용하세요.

**중요**: 토큰이 포함된 파일은 Git에 커밋하지 마세요!

## 📊 알림 예시

```
🔻 과매도 돌파: BTC (5분봉)

⏰ 시간: 2024-01-15 12:00:00
💰 현재가: 43250.00 USDT

📊 RSI: 32.5 → 28.3
📐 HMA 200 대비: 하단 (HMA: 43500.00)

감지된 신호:
✓ RSI 30 이하 돌파 (과매도) - 32.5 → 28.3
```

## 📱 텔레그램 설정 가이드

자세한 텔레그램 봇 생성 및 Chat ID 확인 방법은 [TELEGRAM_SETUP.md](TELEGRAM_SETUP.md)를 참고하세요.

## ⚠️ 주의사항

- **투자 조언이 아닙니다**: 이 봇은 기술적 지표 기반 알림 도구일 뿐, 매수/매도 결정은 본인 판단에 따라야 합니다.
- **API 제한**: Bybit API는 요청 수 제한이 있으므로 체크 주기를 적절히 설정하세요.
- **과매도 ≠ 반등**: 과매도 구간 진입이 반드시 가격 반등을 의미하지 않습니다.

## 📂 관련 문서

- [TELEGRAM_SETUP.md](TELEGRAM_SETUP.md) - 텔레그램 봇 생성 및 설정
- [DEPLOY.md](DEPLOY.md) - CloudType 배포 가이드
