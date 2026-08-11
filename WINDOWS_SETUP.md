# Windows 환경 설정 가이드

macOS(cron)에서 Windows(작업 스케줄러)로 이 프로젝트를 옮길 때 따라야 할 순서.

## 1. Python 설치

1. https://www.python.org/downloads/ 에서 Python 3.11 설치 (설치 중 "Add python.exe to PATH" 체크 필수)
2. 설치 확인:
   ```
   python --version
   ```

## 2. 프로젝트 폴더 복사

이 폴더(`taskworld-automation`) 전체를 Windows PC의 원하는 위치로 복사.
예: `C:\Users\<사용자명>\taskworld-automation`

## 3. 가상환경(venv) 생성 및 패키지 설치

프로젝트 폴더에서 명령 프롬프트(cmd) 또는 PowerShell 열고:

```
cd C:\Users\<사용자명>\taskworld-automation
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 4. .env 파일 설정

프로젝트 폴더에 `.env` 파일을 새로 만들고, macOS에서 쓰던 것과 동일한 내용을 넣기:

```
TU_EMAIL=...
TU_PASSWORD=...
TU_ART_ID=...
TU_ART_PASSWORD=...
SLACK_BOT_TOKEN=...
SLACK_CHANNEL=...
SLACK_CHANNEL_VALIDATION=...
```

(`.env`는 `.gitignore`에 포함되어 있어 깃허브에는 안 올라감 — Mac에 있는 값을 그대로 복사해서 붙여넣으면 됨)

## 5. Chrome 설치 확인

Windows에 Google Chrome이 설치되어 있어야 함. `webdriver-manager`가 ChromeDriver는 자동으로 맞춰서 다운로드해주니 별도 설치는 불필요.

## 6. 수동 실행 테스트

작업 스케줄러 등록 전에 먼저 터미널에서 직접 한 번 실행해서 정상 동작하는지 확인:

```
cd C:\Users\<사용자명>\taskworld-automation
venv\Scripts\python.exe tu_downloader.py
```

## 7. 작업 스케줄러 등록 (평일 오전 7시)

### 방법 A — GUI

1. 시작 메뉴 → "작업 스케줄러" 검색 → 실행
2. 오른쪽 패널 → **"작업 만들기"** 클릭 (마법사인 "기본 작업 만들기" 말고 "작업 만들기")
3. **일반** 탭: 이름 입력 (예: "TU 리포트봇"), **"사용자가 로그온했는지 여부에 관계없이 실행"** 선택 ⚠️ 이거 체크 안 하면 컴퓨터 잠금/로그아웃 상태에서 조용히 안 돌아감 (macOS Full Disk Access 문제와 비슷한 함정)
4. **트리거** 탭: 새로 만들기 → "매주" 선택 → 요일: 월,화,수,목,금 체크 → 시작 시간: 오전 7:00
5. **동작** 탭: 새로 만들기 →
   - 프로그램/스크립트: `C:\Users\<사용자명>\taskworld-automation\venv\Scripts\python.exe`
   - 인수 추가: `tu_downloader.py`
   - 시작 위치: `C:\Users\<사용자명>\taskworld-automation`
6. **조건** 탭: "컴퓨터가 AC 전원에 연결된 경우에만 작업 시작" 체크 해제 (노트북이면 배터리로도 돌게)
7. 확인 눌러서 저장 (관리자 권한 물어보면 승인)

### 방법 B — 명령어 한 번에 등록 (`schtasks`)

명령 프롬프트를 **관리자 권한**으로 열고:

```
schtasks /create /tn "TU리포트봇" /tr "C:\Users\<사용자명>\taskworld-automation\venv\Scripts\python.exe C:\Users\<사용자명>\taskworld-automation\tu_downloader.py" /sc weekly /d MON,TUE,WED,THU,FRI /st 07:00 /rl highest
```

## 8. 등록 확인 및 테스트하는 방법

등록된 작업 확인:
```
schtasks /query /tn "TU리포트봇"
```

예약 시간(오전 7시)까지 기다리지 않고 지금 바로 한 번 실행해서 테스트:
```
schtasks /run /tn "TU리포트봇"
```

실행 결과를 파일로 남기고 싶다면, `schtasks` 등록 시 `/tr` 부분을 아래처럼 바꿔서 리다이렉트 (macOS의 `cron.log`와 동일한 역할):

```
cmd /c "C:\...\venv\Scripts\python.exe C:\...\tu_downloader.py >> C:\...\cron.log 2>&1"
```

### 성공/실패 확인하는 3가지 방법

1. **작업 스케줄러 GUI의 "기록" 탭** — 작업 스케줄러에서 이 작업을 클릭하면 하단에 "기록" 탭이 보임. 마지막 실행 시각과 결과 코드가 나오는데, **`0x0`이면 성공**. 이게 제일 빠르게 확인하는 방법 (cron.log 열어볼 필요도 없이 바로 보임).
2. **`cron.log` 파일 내용 확인** — 위에서 리다이렉트를 설정했다면, 이 파일을 열어서 로그인/다운로드/업로드 각 단계가 `✅`로 찍혔는지 확인. 맨 아래에 "✅ 통계 업로드 완료!"가 있으면 성공.
3. **`debug_*.png` 스크린샷 확인** — 업로드 단계에서 실패하면(`debug_csv_btn_not_found.png`, `debug_file_input_not_found.png`, `debug_upload_btn_not_found.png` 중 하나) 프로젝트 폴더에 실패 시점의 스크린샷이 자동으로 남음. 이 파일이 생겼다면 그걸 열어서 어느 단계에서 막혔는지 눈으로 확인 가능.

### 제일 먼저 의심해볼 것

- **"사용자가 로그온했는지 여부와 관계없이 실행"** 체크박스가 꺼져있으면, 컴퓨터가 잠겨있거나 로그아웃된 상태에서 작업이 조용히 실패함 (macOS에서 Full Disk Access 권한 문제로 cron.log조차 안 생겼던 것과 같은 종류의 함정). "기록" 탭에 아예 실행 흔적이 없다면 이걸 제일 먼저 확인.

## macOS와 다른 점 요약

| 항목 | macOS | Windows |
|---|---|---|
| 스케줄러 | cron (`crontab -e`) | 작업 스케줄러 (`schtasks`) |
| venv 파이썬 경로 | `venv/bin/python3` | `venv\Scripts\python.exe` |
| 잠금/로그아웃 시 실행 | Full Disk Access 권한 필요 | "로그온 여부와 관계없이 실행" 옵션 필요 |
| ChromeDriver | webdriver-manager 자동 | webdriver-manager 자동 (동일) |

## 주의

`tu_downloader.py`의 `DEFAULT_HEADLESS`는 반드시 `True`여야 함. 작업 스케줄러/cron처럼 화면(GUI 세션) 없이 실행되는 환경에서 `headless=False`로 두면 Chrome이 뜨지 못하고 즉시 실패함.
