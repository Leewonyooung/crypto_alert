# CloudType 배포 가이드

이 문서는 CloudType을 통해 알트코인 과매도/과매수 알림 봇을 배포하는 방법을 설명합니다.

## 📋 사전 준비

1. **CloudType 계정 생성**
   - [CloudType](https://cloudtype.io)에 가입

2. **GitHub/GitLab 저장소 준비**
   - 프로젝트를 Git 저장소에 푸시

## 🚀 배포 단계

### 1. 프로젝트 업로드

CloudType 대시보드에서:
1. "새 프로젝트" 클릭
2. Git 저장소 연결 또는 직접 업로드
3. Python 런타임 선택

### 2. 환경변수 설정

CloudType 대시보드의 "환경변수" 섹션에서 다음 변수들을 설정:

#### 필수 환경변수

```env
CHECK_INTERVAL=120
RSI_PERIOD=14
RSI_OVERSOLD=33
RSI_OVERBOUGHT=73
MIN_VOLUME_USDT=1000000
CATEGORY=linear
EXCLUDE_COINS=USDC,USDT,DAI,TUSD
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

#### 선택 환경변수

```env
SINGLE_SCAN=false
```

### 3. 빌드 및 실행 설정

CloudType은 다음 파일들을 자동으로 인식합니다:

- **Procfile**: `worker: python alert_coin.py`
- **requirements.txt**: 의존성 패키지 목록
- **cloudtype.yaml**: CloudType 전용 설정 (선택사항)

### 4. 배포

1. CloudType 대시보드에서 "배포" 버튼 클릭
2. 빌드 로그 확인
3. 실행 로그 확인

## 📊 모니터링

### 로그 확인

CloudType 대시보드의 "로그" 섹션에서:
- 실시간 로그 확인
- 에러 로그 필터링
- 성능 메트릭 확인

### 알림 확인

- 텔레그램 그룹에서 알림 수신 확인
- 봇이 정상 작동하는지 확인

## 🔧 트러블슈팅

### 문제: 봇이 시작되지 않음

**해결 방법:**
1. 환경변수가 모두 설정되었는지 확인
2. 로그에서 에러 메시지 확인
3. `TELEGRAM_BOT_TOKEN`과 `TELEGRAM_CHAT_ID` 확인

### 문제: 알림이 오지 않음

**해결 방법:**
1. 텔레그램 봇 토큰 확인
2. Chat ID 확인 (그룹에 봇이 추가되어 있는지)
3. 봇에게 메시지 전송 권한 확인

### 문제: 메모리 부족

**해결 방법:**
1. CloudType에서 더 높은 플랜으로 업그레이드
2. `CHECK_INTERVAL`을 늘려서 스캔 빈도 감소
3. `MIN_VOLUME_USDT`를 높여서 스캔할 코인 수 감소

## 🔄 업데이트

코드를 수정한 후:

1. Git에 커밋 및 푸시
2. CloudType에서 "재배포" 클릭
3. 새 버전이 자동으로 배포됨

## 💡 팁

1. **환경변수 보안**
   - 민감한 정보(봇 토큰 등)는 환경변수로만 관리
   - `.env` 파일은 Git에 커밋하지 않음

2. **로깅**
   - 모든 로그는 CloudType 대시보드에서 확인 가능
   - 에러 발생 시 로그를 확인하여 문제 해결

3. **성능 최적화**
   - `CHECK_INTERVAL`을 적절히 설정 (너무 짧으면 API 제한 발생 가능)
   - `MIN_VOLUME_USDT`로 유동성 있는 코인만 스캔

4. **비용 관리**
   - CloudType의 무료 플랜으로도 충분히 작동 가능
   - 필요시 유료 플랜으로 업그레이드

## 📝 참고사항

- CloudType은 24/7 서비스를 제공하므로 봇이 계속 실행됩니다
- 프로세스가 종료되면 자동으로 재시작됩니다
- 로그는 CloudType 대시보드에서 확인할 수 있습니다
