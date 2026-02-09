# selenium_taskworld_downloader.py - 완전 자동화 스크립트 (정리된 버전)
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
# 월별 설정 변수 (매월 수정 필요)
# ==========================================
WORKSPACE_NAME = "아트실 일정 - 2026 1주기"  # 한달마다 수정하세요!
OUTPUT_FILENAME = "26_1.csv"  # 한달마다 수정하세요! (예: 25_7.csv, 25_8.csv)

# ==========================================
# 검증 설정 변수 (필요시 수정)
# ==========================================
MIN_REQUIRED_HOURS = 256  # 필요시 수정하세요! (개인별 최소 시간)

# ==========================================
# 파일 경로 설정
# ==========================================
FIRST_TAGS_REQUIRED_ART_FILE = "first_tags_required_second_art.txt"
FIRST_TAGS_REQUIRED_PROJECT_FILE = "first_tags_required_second_project.txt"
FIRST_TAGS_OPTIONAL_SECOND_FILE = "first_tags_optional_second.txt"
SECOND_TAGS_ART_FILE = "second_tags_art.txt"
SECOND_TAGS_PROJECT_FILE = "second_tags_project.txt"
EXCLUDE_VALUES_FILE = "exclude_values.txt"

# ==========================================
# 기타 설정
# ==========================================
DEFAULT_HEADLESS = True

logger = logging.getLogger(__name__)


