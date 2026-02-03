# 텔레그램 봇 생성 및 그룹(방) 메시지 전송 가이드

## 1. 새 텔레그램 봇 생성하기

### 1단계: BotFather에게 연락
1. 텔레그램 앱을 열고 검색창에 **@BotFather** 입력
2. @BotFather 대화를 시작
3. `/newbot` 명령어 전송

### 2단계: 봇 이름 설정
1. **봇 이름** 입력 (예: `My RSI Alert Bot`) - 사람에게 보이는 이름
2. **봇 사용자명** 입력 (예: `my_rsi_alert_bot`) - 반드시 `bot`으로 끝나야 함

### 3단계: 토큰 받기
- BotFather가 **API Token**을 발급해 줍니다.
- 형식: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`
- 이 토큰을 `.env` 파일의 `TELEGRAM_BOT_TOKEN`에 저장하세요.

```
TELEGRAM_BOT_TOKEN=여기에_발급받은_토큰_붙여넣기
```

---

## 2. 그룹(방)에 봇 추가하고 Chat ID 얻기

### 1단계: 그룹 생성 또는 기존 그룹 사용
- 새 그룹을 만들거나, 알림을 받을 기존 그룹을 선택합니다.

### 2단계: 봇을 그룹에 추가
1. 그룹 채팅 화면에서 **멤버 추가** (또는 상단 그룹 이름 탭)
2. 방금 만든 봇의 사용자명 검색 (예: `@my_rsi_alert_bot`)
3. 봇을 그룹에 추가

### 3단계: 그룹에서 봇에게 메시지 보내기
- 그룹 채팅에서 봇에게 `/start` 또는 아무 메시지나 보냅니다.
- 이 단계가 있어야 봇이 그룹의 Chat ID를 알 수 있습니다.

### 4단계: Chat ID 확인하기

**방법 A: 자동 조회 (권장)**  
`.env`에 `TELEGRAM_CHAT_ID=auto`로 설정한 뒤 봇을 실행하면, 코드가 자동으로 Chat ID를 찾아줍니다.

```
TELEGRAM_CHAT_ID=auto
```

**방법 B: 수동 조회**
1. 브라우저에서 아래 URL 접속 (토큰 부분을 본인 토큰으로 교체):
   ```
   https://api.telegram.org/bot<여기에_봇_토큰>/getUpdates
   ```
2. JSON 응답에서 `"chat":{"id":-1001234567890,...}` 형태의 `id` 값을 찾습니다.
3. 그룹 Chat ID는 보통 **음수**입니다 (예: `-1003642012390`).
4. 이 값을 `.env`의 `TELEGRAM_CHAT_ID`에 저장합니다.

```
TELEGRAM_CHAT_ID=-1003642012390
```

---

## 3. .env 설정 예시

```env
# 체크 주기 (초) - 5분봉/15분봉이므로 60초 권장
CHECK_INTERVAL=60

# RSI 설정
RSI_PERIOD=14
RSI_OVERSOLD=30
RSI_OVERBOUGHT=70

# 거래소 (linear = USDT 무기한 선물)
CATEGORY=linear

# 텔레그램 (필수)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=-1001234567890

# 단일 스캔만 실행 (true/false)
SINGLE_SCAN=false
```

---

## 4. 봇 실행 및 테스트

```bash
python alert_coin.py
```

- 시작 시 "🤖 BTC/ETH RSI 알림 봇이 시작되었습니다!" 메시지가 그룹에 오면 설정이 정상입니다.
- BTC 또는 ETH의 5분봉/15분봉에서 RSI가 30 이하 또는 70 이상으로 돌파할 때마다 그룹으로 알림이 전송됩니다.

---

## 5. 자주 묻는 질문

**Q: "chat not found" 오류가 나요**  
- 봇이 그룹에 추가되었는지 확인하세요.  
- 그룹에서 봇에게 `/start` 또는 메시지를 한 번 보냈는지 확인하세요.  
- Chat ID가 음수인지, 숫자만 들어갔는지 확인하세요.

**Q: 개인 채팅으로 보내고 싶어요**  
- 봇에게 `/start`를 보낸 뒤, `getUpdates` URL로 접속해 `"chat":{"id":123456789}` 형태의 `id`를 확인합니다.  
- 개인 Chat ID는 양수입니다.

**Q: 여러 그룹에 보내고 싶어요**  
- 현재 코드는 하나의 Chat ID만 지원합니다.  
- 여러 그룹에 보내려면 `TELEGRAM_CHAT_ID`에 여러 ID를 쉼표로 구분해 넣고, 코드에서 split 후 반복 전송하도록 수정해야 합니다.
