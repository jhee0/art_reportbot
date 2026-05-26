# 🤖 아트실 리포트봇 (TU 인트라넷 자동화)

TU 인트라넷 데이터를 자동으로 다운로드하고 검증하여 art 페이지에 업로드하는 완전 자동화 봇

## ✨ 주요 기능

- 🌐 **TU 인트라넷 자동 로그인 & 다운로드**: Selenium 기반 완전 자동화
- 🔍 **고급 데이터 검증**: 시간 합계 + 스마트 태그 검증 시스템
- 📊 **데이터 처리**: 이메일 → 이름 변환, 연차/반차 자동 태그, 제외 대상 필터링
- 📤 **art 페이지 자동 업로드**: 검증 통과 시 자동 업로드
- 💬 **슬랙 오류 알림**: 검증 오류 또는 업로드 실패 시에만 알림
- ⚠️ **스마트 오류 감지**: 문제 발견 시 담당자 이름 멘션

## 🎯 실행 모드

### 1. 전체 프로세스 (기본)
```bash
python tu_downloader.py
```
- 다운로드 → 처리 → 검증 → art 페이지 업로드 → 오류 시 슬랙 알림

### 2. 검증 전용 모드
```bash
python tu_downloader.py validation
```
- 다운로드 → 처리 → 검증 → 검증 결과만 슬랙 전송 (업로드 없음)
- 원본 파일(`export-아트실-...csv`)과 처리된 파일(`26_5.csv`) 모두 로컬에 저장

## 📅 매월 필수 업데이트

### `tu_downloader.py` 상단 설정값 수정
```python
OUTPUT_FILENAME = "26_5.csv"   # 🔄 매월 수정 (예: 26_6.csv, 26_7.csv)
MIN_REQUIRED_HOURS = 144       # 🔄 공휴일 제외한 실제 업무시간으로 수정
```

## 📁 설정 파일 목록

| 파일명 | 설명 |
|--------|------|
| `email_map.txt` | 이메일 → 이름 매핑 |
| `exclude_names.txt` | 검증 및 CSV에서 제외할 이름 |
| `leave_keywords.txt` | 연차/반차류 Tasklist 키워드 |
| `first_tags_required_second_art.txt` | 두 번째 태그가 필수인 첫 번째 태그 목록 |
| `first_tags_optional_second.txt` | 두 번째 태그가 선택인 첫 번째 태그 목록 |
| `second_tags_art.txt` | 허용되는 두 번째 태그 (아트류) |
| `second_tags_project.txt` | 허용되는 두 번째 태그 (프로젝트류) |

### `email_map.txt`
```
# 형식: 이메일@도메인 : 이름
jhee@aceproject.co.kr : 배진희
```

### `exclude_names.txt`
```
# 검증 및 CSV에서 제외할 이름 (한 줄에 하나)
김찬준
```

### `leave_keywords.txt`
```
# 연차/반차류 Tasklist 키워드
# 이 키워드에 해당하는 행은 Tags가 자동으로 '연차'로 설정됨
# 새 카테고리 추가 시 여기에 추가
연차
반차
오전반차
오후반차
생일
시간차
```

### `first_tags_required_second_art.txt`
```
# 두 번째 태그가 반드시 있어야 하는 첫 번째 태그들
실업무
cpm
c-
9up
9-
a1
netb
fbc
```

### `first_tags_optional_second.txt`
```
# 두 번째 태그가 있어도 되고 없어도 되는 첫 번째 태그들
공통업무
연차
사내행사
공휴일
```

## 🏷️ 태그 검증 시스템

### 동작 방식
1. **첫 번째 태그** 확인
   - `first_tags_required_second_art.txt` 목록에 있으면 → 두 번째 태그 **필수**
   - `first_tags_optional_second.txt` 목록에 있으면 → 두 번째 태그 **선택**
   - 둘 다 없으면 → **오류**

2. **두 번째 태그** 확인 (필수 그룹인 경우)
   - `second_tags_art.txt` 또는 `second_tags_project.txt`에 있어야 함

3. **연차 태그** (`Tags = "연차"`) → 태그 검증 제외

4. **exclude_names** 에 포함된 이름 → 검증 및 CSV 모두 제외

## 🔄 데이터 처리 흐름

```
TU 인트라넷 CSV 다운로드
  ↓
이메일 → 이름 변환 (email_map.txt)
  ↓
exclude_names 제외
  ↓
연차/반차류 자동 태그 처리 (leave_keywords.txt)
  ↓
검증 (시간 합산 + 태그)
  ↓
검증 통과 → art 페이지 업로드
검증 실패 → 슬랙 오류 알림 (업로드 안 함)
```

## 🛠️ GitHub Secrets 설정

| Secret 이름 | 설명 |
|------------|------|
| `TU_EMAIL` | TU 인트라넷 로그인 이메일 |
| `TU_PASSWORD` | TU 인트라넷 로그인 비밀번호 |
| `TU_ART_ID` | art 페이지 Basic Auth 아이디 |
| `TU_ART_PASSWORD` | art 페이지 Basic Auth 비밀번호 |
| `SLACK_BOT_TOKEN` | 슬랙 봇 토큰 |
| `SLACK_CHANNEL` | 전체 프로세스 슬랙 채널 |
| `SLACK_CHANNEL_VALIDATION` | 검증 전용 슬랙 채널 |

## 🤖 슬랙 봇 권한

- `chat:write` - 메시지 전송
- `channels:read` - 채널 목록 읽기

## ⏰ GitHub Actions 스케줄

### 전체 프로세스 (평일 매일 오전 7시 KST)
```yaml
cron: '0 22 * * 0-4'
```

### 검증 프로세스 (평일 3회)
```yaml
cron: '23 7 * * 1-5'   # KST 16:23
cron: '47 9 * * 1-5'   # KST 18:47
cron: '17 13 * * 1-5'  # KST 22:17
```

## 💬 슬랙 알림 기준

| 상황 | 슬랙 알림 |
|------|----------|
| 정상 완료 | ❌ 없음 |
| 검증 오류 발견 | ✅ 오류 목록 + 담당자 이름 + 수동 업데이트 요청 |
| art 업로드 실패 | ✅ 업로드 실패 알림 |

## 📦 의존성 (`requirements.txt`)
```
selenium
pandas
python-dotenv
slack-sdk
```

## 🚨 문제 해결

**로그인 실패**
- `.env` 또는 GitHub Secrets의 `TU_EMAIL`, `TU_PASSWORD` 확인

**art 페이지 업로드 실패**
- `TU_ART_ID`, `TU_ART_PASSWORD` 확인

**슬랙 전송 실패**
- `SLACK_BOT_TOKEN` 유효성 및 채널 확인

**검증 오류**
- 태그 설정 파일 업데이트
- `MIN_REQUIRED_HOURS` 조정

**새 연차 카테고리 추가됨**
- `leave_keywords.txt`에 한 줄 추가

## 📝 매월 체크리스트

- [ ] `OUTPUT_FILENAME` 업데이트 (예: `26_6.csv`)
- [ ] `MIN_REQUIRED_HOURS` 업데이트 (공휴일 제외 실제 업무시간)
- [ ] `email_map.txt` 신규 팀원 추가 여부 확인

## 🔗 관련 링크

- [TU 인트라넷](https://tu.aceproject.co.kr)
- [슬랙 앱 관리](https://api.slack.com/apps)
- [GitHub Actions 문서](https://docs.github.com/en/actions)