class TaskworldSeleniumDownloader:
    def __init__(self, headless=DEFAULT_HEADLESS):
        """
        Selenium 기반 태스크월드 자동 다운로더 + CSV 처리 + 슬랙 전송
        
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
        
        print(f"🤖 완전 자동화 다운로더 초기화 - headless: {headless}")
        print(f"📂 대상 워크스페이스: {WORKSPACE_NAME}")
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
    
    def login_to_taskworld(self, email, password):
        """태스크월드 로그인"""
        try:
            print("🔍 태스크월드 로그인 시작...")
            
            self.driver.get("https://asia-enterprise.taskworld.com/login")
            time.sleep(3)
            
            return self._handle_email_login(email, password)
                    
        except Exception as e:
            print(f"❌ 로그인 전체 프로세스 실패: {e}")
            return False
    
    def _handle_email_login(self, email, password):
        """일반 이메일 로그인 처리"""
        try:
            print("📧 일반 이메일 로그인 시작...")
            
            # 이메일 입력
            email_input = self.wait.until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            email_input.clear()
            email_input.send_keys(email)
            
            # 패스워드 입력
            password_input = self.driver.find_element(By.NAME, "password")
            password_input.clear()
            password_input.send_keys(password)
            
            # 로그인 버튼 클릭
            login_btn = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_btn.click()
            
            # 로그인 완료 대기
            time.sleep(5)
            
            print("✅ 이메일 로그인 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 이메일 로그인 실패: {e}")
            return False
    
    def navigate_to_workspace(self, workspace_name=WORKSPACE_NAME):
        """스마트 대기 시스템이 적용된 워크스페이스 이동"""
        try:
            print(f"📂 워크스페이스 '{workspace_name}' 찾기 시작...")
            
            max_attempts = 3
            
            for attempt in range(1, max_attempts + 1):
                print(f"\n🔄 시도 {attempt}/{max_attempts}")
                
                if not self._wait_for_page_ready():
                    print(f"❌ 시도 {attempt}: 페이지 로딩 대기 실패")
                    continue
                
                if not self._navigate_to_projects_with_smart_wait():
                    print(f"❌ 시도 {attempt}: 프로젝트 페이지 이동 실패")
                    continue
                
                if not self._click_all_projects_tab():
                    print(f"⚠️ 시도 {attempt}: 전체 프로젝트 탭 클릭 실패, 현재 상태로 진행...")
                
                if not self._wait_for_workspace_list_loaded():
                    print(f"❌ 시도 {attempt}: 워크스페이스 목록 로딩 실패")
                    continue
                
                if self._find_workspace_with_smart_search(workspace_name):
                    print(f"✅ 시도 {attempt}: 워크스페이스 접속 성공!")
                    return True
                
                print(f"❌ 시도 {attempt}: 워크스페이스 찾기 실패")
                if attempt < max_attempts:
                    print("🔄 페이지 새로고침 후 재시도...")
                    self.driver.refresh()
                    time.sleep(2)
            
            print("❌ 모든 시도 실패")
            return False
            
        except Exception as e:
            print(f"❌ 워크스페이스 접속 중 오류: {e}")
            return False

    def _wait_for_page_ready(self, timeout=20):
        """페이지가 완전히 준비될 때까지 스마트 대기"""
        try:
            print("⏳ 페이지 완전 로딩 대기...")
            
            # DOM 로딩 완료 대기
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # jQuery 로딩 완료 대기 (있는 경우)
            try:
                WebDriverWait(self.driver, 5).until(
                    lambda driver: driver.execute_script("return typeof jQuery !== 'undefined' && jQuery.active == 0")
                )
            except:
                pass
            
            # 기본 body 요소 존재 확인
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            return True
            
        except Exception as e:
            print(f"❌ 페이지 로딩 대기 실패: {e}")
            return False

    def _navigate_to_projects_with_smart_wait(self):
        """스마트 대기를 적용한 프로젝트 페이지 이동"""
        try:
            current_url = self.driver.current_url
            
            # 방법 1: URL 직접 수정
            if "#/home" in current_url:
                project_url = current_url.replace("#/home", "#/projects")
                self.driver.get(project_url)
                
                try:
                    WebDriverWait(self.driver, 15).until(
                        lambda driver: "#/projects" in driver.current_url
                    )
                    return True
                except:
                    pass
            
            # 방법 2: 네비게이션 메뉴 찾기
            nav_selectors = [
                "//a[contains(@href, 'projects')]",
                "//button[contains(text(), 'Projects')]",
                "//div[contains(text(), 'Projects')]",
                "//nav//a[contains(text(), 'Project')]",
                "//*[@data-testid='projects-nav']"
            ]
            
            for selector in nav_selectors:
                try:
                    nav_element = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    nav_element.click()
                    
                    WebDriverWait(self.driver, 10).until(
                        lambda driver: "projects" in driver.current_url.lower() or
                                     len(driver.find_elements(By.XPATH, "//*[contains(text(), 'workspace') or contains(text(), 'project')]")) > 0
                    )
                    return True
                    
                except:
                    continue
            
            # 방법 3: 강제 URL 구성
            base_url = current_url.split("#/")[0] if "#/" in current_url else current_url
            project_url = base_url + "#/projects"
            self.driver.get(project_url)
            
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda driver: len(driver.find_elements(By.TAG_NAME, "a")) > 5
                )
                return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"❌ 프로젝트 페이지 이동 실패: {e}")
            return False

    def _click_all_projects_tab(self):
        """전체 프로젝트 탭 클릭"""
        try:
            tab_selectors = [
                "//button[contains(text(), '전체 프로젝트')]",
                "//a[contains(text(), '전체 프로젝트')]",
                "//div[contains(text(), '전체 프로젝트')]",
                "//span[contains(text(), '전체 프로젝트')]",
                "//*[contains(text(), '전체') and contains(text(), '프로젝트')]",
                "//button[contains(text(), 'All Projects')]",
                "//a[contains(text(), 'All Projects')]",
                "//*[@data-tab='all' or @data-tab='active']",
                "//*[contains(@class, 'tab') and contains(text(), '전체')]",
                "//li[contains(text(), '전체 프로젝트')]",
                "//*[@role='tab' and contains(text(), '전체')]",
                "//nav//*[contains(text(), '전체 프로젝트')]"
            ]
            
            for selector in tab_selectors:
                try:
                    tab_element = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    
                    try:
                        tab_element.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", tab_element)
                    
                    WebDriverWait(self.driver, 5).until(
                        lambda driver: len(driver.find_elements(By.XPATH, "//a | //div")) > 5
                    )
                    return True
                    
                except:
                    continue
            
            return False
            
        except Exception as e:
            print(f"❌ 전체 프로젝트 탭 클릭 실패: {e}")
            return False

    def _wait_for_workspace_list_loaded(self, timeout=20):
        """워크스페이스 목록이 실제로 로딩될 때까지 스마트 대기"""
        try:
            # 로딩 스피너가 사라질 때까지 대기
            try:
                WebDriverWait(self.driver, 10).until_not(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(@class, 'loading') or contains(@class, 'spinner')]"))
                )
            except:
                pass
            
            # 워크스페이스/프로젝트 관련 요소가 나타날 때까지 대기
            workspace_indicators = [
                "//*[contains(text(), 'workspace')]",
                "//*[contains(text(), 'project')]",
                "//a[contains(@href, 'project')]",
                "//*[@class*='workspace']",
                "//*[@class*='project']"
            ]
            
            for indicator in workspace_indicators:
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, indicator))
                    )
                    break
                except:
                    continue
            
            # 실제 클릭 가능한 링크들이 최소 개수 이상 로딩될 때까지 대기
            WebDriverWait(self.driver, timeout).until(
                lambda driver: len(driver.find_elements(By.XPATH, "//a[@href]")) >= 3
            )
            
            return True
            
        except Exception as e:
            print(f"❌ 워크스페이스 목록 로딩 대기 실패: {e}")
            return False

    def _find_workspace_with_smart_search(self, workspace_name):
        """정확 매치만 사용하는 안전한 워크스페이스 검색"""
        try:
            exact_selectors = [
                f"//a[contains(text(), '{workspace_name}')]",
                f"//div[contains(text(), '{workspace_name}')]",
                f"//span[contains(text(), '{workspace_name}')]",
                f"//button[contains(text(), '{workspace_name}')]",
                f"//h1[contains(text(), '{workspace_name}')]",
                f"//h2[contains(text(), '{workspace_name}')]",
                f"//h3[contains(text(), '{workspace_name}')]",
                f"//td[contains(text(), '{workspace_name}')]",
                f"//li[contains(text(), '{workspace_name}')]",
                f"//*[@title='{workspace_name}']",
                f"//*[contains(@aria-label, '{workspace_name}')]",
                f"//*[text()='{workspace_name}']",
                f"//*[contains(text(), '{workspace_name}')]"
            ]
            
            workspace_link = self._try_selectors_with_smart_wait(exact_selectors, "정확 매치")
            if workspace_link:
                try:
                    element_text = workspace_link.text.strip()
                    if workspace_name in element_text:
                        return self._click_workspace_safely(workspace_link)
                    else:
                        print(f"❌ 텍스트 불일치: 예상 '{workspace_name}', 실제 '{element_text}'")
                except:
                    print("❌ 요소 텍스트 확인 실패")
            
            # 실패 시 디버깅 정보 출력
            try:
                all_elements = self.driver.find_elements(By.XPATH, "//a | //div | //span")
                workspace_candidates = []
                
                for element in all_elements:
                    try:
                        text = element.text.strip()
                        if text and len(text) > 5:
                            if any(keyword in text for keyword in ["아트실", "팀", "프로젝트", "주기", "2025", "2024"]):
                                workspace_candidates.append(text)
                    except:
                        continue
                
                unique_candidates = list(set(workspace_candidates))[:15]
                for i, candidate in enumerate(unique_candidates):
                    print(f"  {i+1}: {candidate}")
                    
            except Exception as debug_error:
                print(f"  디버깅 정보 수집 실패: {debug_error}")
            
            return False
            
        except Exception as e:
            print(f"❌ 워크스페이스 검색 실패: {e}")
            return False

    def _try_selectors_with_smart_wait(self, selectors, search_type):
        """스마트 대기를 적용한 셀렉터 시도"""
        for selector in selectors:
            try:
                element = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                return element
            except:
                continue
        
        return None

    def _click_workspace_safely(self, workspace_element):
        """안전한 워크스페이스 클릭"""
        try:
            # 1차: 일반 클릭
            try:
                workspace_element.click()
            except:
                # 2차: JavaScript 클릭
                self.driver.execute_script("arguments[0].click();", workspace_element)
            
            # 워크스페이스 로딩 확인
            WebDriverWait(self.driver, 15).until(
                lambda driver: driver.current_url != self.driver.current_url or
                              len(driver.find_elements(By.XPATH, "//*[contains(@class, 'task') or contains(@class, 'project')]")) > 0
            )
            
            return True
            
        except Exception as e:
            print(f"❌ 워크스페이스 클릭 실패: {e}")
            return False
    
    def load_allowed_tags(self):
        """허용된 태그 목록 파일에서 로드 - 아트/프로젝트 구조"""
        try:
            # 아트 그룹 첫 번째 태그 (두 번째 태그 필수)
            try:
                with open(FIRST_TAGS_REQUIRED_ART_FILE, 'r', encoding='utf-8') as f:
                    first_tags_required_art = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            except FileNotFoundError:
                default_art = ["cpm", "9up", "c-"]
                with open('first_tags_required_second_art.txt', 'w', encoding='utf-8') as f:
                    f.write("# 아트 그룹: 두 번째 태그가 반드시 있어야 하는 첫 번째 태그들\n")
                    f.write("# 한 줄에 하나씩, 주석은 #으로 시작\n\n")
                    for tag in default_art:
                        f.write(f"{tag}\n")
                first_tags_required_art = default_art

            # 프로젝트 그룹 첫 번째 태그 (두 번째 태그 필수)
            try:
                with open('first_tags_required_second_project.txt', 'r', encoding='utf-8') as f:
                    first_tags_required_project = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            except FileNotFoundError:
                default_project = ["a1", "실업무", "9-"]
                with open('first_tags_required_second_project.txt', 'w', encoding='utf-8') as f:
                    f.write("# 프로젝트 그룹: 두 번째 태그가 반드시 있어야 하는 첫 번째 태그들\n")
                    f.write("# 한 줄에 하나씩, 주석은 #으로 시작\n\n")
                    for tag in default_project:
                        f.write(f"{tag}\n")
                first_tags_required_project = default_project
            
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

    def validate_tags(self, df, first_tags_required_art, first_tags_required_project, first_tags_optional_second, second_tags_art, second_tags_project):
        """C열 태그 검증 - 개선된 로직"""
        
        first_tags_required_second = first_tags_required_art + first_tags_required_project
        second_tags = second_tags_art + second_tags_project
        
        tag_validation_issues = []
        
        try:
            if 'Tags' not in df.columns:
                tag_validation_issues.append("Tags 열이 존재하지 않습니다.")
                return tag_validation_issues
            
            # 전체 허용된 첫 번째 태그 목록
            all_first_tags = first_tags_required_second + first_tags_optional_second
            
            # 각 행별로 태그 검증
            for idx, row in df.iterrows():
                person_name = row['Tasklist']
                tags = row['Tags']
                task_name = row['Task']
                task_display = str(task_name)[:20] + "..." if len(str(task_name)) > 20 else str(task_name)
                    
                # 태그가 비어있거나 NaN인 경우 오류 추가
                if pd.isna(tags) or tags == '' or tags == 0:
                    issue_msg = f"{person_group}님 태그 오류 : {task_display} (태그 없음)"
                    if issue_msg not in tag_validation_issues:
                        tag_validation_issues.append(issue_msg)
                    continue
                
                # 이름 그룹핑 (기존 로직과 동일)
                if pd.isna(person_name) or person_name == '':
                    person_group = '미분류'
                else:
                    name_str = str(person_name).strip()
                    person_group = name_str[:3] if len(name_str) >= 3 else name_str
                
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
            
            # 열 이름 설정 (원본 19열 그대로 유지)
            original_columns = ['Project', 'Tasklist', 'Task', 'Description', 'Assigned To', 'Followers',
                              'Creation Date', 'Completion Date', 'Start Date', 'Due Date', 'Tags',
                              'Status', 'Points', 'Time Spent', 'Checklist', 'Comments', 'Files',
                              'Subtask', 'Subtask Reference ID']
            
            # 실제 컬럼 수에 맞게 조정
            if len(df.columns) > len(original_columns):
                for i in range(len(original_columns), len(df.columns)):
                    original_columns.append(f'Col_{i+1}')

                df.columns = original_columns[:len(df.columns)]
            else:
                essential_columns = ['Tasklist', 'Task', 'Tags', 'Time_Spent']
                if len(df.columns) >= 4:
                    df.columns = essential_columns + [f'Col_{i}' for i in range(4, len(df.columns))]
                else:
                    print(f"컬럼 수 부족: {len(df.columns)}개")
            
            # 1. 태그 설정 로드
            first_tags_required_art, first_tags_required_project, first_tags_optional_second, second_tags_art, second_tags_project = self.load_allowed_tags()
            
            # 2. 시간 검증
            validation_issues = self._validate_time_totals(df, min_hours)
            
            # 3. 태그 검증
            tag_issues = self.validate_tags(df, first_tags_required_art, first_tags_required_project, first_tags_optional_second, second_tags_art, second_tags_project)
            
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
    
    def _validate_time_totals(self, df, min_hours):
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
        
        def get_name_group(tasklist_name):
            """이름 앞 3글자로 그룹핑"""
            if pd.isna(tasklist_name) or tasklist_name == '':
                return '미분류'
            
            name_str = str(tasklist_name).strip()
            if len(name_str) >= 3:
                return name_str[:3]
            else:
                return name_str
        
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
        
        # 이름 그룹 생성
        df['Name_Group'] = df['Tasklist'].apply(get_name_group)
        
        # 그룹별 시간 합계 계산
        group_totals = df.groupby('Name_Group')['Time_Hours'].sum()
        
        # 각 그룹별 검증
        for name_group, total_hours in group_totals.items():
            total_hours = round(total_hours, 1)
            
            if total_hours != min_hours:
                issue_msg = f"{name_group}님 합산 오류 (현재: {total_hours}시간, 기준: {min_hours}시간)"
                validation_issues.append(issue_msg)
        
        return validation_issues
    
    def process_csv(self, input_file, columns=['Tasklist', 'Task', 'Tags', 'Time Spent']):
        """CSV 파일 처리 - 검증용 열 제외하고 최종 파일 저장"""
        try:
            # CSV 읽기
            df = pd.read_csv(input_file)
            original_count = len(df)
            
            # 제외값 필터링
            exclude_values = self.load_exclude_values()
            if 'Tasklist' in df.columns:
                df_filtered = df[~df['Tasklist'].isin(exclude_values)]
                removed_count = original_count - len(df_filtered)
            else:
                df_filtered = df
                removed_count = 0
            
            # 검증 (원본 19열 데이터로 검증)
            validation_issues = self.validate_csv_data(df_filtered.copy(), min_hours=MIN_REQUIRED_HOURS)
            
            # 열 선택 (최종 파일용 4열만)
            final_columns = ['Tasklist', 'Task', 'Tags', 'Time Spent']
            missing_columns = [col for col in final_columns if col not in df_filtered.columns]
            if missing_columns:
                return None, None, f"열을 찾을 수 없음: {missing_columns}", []
            
            selected_df = df_filtered[final_columns]
            
            # 최종 파일 저장 시에는 4개 열만 저장
            final_df = selected_df[['Tasklist', 'Task', 'Tags', 'Time Spent']]
            
            # 파일 저장
            output_file = OUTPUT_FILENAME
            if os.path.exists(output_file):
                os.remove(output_file)
            
            final_df.to_csv(output_file, index=False, header=False, encoding='utf-8-sig')
            
            return selected_df, removed_count, output_file, validation_issues
            
        except Exception as e:
            return None, None, f"CSV 처리 오류: {str(e)}", []

    def send_validation_report_to_slack(self, validation_issues, channel_env_var="SLACK_CHANNEL_VALIDATION"):
        """검증 결과를 슬랙에 전송 (파일 업로드 없이) - 오류가 있을 때만 전송"""
        if not self.slack_client:
            return False
        
        # 오류가 없으면 아무것도 전송하지 않음
        if not validation_issues:
            return True
        
        try:
            validation_channel = os.getenv(channel_env_var, "#아트실")
            mentioned_people = self._extract_people_from_issues(validation_issues)
            message_text = f"[태스크월드 검토] {WORKSPACE_NAME} 오류 발견 ☠️"
            
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
            email = os.getenv("TASKWORLD_EMAIL")
            password = os.getenv("TASKWORLD_PASSWORD")
            workspace = os.getenv("TASKWORLD_WORKSPACE", WORKSPACE_NAME)
            
            if not email or not password:
                error_msg = "환경변수 필요: TASKWORLD_EMAIL, TASKWORLD_PASSWORD"
                self.send_validation_report_to_slack([error_msg], channel_env_var)
                return False
            
            # 1. 드라이버 설정
            if not self.setup_driver():
                error_msg = "브라우저 드라이버 설정 실패"
                self.send_validation_report_to_slack([error_msg], channel_env_var)
                return False
            
            # 2. 로그인
            if not self.login_to_taskworld(email, password):
                error_msg = "태스크월드 로그인 실패"
                self.send_validation_report_to_slack([error_msg], channel_env_var)
                return False
            
            # 3. 워크스페이스 이동
            if not self.navigate_to_workspace(workspace):
                error_msg = f"워크스페이스 '{workspace}' 접속 실패"
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
            
            # 6. 검증 결과 슬랙 전송 (파일 업로드 없음)
            success = self.send_validation_report_to_slack(validation_issues, channel_env_var)
            
            # 7. 파일 정리
            try:
                if os.path.exists(csv_file):
                    os.remove(csv_file)
                
                downloads_pattern = os.path.expanduser("~/Downloads/export-projects*.csv")
                downloads_files = glob.glob(downloads_pattern)
                for file in downloads_files:
                    try:
                        os.remove(file)
                    except:
                        pass
                        
            except Exception as e:
                pass
            
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

    def send_to_slack(self, csv_file_path, stats=None, error_message=None, validation_issues=None):
        """슬랙에 리포트 전송 (파일 업로드 + 메시지)"""
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
            message_text = f"[{today}] 태스크월드 리포트 ({WORKSPACE_NAME})"

            if error_message:
                message_text += f"\n파일 업로드 실패: `{error_message}`"
            else:
                message_text += f"\n✅ 파일 업로드 성공: `{OUTPUT_FILENAME}`"

                if validation_issues:
                    message_text += f"\n```"
                    message_text += f"\n[검증 오류]"
                    for issue in validation_issues:
                        message_text += f"\n- {issue}"
                    message_text += f"\n```"
                    
            msg_response = self.slack_client.chat_postMessage(
                channel=actual_channel_id,
                text=message_text
            )
            
            if not msg_response.get('ok'):
                return False
            
            message_channel = msg_response.get('channel')
            message_ts = msg_response.get('ts')
            
            # 4. 파일 업로드 (파일이 있고 에러가 아닐 경우에만)
            if csv_file_path and os.path.exists(csv_file_path) and not error_message:
                filename = os.path.basename(csv_file_path)
                
                try:
                    with open(csv_file_path, 'rb') as file_obj:
                        file_response = self.slack_client.files_upload_v2(
                            channel=message_channel,
                            file=file_obj,
                            filename=filename,
                            title=f"태스크월드 리포트 - {today}"
                        )
                    
                    if file_response.get('ok'):
                        return True
                    else:
                        error_detail = file_response.get('error', 'unknown')
                        self._send_upload_error_thread(message_channel, message_ts, filename, error_detail, file_response)
                        return False
                        
                except Exception as file_error:
                    filename = os.path.basename(csv_file_path)
                    self._send_upload_error_thread(message_channel, message_ts, filename, f"예외 발생: {str(file_error)}", None)
                    return False
            else:
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

    def _is_clickable_button(self, element):
        """요소가 실제 클릭 가능한 버튼인지 확인"""
        try:
            tag_name = element.tag_name.lower()
            if tag_name in ['button', 'input', 'a']:
                return True
            
            if tag_name == 'input':
                input_type = element.get_attribute('type')
                if input_type in ['button', 'submit']:
                    return True
            
            onclick = element.get_attribute('onclick')
            if onclick:
                return True
            
            cursor_style = element.value_of_css_property('cursor')
            if cursor_style == 'pointer':
                return True
            
            role = element.get_attribute('role')
            if role == 'button':
                return True
            
            try:
                parent = element.find_element(By.XPATH, "..")
                parent_tag = parent.tag_name.lower()
                if parent_tag in ['button', 'a']:
                    return True
                
                parent_role = parent.get_attribute('role')
                if parent_role == 'button':
                    return True
                    
                parent_onclick = parent.get_attribute('onclick')
                if parent_onclick:
                    return True
                    
            except:
                pass
            
            class_name = element.get_attribute('class') or ""
            button_keywords = ['btn', 'button', 'clickable', 'action', 'export']
            if any(keyword in class_name.lower() for keyword in button_keywords):
                return True
            
            return False
            
        except Exception as e:
            return False
    
    def export_csv(self):
        """CSV 내보내기 실행"""
        try:
            # 다운로드 전 기존 CSV 파일 목록 저장 및 정리
            existing_csvs = glob.glob(os.path.join(self.download_dir, "*.csv"))
            
            # 기존 export-projects 관련 파일들 삭제 (중복 방지)
            export_files_pattern = os.path.join(self.download_dir, "export-projects*.csv")
            export_files = glob.glob(export_files_pattern)
            
            for file in export_files:
                try:
                    os.remove(file)
                except Exception as e:
                    pass
            
            # 다운로드 전 기존 CSV 파일 목록 다시 저장
            existing_csvs = glob.glob(os.path.join(self.download_dir, "*.csv"))
            
            time.sleep(3)
            
            # 1단계: URL을 직접 수정해서 설정 페이지로 이동
            current_url = self.driver.current_url
            
            if "view=board" in current_url:
                settings_url = current_url.replace("view=board", "view=settings&menu=general")
                self.driver.get(settings_url)
                time.sleep(3)
            else:
                if "?" in current_url:
                    settings_url = current_url + "&view=settings&menu=general"
                else:
                    settings_url = current_url + "?view=settings&menu=general"
                
                self.driver.get(settings_url)
                time.sleep(3)
            
            # 2단계: CSV 내보내기 버튼 찾기
            csv_export_selectors = [
                "//button[contains(@class, 'export') and contains(text(), 'CSV')]",
                "//button[contains(@data-action, 'csv') or contains(@data-action, 'export')]",
                "//button[contains(@onclick, 'csv') or contains(@onclick, 'export')]",
                "//input[@type='button' and contains(@value, 'CSV')]",
                "//a[contains(@href, 'csv') or contains(@href, 'export')]",
                "//button[contains(text(), 'CSV로 내보내기')]",
                "//*[contains(text(), 'CSV로 내보내기')]",
                "//div[contains(text(), 'CSV로 내보내기')]",
                "//span[contains(text(), 'CSV로 내보내기')]",
                "//a[contains(text(), 'CSV로 내보내기')]",
                "//button[contains(text(), 'CSV')]",
                "//button[contains(text(), '내보내기')]",
                "//a[contains(text(), 'CSV')]",
                "//div[contains(text(), 'CSV')]",
                "//span[contains(text(), 'CSV')]",
                "//*[contains(text(), 'Export')]"
            ]
            
            export_csv_btn = None
            found_selector = None
            
            for i, selector in enumerate(csv_export_selectors):
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    
                    if elements:
                        for j, element in enumerate(elements):
                            try:
                                tag_name = element.tag_name
                                text = element.text.strip()
                                is_enabled = element.is_enabled()
                                is_displayed = element.is_displayed()
                                
                                is_actual_button = self._is_clickable_button(element)
                                
                                if is_enabled and is_displayed and is_actual_button and not export_csv_btn:
                                    export_csv_btn = element
                                    found_selector = selector
                                    break
                                    
                            except Exception as e:
                                pass
                        
                        if export_csv_btn:
                            break
                            
                except Exception as e:
                    continue
            
            if not export_csv_btn:
                return None
                
            # 1차 시도: 일반 클릭
            try:
                export_csv_btn.click()
            except Exception as e:
                pass
            
            time.sleep(2)
            
            # 2차 시도: JavaScript 강제 클릭
            try:
                self.driver.execute_script("arguments[0].click();", export_csv_btn)
            except Exception as e:
                pass
            
            time.sleep(2)
            
            # 3차 시도: ActionChains 클릭
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(self.driver)
                actions.move_to_element(export_csv_btn).click().perform()
            except Exception as e:
                pass
                
            time.sleep(3)
            
            # 다운로드 완료 대기 (새로운 파일이 생성될 때까지)
            timeout = 120
            check_interval = 2
            
            for i in range(0, timeout, check_interval):
                # 현재 CSV 파일 목록 확인
                current_csvs = glob.glob(os.path.join(self.download_dir, "*.csv"))
                new_csvs = [f for f in current_csvs if f not in existing_csvs]
                
                if new_csvs:
                    # 가장 최신 파일 찾기 (생성 시간 기준)
                    latest_file = max(new_csvs, key=os.path.getctime)
                    
                    # 파일 크기 확인 (0바이트가 아닌지)
                    file_size = os.path.getsize(latest_file)
                    
                    if file_size > 0:
                        return latest_file
                    else:
                        print("⚠️ 파일 크기가 0바이트, 계속 대기...")
                
                # Downloads 폴더도 확인 (export-projects 관련 파일)
                downloads_pattern = os.path.expanduser("~/Downloads/export-projects*.csv")
                downloads_csvs = glob.glob(downloads_pattern)
                
                if downloads_csvs:
                    # 가장 최신 파일 찾기
                    latest_download = max(downloads_csvs, key=os.path.getctime)
                    mod_time = os.path.getmtime(latest_download)
                    
                    # 10분 이내에 생성된 파일만 확인
                    if time.time() - mod_time < 600:
                        
                        # 현재 폴더로 복사
                        import shutil
                        local_file = os.path.basename(latest_download)
                        shutil.copy(latest_download, local_file)
                        
                        # Downloads의 원본 파일 삭제 (정리)
                        try:
                            os.remove(latest_download)
                        except:
                            pass
                            
                        return local_file
                
                # .crdownload 파일 확인 (Chrome 다운로드 중 파일)
                downloading_files = glob.glob(os.path.join(self.download_dir, "*.crdownload"))
                downloads_crdownload = glob.glob(os.path.expanduser("~/Downloads/*.crdownload"))
                
                if downloading_files or downloads_crdownload:
                    pass
                elif i % 20 == 0:  # 20초마다 상태 출력
                    # 주기적으로 페이지 새로고침
                    if i > 0 and i % 60 == 0:
                        try:
                            # 현재 URL이 여전히 설정 페이지인지 확인
                            if "settings" not in self.driver.current_url:
                                self.driver.refresh()
                        except:
                            pass
                
                time.sleep(check_interval)
            
            return None
            
        except Exception as e:
            print(f"❌ CSV 내보내기 실패: {e}")
            return None

    def run_complete_automation(self, email, password, workspace_name=WORKSPACE_NAME):
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
                error_msg = "태스크월드 로그인 실패"
                self.send_to_slack(None, None, error_msg)
                return None
            
            # 3. 워크스페이스 이동
            print("\n3️⃣ 워크스페이스 이동...")
            if not self.navigate_to_workspace(workspace_name):
                error_msg = f"워크스페이스 '{workspace_name}' 접속 실패"
                self.send_to_slack(None, None, error_msg)
                return None
            
            # 4. CSV 내보내기
            print("\n4️⃣ CSV 내보내기...")
            csv_file = self.export_csv()
            
            if not csv_file:
                error_msg = "CSV 다운로드 실패"
                self.send_to_slack(None, None, error_msg)
                return None
            
            print(f"\n✅ 태스크월드 CSV 다운로드 완료: {csv_file}")

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
            
            
            # 6. 슬랙 전송 (검증 결과 + 점검 필요 알림 포함)
            print("\n6️⃣ 슬랙 리포트 전송...")
            if self.slack_client:
                # 통계 정보 구성
                stats_info = f"총 {len(result_df) + (removed_count or 0)}행 → 필터링 {removed_count or 0}행 → 최종 {len(result_df)}행"
                
                print(f"📊 전송할 통계: {stats_info}")
                print(f"📁 전송할 파일: {processed_file}")
                
                success = self.send_to_slack(processed_file, stats_info, None, validation_issues)
                if success:
                    print("✅ 슬랙 전송 완료! (파일+메시지 모두 성공)")
                else:
                    print("❌ 슬랙 전송 실패")
                    # 실패해도 파일은 생성되었으므로 프로세스는 성공으로 간주
                    print("💡 파일은 생성되었으니 수동으로 슬랙에 업로드 가능")
            else:
                print("⚠️ 슬랙 토큰이 없어 전송을 건너뜁니다.")
            
            # 7. 파일 정리
            print("\n7️⃣ 파일 정리...")
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
    print(f"📧 TASKWORLD_EMAIL: {'설정됨' if os.getenv('TASKWORLD_EMAIL') else '❌ 없음'}")
    print(f"🔒 TASKWORLD_PASSWORD: {'설정됨' if os.getenv('TASKWORLD_PASSWORD') else '❌ 없음'}")
    print(f"🤖 SLACK_BOT_TOKEN: {'설정됨' if os.getenv('SLACK_BOT_TOKEN') else '❌ 없음'}")
    print(f"💬 SLACK_CHANNEL: {os.getenv('SLACK_CHANNEL', '❌ 없음')}")
    print(f"💬 SLACK_CHANNEL_VALIDATION: {os.getenv('SLACK_CHANNEL_VALIDATION', '❌ 없음')}")
    
    print(f"\n🔍 설정값 확인:")
    print(f"📂 워크스페이스: {WORKSPACE_NAME}")
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
        email = os.getenv("TASKWORLD_EMAIL")
        password = os.getenv("TASKWORLD_PASSWORD")
        workspace = os.getenv("TASKWORLD_WORKSPACE", WORKSPACE_NAME)
        
        if not email or not password:
            print("❌ 환경변수 필요: TASKWORLD_EMAIL, TASKWORLD_PASSWORD")
            exit(1)
        
        downloader = TaskworldSeleniumDownloader(headless=DEFAULT_HEADLESS)
        result = downloader.run_complete_automation(email, password, workspace)
        
        if result:
            print(f"📁 최종 파일: {result}")
        else:
            print("\n❌ 실패")
            exit(1)
