# tu_downloader.py - TU 인트라넷(tu.aceproject.co.kr) 완전 자동화 스크립트
import os
import time
import glob
import pandas as pd
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import logging

# .env 파일 로드
load_dotenv()

# ==========================================
# 월별 설정 변수 (매월 MONTHLY_HOURS에 추가)
# ==========================================
_KST = timezone(timedelta(hours=9))
_now = datetime.now(_KST)
OUTPUT_FILENAME = f"{str(_now.year)[2:]}_{_now.month}.csv"

MONTHLY_HOURS = {
    (2026, 6): 168,
    (2026, 7): 176,
    (2026, 8): 160,
    (2026, 9): 160,
    (2026, 10): 160,
    (2026, 11): 168,
    (2026, 12): 168,
    # 매달 여기에 추가하세요: (연도, 월): 시간
}
MIN_REQUIRED_HOURS = MONTHLY_HOURS[(_now.year, _now.month)]

# ==========================================
# 파일 경로 설정
# ==========================================
FIRST_TAGS_REQUIRED_ART_FILE = "first_tags_required_second_art.txt"
FIRST_TAGS_OPTIONAL_SECOND_FILE = "first_tags_optional_second.txt"
SECOND_TAGS_ART_FILE = "second_tags_art.txt"
SECOND_TAGS_PROJECT_FILE = "second_tags_project.txt"
EXCLUDE_VALUES_FILE = "exclude_values.txt"
EMAIL_MAP_FILE = "email_map.txt"
EXCLUDE_NAMES_FILE = "exclude_names.txt"
LEAVE_KEYWORDS_FILE = "leave_keywords.txt"

# ==========================================
# 기타 설정
# ==========================================
DEFAULT_HEADLESS = True

DISABLE_SLACK_NOTIFICATIONS = False

logger = logging.getLogger(__name__)


