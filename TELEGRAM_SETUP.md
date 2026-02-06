# 텔레그램 봇 생성 및 그룹(방) 메시지 전송 가이드

비트코인/이더리움 RSI·HMA 200 돌파 알림 봇에서 사용하는 텔레그램 설정 방법입니다.

---

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

### 5분봉/15분봉 분리 알림 시
- **봇1** (15분봉): `TELEGRAM_BOT_TOKEN`
- **봇2** (5분봉): `TELEGRAM_BOT_TOKEN_2` (별도 봇 생성 후 토큰 입력)

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

**방법 B: get_chat_id.py 스크립트 사용**
```bash
python get_chat_id.py
```
- 그룹에서 봇에게 `/start` 보낸 후 실행
- 출력된 Chat ID를 `.env`에 복사

**방법 C: 수동 조회**
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

## 3. 설정 방법 (둘 중 하나 선택)

### 방법 A: alert_coin.py에서 직접 설정 (한 곳에서 모두 설정)

`alert_coin.py`를 열고 `if __name__ == "__main__":` 아래 설정 블록에서 다음을 채우세요:

```python
TELEGRAM_BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"   # 봇1: 15분봉
TELEGRAM_BOT_TOKEN_2 = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz2"  # 봇2: 5분봉 (선택)
TELEGRAM_CHAT_ID = "-1001234567890"   # 또는 "auto" (자동 조회)
TELEGRAM_CHAT_ID_2 = ""               # 봇2용 별도 그룹 (비워두면 TELEGRAM_CHAT_ID 사용)
SINGLE_SCAN = False                   # True: 1회 스캔 후 종료
```

### 방법 B: .env 파일 사용 (배포 시 권장 - 토큰을 Git에 올리지 않음)

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_BOT_TOKEN_2=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz2
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_CHAT_ID_2=
SINGLE_SCAN=false
```

> .env에 설정하면 alert_coin.py의 기본값을 덮어씁니다.

---

## 4. 봇 실행 및 테스트

```bash
python alert_coin.py
```

- 시작 시 각 봇에서 테스트 메시지가 오면 설정이 정상입니다.
- **5분봉** 신호 → 봇2 (`TELEGRAM_BOT_TOKEN_2`)로 전송
- **15분봉** 신호 → 봇1 (`TELEGRAM_BOT_TOKEN`)로 전송

---

## 5. 알림 종류

이 봇은 다음 신호를 감지하여 알림을 보냅니다:

| 신호 | 설명 |
|------|------|
| 🔻 과매도 돌파 | RSI 30 이하로 돌파 |
| 🔺 과매수 돌파 | RSI 70 이상으로 돌파 |
| 📈 HMA 200 상단 돌파 | 가격이 HMA 200 위로 돌파 |
| 📉 HMA 200 하단 돌파 | 가격이 HMA 200 아래로 이탈 |