class TaskworldSeleniumDownloader:
    def __init__(self, headless=DEFAULT_HEADLESS):
        """
        Selenium 기반 TU 인트라넷 자동 다운로더 + CSV 처리 + 슬랙 전송
        (tu.aceproject.co.kr 기준)
        
        Args:
            headless (bool): 브라우저를 숨김 모드로 실행할지 여부
        """
        self.headless = headless
        self.driver = None
        self.wait = None
        self.download_dir = os.path.abspath("./")
        
        # 슬랙 봇 설정
        self.slack_token = os.getenv("SLACK_BOT_TOKEN")
        self.slack_channel = os.getenv("SLACK_CHANNEL", "#아트실")
        self.slack_client = None
        
        # 한국 시간대 설정
        self.korea_tz = timezone(timedelta(hours=9))
        
        print(f"🤖 TU 자동화 다운로더 초기화 - headless: {headless}")
        print(f"📄 출력 파일명: {OUTPUT_FILENAME}")
        print(f"⏱️ 최소 필수 시간: {MIN_REQUIRED_HOURS}시간")
        print(f"💬 슬랙 채널: '{self.slack_channel}' (따옴표 포함 확인)")
        
        # 슬랙 봇 초기화
        if self.slack_token:
            try:
                self.slack_client = WebClient(token=self.slack_token)
                response = self.slack_client.auth_test()
                print(f"✅ 슬랙 봇 연결 성공: {response['user']}")
            except SlackApiError as e:
                print(f"❌ 슬랙 봇 연결 실패: {e.response['error']}")
        else:
            print("⚠️ 슬랙 토큰이 없어 슬랙 전송 기능 비활성화")
        
    def setup_driver(self):
        """Chrome 드라이버 설정 (GitHub Actions용 최적화)"""
        try:
            print("🔧 Chrome 드라이버 설정 시작...")
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument("--headless")
            
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # 다운로드 설정
            prefs = {
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
                "profile.default_content_settings.popups": 0
            }
            chrome_options.add_experimental_option("prefs", prefs)
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 30)
            
            print("✅ Chrome 드라이버 설정 완료")
            
            if not self.headless:
                time.sleep(3)
            
            return True
            
        except Exception as e:
            print(f"❌ 드라이버 설정 실패: {e}")
            return False
    
    def load_exclude_values(self):
        """제외할 Tasklist 값들을 텍스트 파일에서 로드"""
        try:
            if os.path.exists(EXCLUDE_VALUES_FILE):
                with open(EXCLUDE_VALUES_FILE, 'r', encoding='utf-8') as f:
                    exclude_values = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                print(f"✅ 제외 값 설정 로드 완료: {len(exclude_values)}개 ({EXCLUDE_VALUES_FILE})")
                return exclude_values
            else:
                default_values = ["주요일정", "아트실", "UI팀", "리소스팀", "디자인팀", "TA팀"]
                print(f"❌ {EXCLUDE_VALUES_FILE} 파일이 없습니다!")
                print(f"🔧 기본값으로 파일을 생성합니다: {default_values}")
                
                with open(EXCLUDE_VALUES_FILE, 'w', encoding='utf-8') as f:
                    f.write("# 제외할 Tasklist 값들 (한 줄에 하나씩)\n")
                    f.write("# 주석은 #으로 시작\n\n")
                    for value in default_values:
                        f.write(f"{value}\n")
                
                print(f"✅ {EXCLUDE_VALUES_FILE} 파일이 생성되었습니다. 필요시 수정하세요.")
                return default_values
                
        except Exception as e:
            print(f"❌ 제외 값 로드 실패: {e}")
            return ["주요일정", "아트실", "UI팀", "리소스팀", "디자인팀", "TA팀"]
    
    def load_email_map(self):
        """이메일 → 이름 매핑 파일 로드 (email_map.txt)
        형식: jhee@aceproject.co.kr : 배진희
        """
        try:
            if os.path.exists(EMAIL_MAP_FILE):
                email_map = {}
                with open(EMAIL_MAP_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        parts = [p.strip() for p in line.split(':')]
                        if len(parts) >= 2:
                            email_map[parts[0]] = parts[1]
                print(f"✅ 이메일 매핑 로드 완료: {len(email_map)}명")
                return email_map
            else:
                print(f"⚠️ {EMAIL_MAP_FILE} 파일이 없습니다! 기본 파일을 생성합니다.")
                with open(EMAIL_MAP_FILE, 'w', encoding='utf-8') as f:
                    f.write("# 이메일 → 이름 매핑\n")
                    f.write("# 형식: 이메일@도메인 : 이름\n\n")
                    f.write("# jhee@aceproject.co.kr : 배진희\n")
                return {}
        except Exception as e:
            print(f"❌ 이메일 매핑 로드 실패: {e}")
            return {}

    def load_leave_keywords(self):
        """연차/반차류 Tasklist 키워드 로드 (leave_keywords.txt)
        이 키워드에 해당하는 행은 Tags가 자동으로 "연차"로 설정됨
        """
        try:
            if os.path.exists(LEAVE_KEYWORDS_FILE):
                keywords = set()
                with open(LEAVE_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        kw = line.strip()
                        if kw and not kw.startswith('#'):
                            keywords.add(kw)
                print(f"✅ 연차 키워드 로드: {len(keywords)}개 → {keywords}")
                return keywords
            else:
                # 기본값으로 파일 생성
                defaults = ["연차", "반차", "오전반차", "오후반차", "생일", "시간차", "공휴일"]
                with open(LEAVE_KEYWORDS_FILE, 'w', encoding='utf-8') as f:
                    f.write("# 연차/반차류 Tasklist 키워드 (한 줄에 하나)\n")
                    f.write("# 이 키워드에 해당하는 행은 Tags가 자동으로 '연차'로 설정됨\n\n")
                    for kw in defaults:
                        f.write(f"{kw}\n")
                print(f"✅ {LEAVE_KEYWORDS_FILE} 기본 파일 생성 완료")
                return set(defaults)
        except Exception as e:
            print(f"❌ 연차 키워드 로드 실패: {e}")
            return set(["연차", "반차", "오전반차", "오후반차", "생일", "시간차", "공휴일"])

    def load_exclude_names(self):
        """검증에서 제외할 이름 목록 로드 (exclude_names.txt)
        형식: 한 줄에 이름 하나
        예시: 김찬준
        """
        try:
            if os.path.exists(EXCLUDE_NAMES_FILE):
                exclude_names = set()
                with open(EXCLUDE_NAMES_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        name = line.strip()
                        if name and not name.startswith('#'):
                            exclude_names.add(name)
                print(f"✅ 검증 제외 이름 로드: {len(exclude_names)}명 → {exclude_names}")
                return exclude_names
            else:
                with open(EXCLUDE_NAMES_FILE, 'w', encoding='utf-8') as f:
                    f.write("# 검증에서 제외할 이름 목록 (한 줄에 하나)\n")
                    f.write("# 예시: 김찬준\n")
                print(f"✅ {EXCLUDE_NAMES_FILE} 템플릿 생성 완료")
                return set()
        except Exception as e:
            print(f"❌ 검증 제외 이름 로드 실패: {e}")
            return set()

    def login_to_taskworld(self, email, password):
        """TU 인트라넷 로그인 (이메일 + 비밀번호)"""
        try:
            print("🔍 TU 인트라넷 로그인 시작...")
            
            self.driver.get("https://tu.aceproject.co.kr/login")
            time.sleep(3)
            
            return self._handle_email_login(email, password)
                    
        except Exception as e:
            print(f"❌ 로그인 전체 프로세스 실패: {e}")
            return False
    
    def _handle_email_login(self, email, password):
        """이메일 + 비밀번호 로그인 처리 (TU 인트라넷)"""
        try:
            print("📧 이메일 로그인 시작...")
            
            # 이메일 입력 (label이 '이메일'인 input)
            email_input = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='email' or @name='email' or @placeholder]"))
            )
            email_input.clear()
            email_input.send_keys(email)
            print("✅ 이메일 입력 완료")
            
            # 비밀번호 입력 (label이 '비밀번호'인 input)
            password_input = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='password' or @name='password']"))
            )
            password_input.clear()
            password_input.send_keys(password)
            print("✅ 비밀번호 입력 완료")
            
            # 로그인 버튼 클릭 — 구글 로그인 버튼과 혼동되지 않도록 정확히 지정
            # submit 타입 버튼 우선, 없으면 비밀번호 입력창 이후에 오는 로그인 버튼
            login_btn = None
            login_btn_selectors = [
                "//button[@type='submit' and not(contains(text(),'Google'))]",
                "//form//button[contains(text(),'로그인')]",
                "//button[text()='로그인']",
                "//input[@type='submit' and not(contains(@value,'Google'))]",
            ]
            for selector in login_btn_selectors:
                try:
                    login_btn = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    print(f"✅ 로그인 버튼 발견: '{login_btn.text.strip()}'")
                    break
                except:
                    continue

            if not login_btn:
                print("❌ 로그인 버튼을 찾지 못함")
                return False

            login_btn.click()
            print("✅ 로그인 버튼 클릭")
            
            # 로그인 완료 대기 — tu.aceproject.co.kr 도메인으로 돌아올 때까지
            # 1단계: 로그인 페이지에서 벗어날 때까지 대기
            print("⏳ 로그인 페이지 이탈 대기...")
            WebDriverWait(self.driver, 30).until(
                lambda driver: "login" not in driver.current_url
            )
            print(f"  → 현재 URL: {self.driver.current_url}")

            # 2단계: 구글 OAuth 중간 페이지를 거칠 수 있으므로 TU 홈까지 대기
            print("⏳ TU 홈 페이지 도착 대기 (최대 60초)...")
            WebDriverWait(self.driver, 60).until(
                lambda driver: "tu.aceproject.co.kr" in driver.current_url
                               and "login" not in driver.current_url
            )
            time.sleep(3)
            print(f"  → TU 홈 도착: {self.driver.current_url}")
            
            print("✅ TU 인트라넷 로그인 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 이메일 로그인 실패: {e}")
            return False
    
    def _add_artroom_team(self):
        """사이드바 팀 섹션에서 + 버튼 클릭 → 아트실 팀 추가"""
        try:
            # 팀 섹션 안에서만 정확히 '아트실' 텍스트 확인
            # (프로젝트의 '아트실 5월' 등과 혼동 방지)
            try:
                # '팀' 텍스트 이후에 오는 요소 중 text()가 정확히 '아트실'인 것만
                team_artroom = self.driver.find_elements(
                    By.XPATH,
                    "//*[text()='팀']/following::*[text()='아트실']"
                )
                visible = [el for el in team_artroom if el.is_displayed() and el.text.strip() == '아트실']
                if visible:
                    print("✅ 아트실 팀이 이미 사이드바 팀 섹션에 존재함, 추가 생략")
                    return True
                else:
                    print("ℹ️ 팀 섹션에 아트실 없음, + 버튼으로 추가 시작")
            except Exception as e:
                print(f"ℹ️ 팀 섹션 확인 중 오류: {e}, + 버튼으로 추가 시작")

            print("➕ 팀 섹션 + 버튼 탐색 중...")

            # + 버튼은 SVG 아이콘 (class="w-3.5 h-3.5")을 포함한 버튼
            plus_selectors = [
                # SVG 클래스로 직접 찾고 부모 버튼 클릭
                "//*[text()='팀']/following::*[.//*[contains(@class,'w-3.5')]][1]",
                "//*[text()='팀']/following::button[.//*[contains(@class,'w-3.5')]][1]",
                "//*[text()='팀']/following::button[1]",
                "//*[text()='팀']/parent::*//button",
                "//*[text()='팀']/parent::*/button",
                # SVG 부모 요소 직접
                "//svg[contains(@class,'w-3.5')]/parent::button",
                "//svg[contains(@class,'w-3.5')]/parent::*[@role='button']",
                "//svg[contains(@class,'w-3.5')]/parent::*",
            ]

            plus_btn = None
            for selector in plus_selectors:
                try:
                    els = self.driver.find_elements(By.XPATH, selector)
                    for el in els:
                        if el.is_displayed():
                            print(f"✅ 팀 + 버튼 발견: tag={el.tag_name} class='{el.get_attribute('class')}'")
                            plus_btn = el
                            break
                    if plus_btn:
                        break
                except:
                    continue

            if not plus_btn:
                print("❌ 팀 + 버튼을 찾지 못함")
                return False

            try:
                plus_btn.click()
            except:
                self.driver.execute_script("arguments[0].click();", plus_btn)

            time.sleep(2)
            print("✅ 팀 + 버튼 클릭 완료, 팀 검색창 대기...")

            # 팀 검색 입력창 대기 후 '아트실' 입력
            search_input = None
            search_selectors = [
                "//input[@placeholder]",
                "//input[@type='text']",
                "//input[@type='search']",
                "//input[contains(@class,'search') or contains(@class,'input')]",
            ]
            for selector in search_selectors:
                try:
                    search_input = WebDriverWait(self.driver, 8).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    if search_input.is_displayed():
                        break
                except:
                    continue

            if not search_input:
                print("❌ 팀 검색 입력창을 찾지 못함")
                return False

            search_input.clear()
            search_input.send_keys("아트실")
            print("✅ '아트실' 입력 완료")
            time.sleep(2)

            # 검색 결과에서 '아트실' 항목 클릭
            result_selectors = [
                "//*[text()='아트실']",
                "//li[contains(text(),'아트실')]",
                "//div[contains(text(),'아트실')]",
                "//*[contains(text(),'아트실') and not(contains(text(),'아트실 5월'))]",
            ]
            for selector in result_selectors:
                try:
                    result_item = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    try:
                        result_item.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", result_item)
                    print("✅ '아트실' 팀 선택 완료")
                    time.sleep(2)
                    return True
                except:
                    continue

            print("❌ 검색 결과에서 '아트실'을 찾지 못함")
            return False

        except Exception as e:
            print(f"❌ 아트실 팀 추가 실패: {e}")
            return False

    def navigate_to_workspace(self):
        """TU 인트라넷: 사이드바에 아트실 팀 추가 후 클릭 → 통계 탭 이동"""
        try:
            print(f"📂 '아트실' 사이드바 메뉴 찾기...")

            # 아트실 팀 추가 (없을 경우 + 버튼으로 추가)
            self._add_artroom_team()
            time.sleep(2)

            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                print(f"\n🔄 시도 {attempt}/{max_attempts}")
                
                # 사이드바에서 '아트실' 클릭 — 정확히 '아트실' 텍스트만 매칭
                artroom_selectors = [
                    "//*[text()='아트실']",
                    "//a[text()='아트실']",
                    "//span[text()='아트실']",
                    "//div[text()='아트실']",
                    "//*[normalize-space(text())='아트실']",
                ]
                
                clicked = False
                for selector in artroom_selectors:
                    try:
                        els = self.driver.find_elements(By.XPATH, selector)
                        for el in els:
                            # 텍스트가 정확히 '아트실'인지 재확인 (아트실5월 등 제외)
                            if el.text.strip() == '아트실' and el.is_displayed():
                                try:
                                    el.click()
                                except:
                                    self.driver.execute_script("arguments[0].click();", el)
                                print("✅ '아트실' 클릭 성공")
                                clicked = True
                                time.sleep(3)
                                break
                        if clicked:
                            break
                    except:
                        continue
                
                if not clicked:
                    print(f"❌ 시도 {attempt}: '아트실' 메뉴를 찾지 못함")
                    if attempt < max_attempts:
                        self.driver.refresh()
                        time.sleep(3)
                    continue
                
                # '통계' 탭 클릭
                stats_selectors = [
                    "//button[contains(text(), '통계')]",
                    "//span[contains(text(), '통계')]",
                    "//a[contains(text(), '통계')]",
                    "//*[text()='통계']",
                    "//*[contains(@class, 'tab') and contains(text(), '통계')]",
                ]
                
                stats_clicked = False
                for selector in stats_selectors:
                    try:
                        el = WebDriverWait(self.driver, 8).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        try:
                            el.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", el)
                        print("✅ '통계' 탭 클릭 성공")
                        stats_clicked = True
                        time.sleep(3)
                        break
                    except:
                        continue
                
                if stats_clicked:
                    print("✅ 아트실 통계 페이지 접속 완료!")
                    return True
                
                print(f"❌ 시도 {attempt}: '통계' 탭을 찾지 못함")
                if attempt < max_attempts:
                    self.driver.refresh()
                    time.sleep(3)
            
            print("❌ 모든 시도 실패")
            return False
            
        except Exception as e:
            print(f"❌ 워크스페이스 접속 중 오류: {e}")
            return False


    
    def load_allowed_tags(self):
        """허용된 태그 목록 파일에서 로드"""
        try:
            # 첫 번째 태그 (두 번째 태그 필수) — art 파일 하나로 통합
            try:
                with open(FIRST_TAGS_REQUIRED_ART_FILE, 'r', encoding='utf-8') as f:
                    first_tags_required_art = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                print(f"✅ 필수 첫번째 태그 로드: {len(first_tags_required_art)}개")
            except FileNotFoundError:
                default_art = ["cpm", "9up", "c-"]
                with open(FIRST_TAGS_REQUIRED_ART_FILE, 'w', encoding='utf-8') as f:
                    f.write("# 두 번째 태그가 반드시 있어야 하는 첫 번째 태그들\n")
                    f.write("# 한 줄에 하나씩, 주석은 #으로 시작\n\n")
                    for tag in default_art:
                        f.write(f"{tag}\n")
                first_tags_required_art = default_art

            # project는 art와 동일하게 처리 (파일 통합됨)
            first_tags_required_project = first_tags_required_art
            
            # 두 번째 태그 선택적인 첫 번째 태그들 (기존과 동일)
            try:
                with open(FIRST_TAGS_OPTIONAL_SECOND_FILE, 'r', encoding='utf-8') as f:
                    first_tags_optional_second = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            except FileNotFoundError:
                default_optional = ["공통업무", "공통작업", "연차", "사내행사", "공휴일"]
                with open(FIRST_TAGS_OPTIONAL_SECOND_FILE, 'w', encoding='utf-8') as f:
                    f.write("# 두 번째 태그가 있어도 되고 없어도 되는 첫 번째 태그들\n")
                    f.write("# 한 줄에 하나씩, 주석은 #으로 시작\n\n")
                    for tag in default_optional:
                        f.write(f"{tag}\n")
                first_tags_optional_second = default_optional
            
            # 아트용 두 번째 태그들
            try:
                with open('second_tags_art.txt', 'r', encoding='utf-8') as f:
                    second_tags_art = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            except FileNotFoundError:
                default_art_second = ["회의", "문서작업"]
                with open('second_tags_art.txt', 'w', encoding='utf-8') as f:
                    f.write("# 아트 그룹용 두 번째 태그로 허용되는 값들 (완전 일치)\n")
                    f.write("# 한 줄에 하나씩, 주석은 #으로 시작\n\n")
                    for tag in default_art_second:
                        f.write(f"{tag}\n")
                second_tags_art = default_art_second

            # 프로젝트용 두 번째 태그들
            try:
                with open('second_tags_project.txt', 'r', encoding='utf-8') as f:
                    second_tags_project = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            except FileNotFoundError:
                default_project_second = ["피드백", "교육"]
                with open('second_tags_project.txt', 'w', encoding='utf-8') as f:
                    f.write("# 프로젝트 그룹용 두 번째 태그로 허용되는 값들 (완전 일치)\n")
                    f.write("# 한 줄에 하나씩, 주석은 #으로 시작\n\n")
                    for tag in default_project_second:
                        f.write(f"{tag}\n")
                second_tags_project = default_project_second
            
            return first_tags_required_art, first_tags_required_project, first_tags_optional_second, second_tags_art, second_tags_project
            
        except Exception as e:
            print(f"❌ 태그 설정 파일 읽기 실패: {e}")
            exit(1)

    def validate_tags(self, df, first_tags_required_art, first_tags_required_project, first_tags_optional_second, second_tags_art, second_tags_project, exclude_names=None):
        """C열 태그 검증 - 개선된 로직"""
        
        first_tags_required_second = first_tags_required_art + first_tags_required_project
        second_tags = second_tags_art + second_tags_project
        
        tag_validation_issues = []
        
        try:
            if 'Tags' not in df.columns:
                tag_validation_issues.append("Tags 열이 존재하지 않습니다.")
                return tag_validation_issues
            if 'Name' not in df.columns:
                tag_validation_issues.append("Name 열이 존재하지 않습니다. email_map.txt 설정을 확인하세요.")
                return tag_validation_issues
            
            # 전체 허용된 첫 번째 태그 목록
            all_first_tags = first_tags_required_second + first_tags_optional_second
            
            # 각 행별로 태그 검증
            for idx, row in df.iterrows():
                person_name = row['Name']  # 이메일 매핑된 이름
                tags = row['Tags']
                task_name = row['Task']
                task_display = str(task_name)[:20] + "..." if len(str(task_name)) > 20 else str(task_name)

                # 이름 설정 (email_map 변환된 이름 전체 사용)
                if pd.isna(person_name) or str(person_name).strip() == '':
                    person_group = '미분류'
                else:
                    person_group = str(person_name).strip()

                # 검증 제외 대상 스킵
                if exclude_names and person_group in exclude_names:
                    continue

                # 연차 태그는 태그 검증 제외
                if str(tags).strip() == '연차':
                    continue

                # 태그가 비어있거나 NaN인 경우 오류 추가
                if pd.isna(tags) or tags == '' or tags == 0:
                    issue_msg = f"{person_group}님 태그 오류 : {task_display} (태그 없음)"
                    if issue_msg not in tag_validation_issues:
                        tag_validation_issues.append(issue_msg)
                    continue
                
                # 태그를 쉼표로 분리
                tag_list = str(tags).split(',')
                tag_list = [tag.strip() for tag in tag_list if tag.strip()]
                
                if len(tag_list) == 0:
                    continue
                
                # 첫 번째 태그 검증 (부분 일치)
                first_tag = tag_list[0]
                first_tag_valid = False
                first_tag_category = None
                
                # 필수 그룹에서 확인
                for allowed_first in first_tags_required_second:
                    if first_tag.startswith(allowed_first):
                        first_tag_valid = True
                        first_tag_category = 'required'
                        break
                
                # 필수 그룹에서 못 찾으면 선택적 그룹에서 확인
                if not first_tag_valid:
                    for allowed_first in first_tags_optional_second:
                        if first_tag.startswith(allowed_first):
                            first_tag_valid = True
                            first_tag_category = 'optional'
                            break
                
                # 첫 번째 태그가 유효하지 않으면 오류
                if not first_tag_valid:
                    issue_msg = f"{person_group}님 태그 오류 : {task_display} (첫번째 태그 '{first_tag}' 불가능)"
                    if issue_msg not in tag_validation_issues:
                        tag_validation_issues.append(issue_msg)
                    continue
                
                # 두 번째 태그 검증
                if first_tag_category == 'required':
                    # 두 번째 태그 필수인 경우
                    if len(tag_list) < 2:
                        issue_msg = f"{person_group}님 태그 오류 : {task_display} (두번째 태그 누락, '{first_tag}'는 필수)"
                        if issue_msg not in tag_validation_issues:
                            tag_validation_issues.append(issue_msg)
                    else:
                        second_tag = tag_list[1]
                        if second_tag not in second_tags:
                            issue_msg = f"{person_group}님 태그 오류 : {task_display} (두번째 태그 '{second_tag}' 불가능)"
                            if issue_msg not in tag_validation_issues:
                                tag_validation_issues.append(issue_msg)
                
                elif first_tag_category == 'optional':
                    # 두 번째 태그 선택적인 경우 - 있으면 검증
                    if len(tag_list) >= 2:
                        second_tag = tag_list[1]
                        if second_tag not in second_tags:
                            issue_msg = f"{person_group}님 태그 오류 : {task_display} (두번째 태그 '{second_tag}' 불가능)"
                            if issue_msg not in tag_validation_issues:
                                tag_validation_issues.append(issue_msg)
            
            return tag_validation_issues
            
        except Exception as e:
            error_msg = f"태그 검증 중 오류 발생: {str(e)}"
            return [error_msg]
    
    def validate_csv_data(self, df, min_hours=MIN_REQUIRED_HOURS):
        """CSV 데이터 검증 - 시간 합계 + 태그 검증"""
        try:
            if len(df.columns) < 4:
                return ["열 수가 부족합니다. 최소 4개 열이 필요합니다."]

            # process_csv에서 이미 컬럼명과 Name 컬럼이 설정된 df가 들어오므로
            # 컬럼 재설정 없이 그대로 사용
            # 필수 컬럼 존재 여부만 확인
            required = ['Name', 'Task', 'Tags', 'Time Spent']
            missing = [c for c in required if c not in df.columns]
            if missing:
                return [f"필수 컬럼 없음: {missing}"]

            # 1. 태그 설정 로드
            first_tags_required_art, first_tags_required_project, first_tags_optional_second, second_tags_art, second_tags_project = self.load_allowed_tags()

            # 2. 검증 제외 이름 로드
            exclude_names = self.load_exclude_names()

            # 3. 시간 검증
            validation_issues = self._validate_time_totals(df, min_hours, exclude_names)

            # 4. 태그 검증
            tag_issues = self.validate_tags(df, first_tags_required_art, first_tags_required_project, first_tags_optional_second, second_tags_art, second_tags_project, exclude_names)
            
            # 검증 결과 합치기
            all_issues = validation_issues + tag_issues
            
            if not all_issues:
                print("모든 검증 통과!")
            
            return all_issues
            
        except Exception as e:
            import traceback
            error_msg = f"검증 중 오류 발생: {str(e)}"
            print(f"상세 오류 정보:")
            print(traceback.format_exc())
            return [error_msg]
    
    def _validate_time_totals(self, df, min_hours, exclude_names=None):
        """시간 합계 검증"""
        validation_issues = []
        
        def convert_time_to_hours(time_str):
            """시간 문자열 (HH:MM:SS)을 시간 단위로 변환"""
            try:
                if pd.isna(time_str) or time_str == '' or time_str == 0:
                    return 0.0
                
                time_str = str(time_str).strip()
                
                if ':' in time_str:
                    parts = time_str.split(':')
                    if len(parts) == 3:
                        hours = int(parts[0])
                        minutes = int(parts[1])
                        seconds = int(parts[2])
                        total_hours = hours + (minutes / 60.0) + (seconds / 3600.0)
                        return round(total_hours, 1)
                    elif len(parts) == 2:
                        minutes = int(parts[0])
                        seconds = int(parts[1])
                        total_hours = (minutes / 60.0) + (seconds / 3600.0)
                        return round(total_hours, 1)
                
                return round(float(time_str), 1)
                
            except (ValueError, IndexError, TypeError):
                return 0.0
        
        def get_name_group(name):
            """이름 전체 반환 (email_map으로 이미 변환된 이름 사용)"""
            if pd.isna(name) or str(name).strip() == '':
                return '미분류'
            return str(name).strip()
        
        # Time Spent 컬럼 찾기
        time_column = None
        if 'Time Spent' in df.columns:
            time_column = 'Time Spent'
        elif 'Time_Spent' in df.columns:
            time_column = 'Time_Spent'
        else:
            if len(df.columns) >= 4:
                time_column = df.columns[3]
            else:
                return ["시간 데이터 컬럼을 찾을 수 없습니다."]
        
        # 시간 데이터 변환
        df['Time_Hours'] = df[time_column].apply(convert_time_to_hours)
        
        # 이름 그룹 생성 (매핑된 이름 컬럼 사용)
        name_col = 'Name' if 'Name' in df.columns else 'Assigned To'
        df['Name_Group'] = df[name_col].apply(get_name_group)
        
        # 그룹별 시간 합계 계산
        group_totals = df.groupby('Name_Group')['Time_Hours'].sum()
        
        # 각 그룹별 검증
        for name_group, total_hours in group_totals.items():
            total_hours = round(total_hours, 1)
            
            if exclude_names and name_group in exclude_names:
                print(f"  ⏭️ 합산 검증 제외: {name_group}")
                continue
            if total_hours != min_hours:
                issue_msg = f"{name_group}님 합산 오류 (현재: {total_hours}시간, 기준: {min_hours}시간)"
                validation_issues.append(issue_msg)
        
        return validation_issues
    
    def process_csv(self, input_file, columns=['Assigned To', 'Task', 'Tags', 'Time Spent']):
        """CSV 파일 처리 - Assigned To(이메일→이름 변환) 기반 필터링 후 저장"""
        try:
            # CSV 읽기
            df = pd.read_csv(input_file)
            original_count = len(df)
            print(f"📊 원본 행 수: {original_count}")

            # 이메일 → 이름 매핑 로드
            email_map = self.load_email_map()

            # Assigned To 이메일 → 이름 변환
            if 'Assigned To' in df.columns:
                df['Name'] = df['Assigned To'].apply(
                    lambda x: email_map.get(str(x).strip(), str(x).strip()) if pd.notna(x) else ''
                )
                print(f"✅ 이름 변환 완료")
            else:
                print("⚠️ 'Assigned To' 열 없음")
                df['Name'] = ''

            # Assigned To가 비어있는 행 체크 (오류로 수집, 제거하지 않음)
            empty_assigned = df[df['Assigned To'].isna() | (df['Assigned To'].astype(str).str.strip() == '')]
            assigned_warnings = []
            for _, row in empty_assigned.iterrows():
                task_display = str(row['Task'])[:25] + "..." if len(str(row['Task'])) > 25 else str(row['Task'])
                assigned_warnings.append(f"담당자 없음 오류 : {task_display} (Assigned To 비어있음)")
                print(f"⚠️ 담당자 없음: {task_display}")

            # email_map에 없는 이메일 경고
            if email_map:
                unmapped = df[~df['Assigned To'].isna() &
                              ~df['Assigned To'].astype(str).str.strip().isin(email_map.keys())]
                for email_val in unmapped['Assigned To'].dropna().unique():
                    email_val = str(email_val).strip()
                    if email_val:
                        print(f"⚠️ email_map 미등록 이메일: {email_val}")

            # 필터링 없이 전체 행 사용
            df_filtered = df
            removed_count = 0
            print(f"📊 전체 행 수: {len(df_filtered)}")

            # Status가 Completed이면서 첫번째 태그가 '공통업무'인 경우 검증 (필터링 전)
            status_completed_tag_issues = []
            if 'Status' in df_filtered.columns and 'Tags' in df_filtered.columns:
                for idx, row in df_filtered.iterrows():
                    if str(row.get('Status', '')).strip() == 'Completed':
                        tags = row.get('Tags')
                        if pd.isna(tags) or str(tags).strip() in ('', 'nan'):
                            continue
                        first_tag = str(tags).split(',')[0].strip()
                        if first_tag.startswith('공통업무'):
                            name = str(row.get('Name', '')).strip() or '미분류'
                            task_name = str(row.get('Task', ''))
                            task_display = task_name[:20] + "..." if len(task_name) > 20 else task_name
                            issue_msg = f"{name}님 태그 오류 : {task_display} (완료된 업무에 '공통업무' 태그 불가)"
                            if issue_msg not in status_completed_tag_issues:
                                status_completed_tag_issues.append(issue_msg)

            # 최종 4열: Name, Task, Tags, Time Spent
            final_columns = ['Name', 'Task', 'Tags', 'Time Spent']
            missing_columns = [col for col in final_columns if col not in df_filtered.columns]
            if missing_columns:
                return None, None, f"열을 찾을 수 없음: {missing_columns}", []

            final_df = df_filtered[final_columns].copy()

            # exclude_names에 포함된 이름은 CSV에서 제외
            exclude_names_for_csv = self.load_exclude_names()
            if exclude_names_for_csv:
                before = len(final_df)
                final_df = final_df[~final_df['Name'].isin(exclude_names_for_csv)]
                removed = before - len(final_df)
                if removed > 0:
                    print(f"✅ 제외 이름 필터링: {removed}행 제거 ({exclude_names_for_csv})")

            # 연차/반차류 행 자동 태그 처리
            # Tasklist가 연차 키워드인 행 → Task를 Tasklist 값으로, Tags를 "연차"로 설정
            leave_keywords = self.load_leave_keywords()
            leave_count = 0
            for idx in final_df.index:
                if idx in df.index and df.loc[idx, 'Tasklist'] in leave_keywords:
                    tasklist_val = df.loc[idx, 'Tasklist']
                    final_df.at[idx, 'Task'] = '사내행사' if tasklist_val == '행사공결' else tasklist_val
                    final_df.at[idx, 'Tags'] = '사내행사' if tasklist_val == '행사공결' else '연차'
                    leave_count += 1
            if leave_count > 0:
                print(f"✅ 연차/반차 자동 태그 처리: {leave_count}행")

            # 검증 (수동 입력 포함된 df로 검증)
            validation_issues = self.validate_csv_data(final_df.copy(), min_hours=MIN_REQUIRED_HOURS)
            # 담당자 없음 오류 추가
            if assigned_warnings:
                validation_issues = assigned_warnings + validation_issues
            # Status Completed + 공통업무 태그 오류 추가
            if status_completed_tag_issues:
                validation_issues = status_completed_tag_issues + validation_issues

            # 파일 저장
            output_file = OUTPUT_FILENAME
            if os.path.exists(output_file):
                os.remove(output_file)
            final_df.to_csv(output_file, index=False, header=False, encoding='utf-8-sig')
            print(f"✅ 파일 저장 완료: {output_file}")

            return final_df, removed_count, output_file, validation_issues

        except Exception as e:
            return None, None, f"CSV 처리 오류: {str(e)}", []

    def send_validation_report_to_slack(self, validation_issues, channel_env_var="SLACK_CHANNEL_VALIDATION"):
        """검증 결과를 슬랙에 전송 (파일 업로드 없이) - 오류가 있을 때만 전송"""
        if DISABLE_SLACK_NOTIFICATIONS:
            print("⏸️ 슬랙 노티 임시 비활성화 (테스트 중)")
            return True

        if not self.slack_client:
            return False
        
        # 오류가 없으면 아무것도 전송하지 않음
        if not validation_issues:
            return True
        
        try:
            validation_channel = os.getenv(channel_env_var, "#아트실")
            mentioned_people = self._extract_people_from_issues(validation_issues)
            message_text = f"[TU 검토] 아트실 오류 발견 ☠️"
            
            if mentioned_people:
                people_list = ", ".join(mentioned_people)
                message_text += f"\n🧨 확인 필요한 사람 : {people_list}"
                message_text += f"\n```[오류 내용 확인]"
                for issue in validation_issues:
                    message_text += f"\n- {issue}"
                message_text += f"```"

                msg_response = self.slack_client.chat_postMessage(
                    channel=validation_channel,
                    text=message_text
                )
                if msg_response.get('ok'):
                    return True
                else:
                    return False
            
        except Exception as e:
            return False

    def _extract_people_from_issues(self, validation_issues):
        """검증 오류에서 사람 이름 추출"""
        people = set()
        try:
            for issue in validation_issues:
                if "님" in issue:
                    parts = issue.split("님")
                    if len(parts) > 0:
                        name_part = parts[0].strip()
                        words = name_part.split()
                        if words:
                            name = words[-1]
                            if len(name) >= 2 and all('\uac00' <= char <= '\ud7a3' for char in name):
                                people.add(name)
            
            return list(people)
            
        except Exception as e:
            return []

    def run_validation_only(self, channel_env_var="SLACK_CHANNEL_VALIDATION"):
        """검증 전용 실행 (전체 프로세스와 동일하되 파일 업로드 없이 검증 결과만 슬랙 전송)"""
        try:
            # 환경변수에서 로그인 정보 읽기
            email = os.getenv("TU_EMAIL")
            password = os.getenv("TU_PASSWORD")
            workspace = None  # 아트실 고정, 환경변수 불필요
            
            if not email or not password:
                error_msg = "환경변수 필요: TU_EMAIL, TU_PASSWORD"
                self.send_validation_report_to_slack([error_msg], channel_env_var)
                return False
            
            # 1. 드라이버 설정
            if not self.setup_driver():
                error_msg = "브라우저 드라이버 설정 실패"
                self.send_validation_report_to_slack([error_msg], channel_env_var)
                return False
            
            # 2. 로그인
            if not self.login_to_taskworld(email, password):
                error_msg = "TU 인트라넷 로그인 실패"
                self.send_validation_report_to_slack([error_msg], channel_env_var)
                return False
            
            # 3. 아트실 이동
            if not self.navigate_to_workspace():
                error_msg = "아트실 통계 페이지 접속 실패"
                self.send_validation_report_to_slack([error_msg], channel_env_var)
                return False
            
            # 4. CSV 내보내기
            csv_file = self.export_csv()
            
            if not csv_file:
                error_msg = "CSV 다운로드 실패"
                self.send_validation_report_to_slack([error_msg], channel_env_var)
                return False
            
            # 5. CSV 처리 + 검증
            result_df, removed_count, processed_file, validation_issues = self.process_csv(csv_file)
            
            if result_df is None:
                error_msg = processed_file
                self.send_validation_report_to_slack([error_msg], channel_env_var)
                return False
            
            # 6. 검증 결과 터미널 출력 + 슬랙 전송
            if validation_issues:
                print(f"\n⚠️ 검증 이슈 {len(validation_issues)}개 발견:")
                for issue in validation_issues:
                    print(f"  - {issue}")
            else:
                print("\n✅ 검증 이슈 없음")
            success = self.send_validation_report_to_slack(validation_issues, channel_env_var)

            print(f"\n✅ 처리된 파일 로컬 저장: {processed_file}")
            print(f"📁 파일 위치: {os.path.abspath(processed_file)}")

            # 7. 파일 정리 없음 — 원본 + 처리된 파일 모두 유지 (검토용)
            print(f"📁 원본 파일: {os.path.abspath(csv_file)}")

            if success:
                return True
            else:
                return False
                
        except Exception as e:
            error_msg = f"검증 전용 프로세스 실패: {str(e)}"
            
            try:
                self.send_validation_report_to_slack([error_msg], channel_env_var)
            except:
                pass
            
            return False
            
        finally:
            if self.driver:
                self.driver.quit()

    def _dump_debug_info(self, driver, label):
        """실패 시 현재 URL/스크린샷/페이지 소스 일부를 남겨 원인 구분"""
        import re
        try:
            print(f"  🔎 [DEBUG:{label}] 현재 URL: {driver.current_url}")
            screenshot_path = f"debug_{label}.png"
            driver.save_screenshot(screenshot_path)
            print(f"  🔎 [DEBUG:{label}] 스크린샷 저장: {os.path.abspath(screenshot_path)}")

            source = driver.page_source
            err_match = re.search(r'ERR_[A-Z_]+', source)
            if err_match:
                print(f"  🔎 [DEBUG:{label}] ⚠️ 크롬 네트워크 에러 감지: {err_match.group()}")

            page_snippet = source[:4000].replace("\n", " ")
            print(f"  🔎 [DEBUG:{label}] page_source (최대 4000자): {page_snippet}")
            print(f"  🔎 [DEBUG:{label}] page_source 총 길이: {len(source)}자")
        except Exception as e:
            print(f"  🔎 [DEBUG:{label}] 디버그 정보 수집 실패: {e}")

    def upload_to_art_page(self, csv_file_path):
        """fbcweb.aceproject.co.kr/stats/ 에 CSV 파일 업로드 (Selenium, Basic Auth 불필요)"""
        art_driver = None
        try:
            print("🌐 통계 업로드 시작 (Selenium)...")

            from selenium.webdriver.chrome.options import Options as ChromeOptions
            art_options = ChromeOptions()
            if self.headless:
                art_options.add_argument("--headless")
            art_options.add_argument("--no-sandbox")
            art_options.add_argument("--disable-dev-shm-usage")
            art_options.add_argument("--disable-gpu")
            art_options.add_argument("--window-size=1920,1080")
            art_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            art_driver = webdriver.Chrome(options=art_options)

            # 1단계: /stats/ 페이지 이동 (Basic Auth 해제됨, 인증 정보 불필요)
            art_driver.get("https://fbcweb.aceproject.co.kr/stats/")
            time.sleep(3)
            print(f"  ✅ 페이지 이동 완료 (현재 URL: {art_driver.current_url})")

            # 2단계: 'CSV 업로드' 링크 클릭
            csv_upload_selectors = [
                "//a[@href='upload']",
                "//a[contains(@href, 'upload')]",
                "//*[contains(text(), 'CSV 업로드')]",
            ]
            csv_btn = None
            for selector in csv_upload_selectors:
                try:
                    csv_btn = WebDriverWait(art_driver, 8).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    break
                except:
                    continue

            if not csv_btn:
                print("  ❌ CSV 업로드 링크를 찾지 못함")
                self._dump_debug_info(art_driver, "csv_btn_not_found")
                return False

            try:
                csv_btn.click()
            except:
                art_driver.execute_script("arguments[0].click();", csv_btn)
            time.sleep(2)
            print(f"  ✅ CSV 업로드 링크 클릭 (현재 URL: {art_driver.current_url})")

            # 3단계: 파일 input에 파일 경로 전달
            abs_path = os.path.abspath(csv_file_path)
            file_input_selectors = [
                "//input[@id='fileInput']",
                "//input[@type='file']",
            ]
            file_input = None
            for selector in file_input_selectors:
                try:
                    file_input = WebDriverWait(art_driver, 8).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    break
                except:
                    continue

            if not file_input:
                print("  ❌ 파일 input 요소를 찾지 못함")
                self._dump_debug_info(art_driver, "file_input_not_found")
                return False

            art_driver.execute_script("arguments[0].style.display = 'block';", file_input)
            file_input.send_keys(abs_path)
            time.sleep(2)
            print(f"  ✅ 파일 선택 완료: {os.path.basename(abs_path)}")

            # 4단계: 업로드 버튼 클릭 (파일 선택 후 JS가 주기를 자동 감지해야 disabled가 풀림)
            upload_btn_selectors = [
                "//button[@id='submitBtn']",
                "//button[contains(text(), '업로드')]",
            ]
            upload_btn = None
            for selector in upload_btn_selectors:
                try:
                    upload_btn = WebDriverWait(art_driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    break
                except:
                    continue

            if not upload_btn:
                try:
                    disabled_btn = art_driver.find_element(By.XPATH, "//button[@id='submitBtn']")
                    print(f"  ❌ 업로드 버튼이 비활성화 상태로 남아있음, disabled={disabled_btn.get_attribute('disabled')}")
                except:
                    print("  ❌ 업로드 버튼을 찾지 못함")
                self._dump_debug_info(art_driver, "upload_btn_not_found")
                return False

            try:
                upload_btn.click()
            except:
                art_driver.execute_script("arguments[0].click();", upload_btn)
            time.sleep(3)
            print(f"  ✅ 업로드 버튼 클릭 완료 (현재 URL: {art_driver.current_url})")

            print("✅ 통계 업로드 완료!")
            return True

        except Exception as e:
            import traceback
            print(f"❌ 통계 업로드 실패: {e}")
            print(traceback.format_exc())
            return False

        finally:
            if art_driver:
                art_driver.quit()

    def send_to_slack(self, csv_file_path, stats=None, error_message=None, validation_issues=None):
        """슬랙에 리포트 전송 (파일 업로드 + 메시지)"""
        if DISABLE_SLACK_NOTIFICATIONS:
            print("⏸️ 슬랙 노티 임시 비활성화 (테스트 중)")
            return True

        if not self.slack_client:
            return False
        
        try:
            # 1. 기본 인증 확인
            auth_response = self.slack_client.auth_test()
            if not auth_response.get('ok'):
                return False
            
            # 2. 채널 ID 확보
            actual_channel_id = self.slack_channel
            if self.slack_channel.startswith('#'):
                channel_name = self.slack_channel[1:]
                try:
                    conversations = self.slack_client.conversations_list(limit=1000)
                    if conversations.get('ok'):
                        channels = conversations.get('channels', [])
                        found_channel = next((ch for ch in channels if ch['name'] == channel_name), None)
                        if found_channel:
                            actual_channel_id = found_channel['id']
                except Exception as e:
                    pass
            
            # 3. 메시지 전송
            today = datetime.now(self.korea_tz).strftime("%Y-%m-%d")
            message_text = f"[{today}] TU 인트라넷 리포트 (아트실)"

            if error_message:
                message_text += f"\n❌ 오류 발생: `{error_message}`"
            elif validation_issues:
                message_text += f"\n⚠️ 검증 오류 발견으로 통계 CSV가 업데이트 되지 않습니다."
                message_text += f"\n```"
                message_text += f"\n[검증 오류]"
                for issue in validation_issues:
                    message_text += f"\n- {issue}"
                message_text += f"\n```"
            else:
                message_text += f"\n✅ 통계 CSV 업데이트 완료"

            msg_response = self.slack_client.chat_postMessage(
                channel=actual_channel_id,
                text=message_text
            )

            if not msg_response.get('ok'):
                return False

            return True
        
        except Exception as e:
            return False

    def _send_upload_error_thread(self, channel, thread_ts, filename, error_detail, full_response):
        """파일 업로드 실패 시 스레드에 상세 오류 정보 전송"""
        try:
            thread_text = f"파일 업로드 실패 상세 정보\n\n"
            thread_text += f"파일명: `{filename}`\n"
            thread_text += f"오류: {error_detail}\n"
            
            if full_response:
                if 'needed' in full_response:
                    thread_text += f"필요한 권한: {full_response.get('needed')}\n"
                if 'provided' in full_response:
                    thread_text += f"현재 권한: {full_response.get('provided')}\n"
            
            thread_text += f"\n파일은 서버에 생성되었으니 수동으로 업로드 가능합니다."
            
            self.slack_client.chat_postMessage(
                channel=channel,
                text=thread_text,
                thread_ts=thread_ts
            )
            
        except Exception as e:
            pass


    def export_csv(self):
        """TU 인트라넷 통계 페이지에서 'Taskworld 내보내기' 버튼 클릭 → CSV 다운로드"""
        try:
            # 다운로드 전 기존 CSV 파일 목록 저장 및 정리
            export_files = glob.glob(os.path.join(self.download_dir, "export-projects*.csv"))
            for file in export_files:
                try:
                    os.remove(file)
                except:
                    pass
            
            existing_csvs = set(glob.glob(os.path.join(self.download_dir, "*.csv")))
            
            time.sleep(2)
            
            # 'Taskworld 내보내기' 버튼 찾기
            print("🔍 'Taskworld 내보내기' 버튼 탐색 중...")
            tw_export_selectors = [
                "//button[contains(text(), 'Taskworld 내보내기')]",
                "//a[contains(text(), 'Taskworld 내보내기')]",
                "//span[contains(text(), 'Taskworld 내보내기')]",
                "//*[contains(text(), 'Taskworld 내보내기')]",
                "//button[contains(text(), 'Taskworld')]",
                "//*[contains(text(), 'Taskworld') and contains(text(), '내보내기')]",
            ]
            
            export_btn = None
            for selector in tw_export_selectors:
                try:
                    export_btn = WebDriverWait(self.driver, 8).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    print(f"✅ 'Taskworld 내보내기' 버튼 발견: {selector}")
                    break
                except:
                    continue
            
            if not export_btn:
                print("❌ 'Taskworld 내보내기' 버튼을 찾지 못함")
                return None
            
            # 1차: 일반 클릭
            try:
                export_btn.click()
                print("✅ 버튼 클릭 (일반)")
            except:
                pass
            
            time.sleep(2)
            
            # 2차: JavaScript 강제 클릭
            try:
                self.driver.execute_script("arguments[0].click();", export_btn)
                print("✅ 버튼 클릭 (JavaScript)")
            except:
                pass
            
            time.sleep(2)
            
            # 다운로드 완료 대기 (최대 120초)
            print("⏳ CSV 다운로드 대기 중...")
            timeout = 120
            check_interval = 2
            
            for i in range(0, timeout, check_interval):
                # 현재 폴더에서 새 CSV 확인
                current_csvs = set(glob.glob(os.path.join(self.download_dir, "*.csv")))
                new_csvs = current_csvs - existing_csvs
                
                if new_csvs:
                    latest_file = max(new_csvs, key=os.path.getctime)
                    if os.path.getsize(latest_file) > 0:
                        print(f"✅ CSV 다운로드 완료: {os.path.basename(latest_file)}")
                        return latest_file
                
                # Downloads 폴더도 확인
                downloads_pattern = os.path.expanduser("~/Downloads/export-projects*.csv")
                downloads_csvs = glob.glob(downloads_pattern)
                if downloads_csvs:
                    latest_download = max(downloads_csvs, key=os.path.getctime)
                    if time.time() - os.path.getmtime(latest_download) < 600:
                        import shutil
                        local_file = os.path.basename(latest_download)
                        shutil.copy(latest_download, local_file)
                        try:
                            os.remove(latest_download)
                        except:
                            pass
                        print(f"✅ CSV 다운로드 완료 (Downloads 폴더): {local_file}")
                        return local_file
                
                # .crdownload 확인 (다운로드 중)
                if glob.glob(os.path.join(self.download_dir, "*.crdownload")):
                    pass  # 아직 다운로드 중
                elif i % 20 == 0 and i > 0:
                    print(f"  ⏳ {i}초 경과, 계속 대기 중...")
                
                time.sleep(check_interval)
            
            print("❌ CSV 다운로드 타임아웃 (120초 초과)")
            return None
            
        except Exception as e:
            print(f"❌ CSV 내보내기 실패: {e}")
            return None

    def run_complete_automation(self, email, password):
        """완전 자동화 프로세스 실행: 다운로드 → 처리 → 슬랙 전송"""
        try:
            print("🚀 완전 자동화 프로세스 시작")
            print("=" * 60)
            
            # 1. 드라이버 설정
            print("1️⃣ 드라이버 설정...")
            if not self.setup_driver():
                error_msg = "브라우저 드라이버 설정 실패"
                self.send_to_slack(None, None, error_msg)
                return None
            
            # 2. 로그인
            print("\n2️⃣ 로그인...")
            if not self.login_to_taskworld(email, password):
                error_msg = "TU 인트라넷 로그인 실패"
                self.send_to_slack(None, None, error_msg)
                return None
            
            # 3. 워크스페이스 이동
            print("\n3️⃣ 아트실 이동...")
            if not self.navigate_to_workspace():
                error_msg = "아트실 통계 페이지 접속 실패"
                self.send_to_slack(None, None, error_msg)
                return None
            
            # 4. CSV 내보내기
            print("\n4️⃣ CSV 내보내기...")
            csv_file = self.export_csv()
            
            if not csv_file:
                error_msg = "CSV 다운로드 실패"
                self.send_to_slack(None, None, error_msg)
                return None
            
            print(f"\n✅ TU CSV 다운로드 완료: {csv_file}")

            # 5. CSV 처리 + 검증 (Due Date 체크 제외)
            print("\n5️⃣ CSV 파일 처리 및 검증...")
            result_df, removed_count, processed_file, validation_issues = self.process_csv(csv_file)
            
            if result_df is None:
                error_msg = processed_file
                self.send_to_slack(None, None, error_msg)
                return None
            
            print(f"✅ CSV 처리 완료: {processed_file}")
            
            # 검증 결과 표시
            if validation_issues:
                print(f"⚠️ 검증 이슈 {len(validation_issues)}개 발견:")
                for issue in validation_issues:
                    print(f"  - {issue}")
            else:
                print("✅ 모든 데이터 검증 통과")
            
            
            # 6. art 페이지 CSV 업로드 — 검증 오류 있으면 건너뜀
            print("\n6️⃣ art 페이지 CSV 업로드...")
            today_str = datetime.now(self.korea_tz).strftime("%Y-%m-%d")

            if validation_issues:
                print("⚠️ 검증 오류 있음 — art 업로드 건너뜀, 슬랙에 수동 업데이트 요청")
                art_success = False
                art_skipped = True
            else:
                art_skipped = False
                art_success = self.upload_to_art_page(processed_file)
                if art_success:
                    print("✅ art 페이지 업로드 완료!")
                else:
                    print("❌ 통계 업로드 실패 — 슬랙에 오류 알림")

            # 7. 슬랙 노티 — 오류/실패 시에만 전송
            print("\n7️⃣ 슬랙 노티 확인...")
            needs_notify = art_skipped or not art_success

            if not needs_notify:
                print("✅ 오류 없음 — 슬랙 노티 생략")
            else:
                # 검증 오류 담당자 추출 (이름 → 슬랙 태그)
                if art_skipped and validation_issues:
                    # 오류 담당자 이름 추출
                    error_names = set()
                    for issue in validation_issues:
                        if '님' in issue:
                            name_part = issue.split('님')[0].strip().split()[-1]
                            error_names.add(name_part)

                    people_list = ", ".join(sorted(error_names))
                    notify_msg = f"[{today_str}] ⚠️ 검증 오류 발견 — 확인 후 수동 업데이트 해주세요."
                    if people_list:
                        notify_msg += f"\n🧨 확인 필요한 사람 : {people_list}"
                    notify_msg += "\n```\n[검증 오류]"
                    for issue in validation_issues:
                        notify_msg += f"\n- {issue}"
                    notify_msg += "\n```"
                else:
                    notify_msg = f"[{today_str}] ❌ 통계 업로드 실패"

                print(notify_msg)

                if self.slack_client:
                    success = self.send_to_slack(
                        None, None,
                        None if art_skipped else "통계 업로드 실패",
                        validation_issues if art_skipped else None
                    )
                    if success:
                        print("✅ 슬랙 노티 전송 완료!")
                    else:
                        print("❌ 슬랙 전송 실패")
                else:
                    print("⚠️ 슬랙 토큰이 없어 전송을 건너뜁니다.")
            
            # 8. 파일 정리
            print("\n8️⃣ 파일 정리...")
            try:
                # 원본 파일 삭제 (처리된 파일만 남김)
                if os.path.exists(csv_file):
                    os.remove(csv_file)
                    print(f"🗑️ 원본 파일 삭제: {os.path.basename(csv_file)}")
                
                # Downloads 폴더의 export-projects 관련 파일들도 정리
                downloads_pattern = os.path.expanduser("~/Downloads/export-projects*.csv")
                downloads_files = glob.glob(downloads_pattern)
                for file in downloads_files:
                    try:
                        os.remove(file)
                        print(f"🗑️ Downloads 파일 삭제: {os.path.basename(file)}")
                    except:
                        pass
                
                print(f"📁 최종 파일: {processed_file}")
                print(f"📂 파일 위치: {os.path.abspath(processed_file)}")
                if os.path.exists(processed_file):
                    file_size = os.path.getsize(processed_file)
                    print(f"📊 파일 정보: {file_size} 바이트")
                    print(f"💡 슬랙 업로드가 실패했다면 위 파일을 수동으로 업로드하세요.")
                print("✅ 파일 정리 완료 - 처리된 파일만 보존")
            except Exception as e:
                print(f"⚠️ 파일 정리 실패: {e}")
            
            print(f"\n🎉 완전 자동화 프로세스 완료!")
            print(f"📁 최종 파일: {processed_file}")
            return processed_file
                
        except Exception as e:
            error_msg = f"완전 자동화 프로세스 실패: {str(e)}"
            print(f"\n❌ {error_msg}")
            self.send_to_slack(None, None, error_msg)
            return None
            
        finally:
            # 브라우저 종료 (headless=False일 때는 5초 대기)
            if not self.headless:
                print("\n⏳ 브라우저 확인을 위해 5초 후 종료...")
                time.sleep(5)
            
            if self.driver:
                self.driver.quit()
                print("🔚 브라우저 종료")
            

if __name__ == "__main__":
    import sys
    
    print("🔍 환경변수 확인:")
    print(f"📧 TU_EMAIL: {'설정됨' if os.getenv('TU_EMAIL') else '❌ 없음'}")
    print(f"🔒 TU_PASSWORD: {'설정됨' if os.getenv('TU_PASSWORD') else '❌ 없음'}")
    print(f"🤖 SLACK_BOT_TOKEN: {'설정됨' if os.getenv('SLACK_BOT_TOKEN') else '❌ 없음'}")
    print(f"💬 SLACK_CHANNEL: {os.getenv('SLACK_CHANNEL', '❌ 없음')}")
    print(f"💬 SLACK_CHANNEL_VALIDATION: {os.getenv('SLACK_CHANNEL_VALIDATION', '❌ 없음')}")
    
    print(f"\n🔍 설정값 확인:")
    print(f"📄 출력 파일명: {OUTPUT_FILENAME}")
    print(f"⏱️ 최소 필수 시간: {MIN_REQUIRED_HOURS}시간")
    
    # 실행 모드 확인
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    
    if mode == "validation":
        # 검증 전용 모드
        print("🔍 검증 전용 모드로 실행")
        downloader = TaskworldSeleniumDownloader(headless=True)
        result = downloader.run_validation_only()
        
        if not result:
            exit(1)
    else:
        # 기존 전체 프로세스 모드
        print("🚀 전체 프로세스 모드로 실행")
        
        # 환경변수에서 로그인 정보 읽기
        email = os.getenv("TU_EMAIL")
        password = os.getenv("TU_PASSWORD")
        
        if not email or not password:
            print("❌ 환경변수 필요: TU_EMAIL, TU_PASSWORD")
            exit(1)
        
        downloader = TaskworldSeleniumDownloader(headless=DEFAULT_HEADLESS)
        result = downloader.run_complete_automation(email, password)
        
        if result:
            print(f"📁 최종 파일: {result}")
        else:
            print("\n❌ 실패")
            exit(1)
