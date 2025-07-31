# selenium_taskworld_downloader.py - 완전 자동화 스크립트 (설정값 개선 + 검증 전용 기능 + Due Date 체크 추가)
import os
import time
import glob
import pandas as pd
from datetime import datetime, timezone, timedelta, date
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
# 📅 월별 설정 변수 (매월 수정 필요)
# ==========================================
WORKSPACE_NAME = "아트실 일정 - 2024 7주기"  # 🔄 한달마다 수정하세요!
OUTPUT_FILENAME = "24_7.csv"  # 🔄 한달마다 수정하세요! (예: 25_7.csv, 25_8.csv)

# ==========================================
# 🔧 검증 설정 변수 (필요시 수정)
# ==========================================
MIN_REQUIRED_HOURS = 160  # 🔄 필요시 수정하세요! (개인별 최소 시간)
WORK_END_TIME_HOUR = 18   # 🔄 업무 종료 시간 (24시간 형식, 기본: 18시)

# ==========================================
# 🗂️ 파일 경로 설정
# ==========================================

FIRST_TAGS_REQUIRED_ART_FILE = "first_tags_required_second_art.txt"         # 프로젝트 제외. 실에서 사용하는 두번째 태그 필수인 첫 번째 태그들
FIRST_TAGS_REQUIRED_PROJECT_FILE = "first_tags_required_second_project.txt" # 프로젝트용 두번째 태그 필수인 첫 번째 태그들
FIRST_TAGS_OPTIONAL_SECOND_FILE = "first_tags_optional_second.txt"          # 두 번째 태그 선택적인 첫 번째 태그들
SECOND_TAGS_ART_FILE = "second_tags_art.txt"                                # 프로젝트 제외. 실에서 사용하면서 두번째 태그에 올 수 있는 태그들
SECOND_TAGS_PROJECT_FILE = "second_tags_project.txt"                        # 프로젝트용 두번째 태그에 올 수 있는 태그들
EXCLUDE_VALUES_FILE = "exclude_values.txt"                                  # 제외할 Tasklist 값들 파일

# ==========================================
# 기타 설정
# ==========================================
DEFAULT_HEADLESS = True  # 브라우저 창 보기/숨기기 (True: 숨김, False: 보기)

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
        self.download_dir = os.path.abspath("./")  # 현재 디렉토리로 통일
        
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
        print(f"🕕 업무 종료 시간: {WORK_END_TIME_HOUR}시")
        print(f"💬 슬랙 채널: '{self.slack_channel}' (따옴표 포함 확인)")
        print(f"🔧 채널명 길이: {len(self.slack_channel)} 글자")
        
        # 슬랙 봇 초기화
        if self.slack_token:
            try:
                self.slack_client = WebClient(token=self.slack_token)
                response = self.slack_client.auth_test()
                print(f"✅ 슬랙 봇 연결 성공: {response['user']}")
                print(f"🔑 토큰 앞부분: {self.slack_token[:20]}...")
                
                # 봇 권한 간단 확인
                try:
                    test_response = self.slack_client.conversations_list(limit=1)
                    if test_response['ok']:
                        print(f"✅ 채널 읽기 권한 확인됨")
                    else:
                        print(f"⚠️ 채널 읽기 권한 없음: {test_response.get('error')}")
                except Exception as perm_error:
                    print(f"⚠️ 권한 확인 실패: {perm_error}")
                    
            except SlackApiError as e:
                print(f"❌ 슬랙 봇 연결 실패: {e.response['error']}")
                if e.response['error'] == 'invalid_auth':
                    print("🔑 토큰이 유효하지 않습니다. 새 토큰이 필요합니다!")
        else:
            print("⚠️ 슬랙 토큰이 없어 슬랙 전송 기능 비활성화")
        
    def setup_driver(self):
        """Chrome 드라이버 설정 (GitHub Actions용 최적화)"""
        try:
            print("🔧 Chrome 드라이버 설정 시작...")
            chrome_options = Options()
            
            # headless 설정 (조건부)
            if self.headless:
                chrome_options.add_argument("--headless")
                print("👻 Headless 모드로 실행")
            else:
                print("🖥️ 브라우저 창 보기 모드로 실행")
            
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # 다운로드 설정 - 경로 통일
            prefs = {
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
                "profile.default_content_settings.popups": 0
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # User Agent 설정 (봇 감지 방지)
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 30)
            
            print("✅ Chrome 드라이버 설정 완료")
            print(f"📁 다운로드 경로: {self.download_dir}")
            
            # 브라우저 확인용 대기
            if not self.headless:
                print("⏳ 브라우저 창 확인을 위해 3초 대기...")
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
                print(f"📋 제외 값들: {exclude_values}")
                return exclude_values
            else:
                # 기본값 사용 및 파일 생성
                default_values = ["주요일정", "아트실", "UI팀", "리소스팀", "디자인팀", "TA팀"]
                print(f"❌ {EXCLUDE_VALUES_FILE} 파일이 없습니다!")
                print(f"🔧 기본값으로 파일을 생성합니다: {default_values}")
                
                # 기본 파일 생성
                with open(EXCLUDE_VALUES_FILE, 'w', encoding='utf-8') as f:
                    f.write("# 제외할 Tasklist 값들 (한 줄에 하나씩)\n")
                    f.write("# 주석은 #으로 시작\n\n")
                    for value in default_values:
                        f.write(f"{value}\n")
                
                print(f"✅ {EXCLUDE_VALUES_FILE} 파일이 생성되었습니다. 필요시 수정하세요.")
                return default_values
                
        except Exception as e:
            print(f"❌ 제외 값 로드 실패: {e}")
            print("🔧 기본값을 사용합니다.")
            return ["주요일정", "아트실", "UI팀", "리소스팀", "디자인팀", "TA팀"]
    
    def login_to_taskworld(self, email, password):
        """태스크월드 로그인"""
        try:
            print("🔐 태스크월드 로그인 시작...")
            print(f"📧 사용할 이메일: {email[:3]}***@{email.split('@')[1] if '@' in email else '***'}")
            
            # 태스크월드 로그인 페이지로 이동
            print("🌐 태스크월드 로그인 페이지로 이동 중...")
            self.driver.get("https://asia-enterprise.taskworld.com/login")
            
            # 페이지 로딩 대기
            time.sleep(3)
            print(f"📄 현재 페이지 URL: {self.driver.current_url}")
            print(f"📄 페이지 제목: {self.driver.title}")
            
            # 일반 이메일 로그인으로 바로 진행
            print("📧 일반 이메일 로그인으로 진행...")
            return self._handle_email_login(email, password)
                    
        except Exception as e:
            print(f"❌ 로그인 전체 프로세스 실패: {e}")
            return False
    
    def _handle_email_login(self, email, password):
        """일반 이메일 로그인 처리"""
        try:
            print("📧 일반 이메일 로그인 시작...")
            
            # 이메일 입력
            print("📧 이메일 입력 필드 찾는 중...")
            email_input = self.wait.until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            print("✅ 이메일 입력 필드 발견")
            
            email_input.clear()
            email_input.send_keys(email)
            print(f"📝 이메일 입력 완료: {email[:3]}***")
            
            # 패스워드 입력
            print("🔒 패스워드 입력 필드 찾는 중...")
            password_input = self.driver.find_element(By.NAME, "password")
            password_input.clear()
            password_input.send_keys(password)
            print("🔒 패스워드 입력 완료")
            
            # 로그인 버튼 클릭
            print("🖱️ 로그인 버튼 찾는 중...")
            login_btn = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_btn.click()
            print("✅ 로그인 버튼 클릭 완료")
            
            # 로그인 완료 대기
            print("⏳ 로그인 완료 대기 중...")
            time.sleep(5)
            
            print(f"📄 로그인 후 URL: {self.driver.current_url}")
            print("✅ 이메일 로그인 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 이메일 로그인 실패: {e}")
            print(f"📄 현재 URL: {self.driver.current_url}")
            return False
    
    def navigate_to_workspace(self, workspace_name=WORKSPACE_NAME):
        """특정 워크스페이스로 이동"""
        try:
            print(f"📂 워크스페이스 '{workspace_name}' 찾는 중...")
            print(f"📄 현재 URL: {self.driver.current_url}")
            
            time.sleep(3)  # 페이지 로딩 대기
            
            # 1단계: URL을 직접 수정해서 프로젝트 페이지로 이동
            print("🔗 URL을 직접 수정해서 프로젝트 페이지로 이동...")
            current_url = self.driver.current_url
            
            # home을 projects로 교체
            if "#/home" in current_url:
                project_url = current_url.replace("#/home", "#/projects")
                print(f"📄 이동할 URL: {project_url}")
                self.driver.get(project_url)
                time.sleep(3)  # 프로젝트 페이지 로딩 대기
                print("✅ 프로젝트 페이지로 이동 완료")
            else:
                print("⚠️ URL에 #/home이 없어서 직접 프로젝트 페이지 구성을 시도합니다...")
                # 기본 URL 구조에 #/projects 추가
                if "#/" not in current_url:
                    project_url = current_url + "#/projects"
                else:
                    base_url = current_url.split("#/")[0]
                    project_url = base_url + "#/projects"
                
                print(f"📄 구성된 URL: {project_url}")
                self.driver.get(project_url)
                time.sleep(3)
            
            # 2단계: 워크스페이스 찾기
            print(f"📂 워크스페이스 '{workspace_name}' 찾는 중...")
            workspace_selectors = [
                f"//a[contains(text(), '{workspace_name}')]",
                f"//div[contains(text(), '{workspace_name}')]",
                f"//span[contains(text(), '{workspace_name}')]",
                f"//button[contains(text(), '{workspace_name}')]",
                f"//*[contains(text(), '{workspace_name}')]"
            ]
            
            workspace_link = None
            for selector in workspace_selectors:
                try:
                    print(f"🔍 워크스페이스 선택자 시도: {selector}")
                    workspace_link = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    print(f"✅ 워크스페이스 링크 발견: {selector}")
                    break
                except:
                    print(f"❌ 워크스페이스 선택자 실패: {selector}")
                    continue
            
            if not workspace_link:
                print("❌ 워크스페이스 링크를 찾을 수 없음")
                print("📋 페이지의 모든 텍스트 확인:")
                try:
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text
                    print(page_text[:500] + "..." if len(page_text) > 500 else page_text)
                except:
                    print("페이지 텍스트 가져오기 실패")
                return False
            
            # 워크스페이스 클릭
            print("🖱️ 워크스페이스 클릭...")
            workspace_link.click()
            
            # 워크스페이스 로딩 대기
            print("⏳ 워크스페이스 로딩 대기...")
            time.sleep(5)
            
            print(f"📄 워크스페이스 접속 후 URL: {self.driver.current_url}")
            print(f"✅ '{workspace_name}' 워크스페이스 접속 완료")
            return True
            
        except Exception as e:
            print(f"❌ 워크스페이스 접속 실패: {e}")
            print(f"📄 현재 URL: {self.driver.current_url}")
            return False

    def load_allowed_tags(self):
        """허용된 태그 목록 파일에서 로드 - 아트/프로젝트 구조"""
        try:
            # 아트 그룹 첫 번째 태그 (두 번째 태그 필수)
            try:
                with open(FIRST_TAGS_REQUIRED_ART_FILE, 'r', encoding='utf-8') as f:
                    first_tags_required_art = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                print(f"✅ 아트 그룹 필수 첫 번째 태그 로드: {len(first_tags_required_art)}개 (first_tags_required_second_art.txt)")
            except FileNotFoundError:
                print(f"❌ 검증을 위한 first_tags_required_second_art.txt 파일을 확인해주세요.")
                # 기본 파일 생성
                default_art = ["cpm", "9up", "c-"]
                with open('first_tags_required_second_art.txt', 'w', encoding='utf-8') as f:
                    f.write("# 아트 그룹: 두 번째 태그가 반드시 있어야 하는 첫 번째 태그들\n")
                    f.write("# 한 줄에 하나씩, 주석은 #으로 시작\n\n")
                    for tag in default_art:
                        f.write(f"{tag}\n")
                print(f"✅ first_tags_required_second_art.txt 기본 파일 생성됨")
                first_tags_required_art = default_art

            # 프로젝트 그룹 첫 번째 태그 (두 번째 태그 필수)
            try:
                with open('first_tags_required_second_project.txt', 'r', encoding='utf-8') as f:
                    first_tags_required_project = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                print(f"✅ 프로젝트 그룹 필수 첫 번째 태그 로드: {len(first_tags_required_project)}개 (first_tags_required_second_project.txt)")
            except FileNotFoundError:
                print(f"❌ 검증을 위한 first_tags_required_second_project.txt 파일을 확인해주세요.")
                # 기본 파일 생성
                default_project = ["a1", "실업무", "9-"]
                with open('first_tags_required_second_project.txt', 'w', encoding='utf-8') as f:
                    f.write("# 프로젝트 그룹: 두 번째 태그가 반드시 있어야 하는 첫 번째 태그들\n")
                    f.write("# 한 줄에 하나씩, 주석은 #으로 시작\n\n")
                    for tag in default_project:
                        f.write(f"{tag}\n")
                print(f"✅ first_tags_required_second_project.txt 기본 파일 생성됨")
                first_tags_required_project = default_project
            
            # 두 번째 태그 선택적인 첫 번째 태그들 (기존과 동일)
            try:
                with open(FIRST_TAGS_OPTIONAL_SECOND_FILE, 'r', encoding='utf-8') as f:
                    first_tags_optional_second = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                print(f"✅ 두 번째 태그 선택적 첫 번째 태그 로드: {len(first_tags_optional_second)}개 ({FIRST_TAGS_OPTIONAL_SECOND_FILE})")
            except FileNotFoundError:
                print(f"❌ 검증을 위한 {FIRST_TAGS_OPTIONAL_SECOND_FILE} 파일을 확인해주세요.")
                # 기본 파일 생성
                default_optional = ["공통업무", "공통작업", "연차", "사내행사", "공휴일"]
                with open(FIRST_TAGS_OPTIONAL_SECOND_FILE, 'w', encoding='utf-8') as f:
                    f.write("# 두 번째 태그가 있어도 되고 없어도 되는 첫 번째 태그들\n")
                    f.write("# 한 줄에 하나씩, 주석은 #으로 시작\n\n")
                    for tag in default_optional:
                        f.write(f"{tag}\n")
                print(f"✅ {FIRST_TAGS_OPTIONAL_SECOND_FILE} 기본 파일 생성됨")
                first_tags_optional_second = default_optional
            
            # 아트용 두 번째 태그들
            try:
                with open('second_tags_art.txt', 'r', encoding='utf-8') as f:
                    second_tags_art = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                print(f"✅ 아트용 두 번째 태그 로드 완료: {len(second_tags_art)}개 (second_tags_art.txt)")
            except FileNotFoundError:
                print(f"❌ 검증을 위한 second_tags_art.txt 파일을 확인해주세요.")
                # 기본 파일 생성
                default_art_second = ["회의", "문서작업"]
                with open('second_tags_art.txt', 'w', encoding='utf-8') as f:
                    f.write("# 아트 그룹용 두 번째 태그로 허용되는 값들 (완전 일치)\n")
                    f.write("# 한 줄에 하나씩, 주석은 #으로 시작\n\n")
                    for tag in default_art_second:
                        f.write(f"{tag}\n")
                print(f"✅ second_tags_art.txt 기본 파일 생성됨")
                second_tags_art = default_art_second

            # 프로젝트용 두 번째 태그들
            try:
                with open('second_tags_project.txt', 'r', encoding='utf-8') as f:
                    second_tags_project = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                print(f"✅ 프로젝트용 두 번째 태그 로드 완료: {len(second_tags_project)}개 (second_tags_project.txt)")
            except FileNotFoundError:
                print(f"❌ 검증을 위한 second_tags_project.txt 파일을 확인해주세요.")
                # 기본 파일 생성
                default_project_second = ["피드백", "교육"]
                with open('second_tags_project.txt', 'w', encoding='utf-8') as f:
                    f.write("# 프로젝트 그룹용 두 번째 태그로 허용되는 값들 (완전 일치)\n")
                    f.write("# 한 줄에 하나씩, 주석은 #으로 시작\n\n")
                    for tag in default_project_second:
                        f.write(f"{tag}\n")
                print(f"✅ second_tags_project.txt 기본 파일 생성됨")
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
            print("🏷️ C열 태그 검증 시작...")
            print(f"📋 아트 그룹 필수: {first_tags_required_art}")
            print(f"📋 프로젝트 그룹 필수: {first_tags_required_project}")
            print(f"📋 두 번째 태그 선택적: {first_tags_optional_second}")
            print(f"📋 아트용 두 번째 태그: {second_tags_art}")
            print(f"📋 프로젝트용 두 번째 태그: {second_tags_project}")
            
            # 태그 열이 존재하는지 확인
            if 'Tags' not in df.columns:
                tag_validation_issues.append("Tags 열이 존재하지 않습니다.")
                return tag_validation_issues
            
            # 전체 허용된 첫 번째 태그 목록
            all_first_tags = first_tags_required_second + first_tags_optional_second
            
            # 각 행별로 태그 검증
            for idx, row in df.iterrows():
                person_name = row['Tasklist']  # A열 이름
                tags = row['Tags']  # C열 태그
                
                task_name = row['Task']  # B열 작업명
                task_display = str(task_name)[:20] + "..." if len(str(task_name)) > 20 else str(task_name)
                
                # 태그가 비어있거나 NaN인 경우 건너뛰기
                if pd.isna(tags) or tags == '' or tags == 0:
                    continue
                
                # 이름 그룹핑 (기존 로직과 동일)
                if pd.isna(person_name) or person_name == '':
                    person_group = '미분류'
                else:
                    name_str = str(person_name).strip()
                    person_group = name_str[:3] if len(name_str) >= 3 else name_str
                
                # 태그를 쉼표로 분리
                tag_list = str(tags).split(',')
                tag_list = [tag.strip() for tag in tag_list if tag.strip()]  # 공백 제거 및 빈 값 제거
                
                if len(tag_list) == 0:
                    continue  # 태그가 없으면 건너뛰기
                
                # 첫 번째 태그 검증 (부분 일치)
                first_tag = tag_list[0]
                first_tag_valid = False
                first_tag_category = None  # 'required' 또는 'optional'
                
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
                    continue  # 첫 번째 태그가 틀리면 두 번째는 확인하지 않음
                
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
            
            if tag_validation_issues:
                print(f"❌ {len(tag_validation_issues)}개의 태그 검증 이슈 발견")
                for issue in tag_validation_issues:
                    print(f"  - {issue}")
            else:
                print("✅ 모든 태그 검증 통과!")
            
            return tag_validation_issues
            
        except Exception as e:
            error_msg = f"태그 검증 중 오류 발생: {str(e)}"
            print(f"❌ {error_msg}")
            return [error_msg]
    
    def check_due_date_alerts(self, df, work_end_hour=WORK_END_TIME_HOUR):
        """Due Date 기반 마감일 알림 체크 - 강화된 디버깅"""
        due_date_alerts = []
        
        try:
            print(f"📅 Due Date 알림 체크 시작 (업무종료시간: {work_end_hour}시)...")
            
            # Due Date 열이 존재하는지 확인
            if 'Due Date' not in df.columns:
                print("⚠️ Due Date 열이 존재하지 않음 - 마감일 체크 건너뜀")
                print(f"📋 사용 가능한 컬럼: {list(df.columns)}")
                return due_date_alerts
            
            # 현재 한국 시간
            now = datetime.now(self.korea_tz)
            today = now.date()
            current_time = now.time()
            work_end_time = datetime.strptime(f"{work_end_hour}:00", "%H:%M").time()
            
            print(f"📅 현재 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"📅 오늘 날짜: {today}")
            print(f"🕐 업무 종료 시간: {work_end_time}")
            
            # 🔍 Due Date 컬럼의 모든 고유값 확인
            unique_due_dates = df['Due Date'].unique()
            print(f"🔍 Due Date 컬럼의 고유값들 (처음 10개): {unique_due_dates[:10]}")
            print(f"🔍 Due Date 컬럼 데이터 타입들: {[type(x).__name__ for x in unique_due_dates[:5]]}")
            
            # 이름 그룹핑 함수
            def get_name_group(tasklist_name):
                if pd.isna(tasklist_name) or tasklist_name == '':
                    return '미분류'
                name_str = str(tasklist_name).strip()
                return name_str[:3] if len(name_str) >= 3 else name_str
            
            # 날짜 파싱 함수 (강화된 디버깅)
            def parse_due_date(due_date_str, debug_info=""):
                if pd.isna(due_date_str) or due_date_str == '':
                    return None
                
                try:
                    # 다양한 날짜 형식 지원 (시간 포함 형식 추가)
                    date_formats = [
                        '%Y-%m-%d',                # 2025-07-08
                        '%m/%d/%Y',               # 07/08/2025
                        '%d/%m/%Y',               # 08/07/2025
                        '%Y.%m.%d',               # 2025.07.08
                        '%Y/%m/%d',               # 2025/07/08
                        '%Y-%m-%d %H:%M:%S',      # 2025-07-08 00:00:00
                        '%Y-%m-%dT%H:%M:%S',      # 2025-07-08T00:00:00
                        '%m/%d/%Y %H:%M',         # 07/09/2025 18:00  ← 추가!
                        '%m/%d/%Y %H:%M:%S',      # 07/09/2025 18:00:00
                        '%d/%m/%Y %H:%M',         # 09/07/2025 18:00
                        '%d/%m/%Y %H:%M:%S',      # 09/07/2025 18:00:00
                        '%Y.%m.%d %H:%M',         # 2025.07.09 18:00
                        '%Y/%m/%d %H:%M',         # 2025/07/09 18:00
                    ]
                    
                    date_str = str(due_date_str).strip()
                    
                    for fmt in date_formats:
                        try:
                            parsed_date = datetime.strptime(date_str, fmt).date()
                            if debug_info and parsed_date == today:
                                print(f"🎯 {debug_info} - 오늘 마감 발견! '{date_str}' -> {parsed_date} (형식: {fmt})")
                            return parsed_date
                        except ValueError:
                            continue
                    
                    print(f"⚠️ 날짜 형식 파싱 실패: '{due_date_str}' {debug_info}")
                    return None
                    
                except Exception as e:
                    print(f"⚠️ 날짜 파싱 오류: '{due_date_str}' {debug_info} - {e}")
                    return None
            
            # 제외 대상 로드
            exclude_values = self.load_exclude_values()
            print(f"🚫 제외 대상: {exclude_values}")
            
            # 각 행별로 Due Date 체크 (간소화된 로그)
            due_date_count = 0
            today_due_count = 0
            excluded_count = 0
            empty_due_date_count = 0
            completed_count = 0

            
            for idx, row in df.iterrows():
                person_name = row['Tasklist']
                task_name = row['Task']
                due_date_str = row['Due Date']
                status = row.get('Status', '')  # Status 컬럼 확인
                
                # 제외 대상 건너뛰기 (팀명 등)
                if person_name in exclude_values:
                    excluded_count += 1
                    continue
                
                # Completed 상태 제외 (Active만 체크)
                if status == 'Completed':
                    completed_count += 1
                    continue
        
                # Due Date 파싱
                debug_info = f"행 {idx+1} ({person_name})"
                due_date = parse_due_date(due_date_str, debug_info)
                
                if not due_date:
                    empty_due_date_count += 1
                    continue
                
                due_date_count += 1
                
                # 오늘 마감인 Active 작업만 체크
                if due_date == today:
                    today_due_count += 1
                    person_group = get_name_group(person_name)
                    task_display = str(task_name)[:30] + "..." if len(str(task_name)) > 30 else str(task_name)
                    
                    print(f"🎯 오늘 마감 Active 작업 발견! {person_name} - {task_name} (Status: {status})")
                    
                    if current_time < work_end_time:
                        # 아직 업무시간 내
                        alert_msg = f"{person_group}님 : {task_display} (오늘 종료 예정)"
                    else:
                        # 업무시간 지남
                        alert_msg = f"{person_group}님 : {task_display} (업무종료시간 지남)"
                    
                    due_date_alerts.append(alert_msg)
                    print(f"📅 마감일 알림 생성: {alert_msg}")
            
            print(f"\n📊 Due Date 체크 최종 결과:")
            print(f"  - 전체 행: {len(df)}개")
            print(f"  - 제외된 행 (팀명 등): {excluded_count}개")
            print(f"  - Due Date 없는 행: {empty_due_date_count}개")
            print(f"  - Completed 상태 제외: {completed_count}개")
            print(f"  - 오늘 마감 Active 작업: {today_due_count}개")
            print(f"  - 알림 생성: {len(due_date_alerts)}개")
            
            return due_date_alerts
            
        except Exception as e:
            error_msg = f"Due Date 체크 중 오류 발생: {str(e)}"
            print(f"❌ {error_msg}")
            return [error_msg]
    
    def check_assigned_to_alerts(self, df):
        """Assigned To가 비어있는 Active 작업 체크"""
        assigned_to_alerts = []
        
        try:
            print(f"👤 Assigned To 체크 시작...")
            
            # Assigned To 열이 존재하는지 확인
            if 'Assigned To' not in df.columns:
                print("⚠️ Assigned To 열이 존재하지 않음 - Assigned To 체크 건너뜀")
                print(f"📋 사용 가능한 컬럼: {list(df.columns)}")
                return assigned_to_alerts
            
            # 이름 그룹핑 함수
            def get_name_group(tasklist_name):
                if pd.isna(tasklist_name) or tasklist_name == '':
                    return '미분류'
                name_str = str(tasklist_name).strip()
                return name_str[:3] if len(name_str) >= 3 else name_str
            
            # 제외 대상 로드
            exclude_values = self.load_exclude_values()
            
            # 각 행별로 Assigned To 체크
            assigned_to_count = 0
            excluded_count = 0
            empty_assigned_to_count = 0
            empty_time_count = 0
            
            for idx, row in df.iterrows():
                person_name = row['Tasklist']
                task_name = row['Task']
                assigned_to = row['Assigned To']
                time_spent = row['Time Spent']
                status = row.get('Status', '')
                
                # 제외 대상 건너뛰기 (팀명 등)
                if person_name in exclude_values:
                    excluded_count += 1
                    continue
                
                assigned_to_count += 1
                
                # Assigned To가 비어있는지 확인
                is_empty_assigned = pd.isna(assigned_to) or str(assigned_to).strip() == '' or assigned_to == 0
                is_empty_time = pd.isna(time_spent) or str(time_spent).strip() == '' or time_spent == 0
                
                if is_empty_assigned:
                    empty_assigned_to_count += 1
                    person_group = get_name_group(person_name)
                    task_display = str(task_name)[:30] + "..." if len(str(task_name)) > 30 else str(task_name)
                    
                    print(f"👤 담당자 비어있는 작업 발견! {person_name} - {task_name} (Status: {status})")
                    
                    alert_msg = f"{person_group}님 : {task_display} (업무 담당자가 비어있음)"
                    assigned_to_alerts.append(alert_msg)
                    print(f"👤 담당자 알림 생성: {alert_msg}")
                    
                if is_empty_time:
                    empty_time_count += 1
                    person_group = get_name_group(person_name)
                    task_display = str(task_name)[:30] + "..." if len(str(task_name)) > 30 else str(task_name)
                    
                    print(f"⏰ 작업시간 비어있는 작업 발견! {person_name} - {task_name} (Status: {status})")
                    
                    alert_msg = f"{person_group}님 : {task_display} (작업시간이 비어있음)"
                    assigned_to_alerts.append(alert_msg)
                    print(f"⏰ 작업시간 알림 생성: {alert_msg}")
                    
            
            print(f"\n📊 Assigned To 체크 최종 결과:")
            print(f"  - 전체 행: {len(df)}개")
            print(f"  - 제외된 행 (팀명 등): {excluded_count}개")
            print(f"  - 담당자 비어있는 Active 작업: {empty_assigned_to_count}개")
            print(f"  - 작업시간 비어있는 Active 작업: {empty_time_count}개")
            print(f"  - 담당자 알림 생성: {len(assigned_to_alerts)}개")
            print(f"  - 담당자+시간 알림 생성: {len(assigned_to_alerts)}개")
            
            return assigned_to_alerts
            
        except Exception as e:
            error_msg = f"Assigned To 체크 중 오류 발생: {str(e)}"
            print(f"❌ {error_msg}")
            return [error_msg]
    
    def validate_csv_data(self, df, min_hours=MIN_REQUIRED_HOURS, include_due_date_check=True):
        """
        CSV 데이터 검증 - 시간 합계 + 태그 검증 + Due Date 체크 (선택적)
        
        Args:
            df: 검증할 DataFrame
            min_hours: 최소 필수 시간
            include_due_date_check: Due Date 체크 포함 여부 (검증 모드에서만 True)
        """
        try:
            print("🔍 CSV 데이터 검증 시작...")
            print(f"⏱️ 검증 기준: {min_hours}시간 (설정값: MIN_REQUIRED_HOURS)")
            
            if include_due_date_check:
                print("📅 Due Date 체크 포함")
            else:
                print("📅 Due Date 체크 제외 (전체 모드)")
            
            if len(df.columns) < 4:
                return ["❌ 열 수가 부족합니다. 최소 4개 열이 필요합니다."], []
            
            # 열 이름 설정 (원본 19열 그대로 유지)
            print(f"🔍 컬럼 설정 전 - df.columns 수: {len(df.columns)}")
            original_columns = ['Project', 'Tasklist', 'Task', 'Description', 'Assigned To', 'Followers',
                              'Creation Date', 'Completion Date', 'Start Date', 'Due Date', 'Tags',
                              'Status', 'Points', 'Time Spent', 'Checklist', 'Comments', 'Files',
                              'Subtask', 'Subtask Reference ID']
            
            # 실제 컬럼 수에 맞게 조정
            if len(df.columns) > len(original_columns):
            # 부족한 컬럼명 추가
                for i in range(len(original_columns), len(df.columns)):
                    original_columns.append(f'Col_{i+1}')

                # 컬럼명 설정
                df.columns = original_columns[:len(df.columns)]
                print(f"🔍 컬럼 설정 완료")
            else:
                # 필수 컬럼만 설정
                essential_columns = ['Tasklist', 'Task', 'Tags', 'Time_Spent']
                if len(df.columns) >= 4:
                    df.columns = essential_columns + [f'Col_{i}' for i in range(4, len(df.columns))]
                    print(f"🔍 컬럼 설정 완료 - 필수 컬럼 형식 사용")
                else:
                    print(f"❌ 컬럼 수 부족: {len(df.columns)}개")
            
            print(f"🔍 최종 컬럼명: {list(df.columns)}")
            
            # 1. 태그 설정 로드
            first_tags_required_art, first_tags_required_project, first_tags_optional_second, second_tags_art, second_tags_project = self.load_allowed_tags()
            
            # 2. 시간 검증 (기존 로직) - 4열 기준으로
            validation_issues = self._validate_time_totals(df, min_hours)
            
            # 3. 태그 검증 (개선된 로직) - 원본 데이터 사용
            tag_issues = self.validate_tags(df, first_tags_required_art, first_tags_required_project, first_tags_optional_second, second_tags_art, second_tags_project)
            
            # 4. Due Date 체크 + Assigned To 체크 (검증 모드에서만 실행)
            due_date_alerts = []
            assigned_to_alerts = []
            if include_due_date_check:
                print("🔍 Due Date 체크 시작...")
                due_date_alerts = self.check_due_date_alerts(df, WORK_END_TIME_HOUR)
                print(f"🔍 Due Date 체크 완료: {len(due_date_alerts)}개")
                
                print("🔍 Assigned To 체크 시작...")
                assigned_to_alerts = self.check_assigned_to_alerts(df)
                print(f"🔍 Assigned To 체크 완료: {len(assigned_to_alerts)}개")
            
            # 🚨 문제 해결: 기존 방식대로 due_date_alerts 반환하되, 내용만 합치기
            combined_alerts = due_date_alerts + assigned_to_alerts
            
            print(f"🔍 validate_csv_data 알림 합치기 결과:")
            print(f"  - due_date_alerts: {len(due_date_alerts)}개")
            print(f"  - assigned_to_alerts: {len(assigned_to_alerts)}개")
            print(f"  - combined_alerts: {len(combined_alerts)}개")
            print(f"  - combined_alerts 내용: {combined_alerts}")
            
            # 검증 결과 합치기
            all_issues = validation_issues + tag_issues
            
            if not all_issues:
                print("✅ 모든 검증 통과! (시간 합계 + 태그 모두 정상)")
            else:
                print(f"❌ 총 {len(all_issues)}개의 검증 이슈 발견")
            
            if include_due_date_check:
                if combined_alerts:
                    print(f"📅 총 {len(combined_alerts)}개의 점검 필요 알림 (마감일: {len(due_date_alerts)}개, 담당자: {len(assigned_to_alerts)}개)")
                else:
                    print("📅 점검 필요한 작업 없음")
            
            print(f"🔍 validate_csv_data 반환 직전:")
            print(f"  - all_issues: {len(all_issues)}개")
            print(f"  - combined_alerts: {len(combined_alerts)}개")
            
            # 🚨 기존 방식대로 due_date_alerts 위치에 combined_alerts 반환
            return all_issues, combined_alerts
            
        except Exception as e:
            import traceback
            error_msg = f"검증 중 오류 발생: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"🔍 상세 오류 정보:")
            print(traceback.format_exc())
            return [error_msg], []
    
    def _validate_time_totals(self, df, min_hours):
        """시간 합계 검증 (기존 로직을 별도 메서드로 분리)"""
        validation_issues = []
        
        # 시간 포맷 변환 함수
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
                print(f"⚠️ 시간 변환 실패: '{time_str}' - 0으로 처리")
                return 0.0
        
        # 이름 그룹핑 함수
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
            # 4번째 컬럼을 시간 컬럼으로 사용
            if len(df.columns) >= 4:
                time_column = df.columns[3]
            else:
                return ["시간 데이터 컬럼을 찾을 수 없습니다."]
        
        # 시간 데이터 변환
        print("⏱️ 시간 데이터 변환 중...")
        df['Time_Hours'] = df[time_column].apply(convert_time_to_hours)
        
        # 이름 그룹 생성
        print("👥 이름 그룹핑 중...")
        df['Name_Group'] = df['Tasklist'].apply(get_name_group)
        
        # 그룹별 시간 합계 계산
        group_totals = df.groupby('Name_Group')['Time_Hours'].sum()
        
        print(f"📊 검증 기준: 정확히 {min_hours}시간")
        print("📋 개인별 시간 합계:")
        
        # 각 그룹별 검증
        for name_group, total_hours in group_totals.items():
            total_hours = round(total_hours, 1)
            print(f"  - {name_group}: {total_hours}시간")
            
            if total_hours != min_hours:
                issue_msg = f"{name_group}님 합산 오류 (현재: {total_hours}시간, 기준: {min_hours}시간)"
                validation_issues.append(issue_msg)
                print(f"    ⚠️ {issue_msg}")
            else:
                print(f"    ✅ 기준 충족 (정확히 {min_hours}시간)")
        
        # 그룹핑 세부 정보 출력
        print("\n🔍 그룹핑 세부 정보:")
        for name_group in group_totals.index:
            group_items = df[df['Name_Group'] == name_group]['Tasklist'].unique()
            if len(group_items) > 1:
                print(f"  - {name_group} 그룹: {list(group_items)}")
        
        return validation_issues
    
    def process_csv(self, input_file, columns=['Tasklist', 'Task', 'Tags', 'Time Spent'], include_due_date_check=True):
        """CSV 파일 처리 - 검증용 열 제외하고 최종 파일 저장
        
        Args:
            input_file: 입력 CSV 파일 경로
            columns: 최종 출력할 컬럼들
            include_due_date_check: Due Date 체크 포함 여부
        """
        try:
            print("📊 CSV 파일 처리 시작...")
            
            # CSV 읽기
            df = pd.read_csv(input_file)
            original_count = len(df)
            
            # 제외값 필터링
            exclude_values = self.load_exclude_values()
            if 'Tasklist' in df.columns:
                df_filtered = df[~df['Tasklist'].isin(exclude_values)]
                removed_count = original_count - len(df_filtered)
                print(f"🚫 필터링: {removed_count}행 제거")
            else:
                df_filtered = df
                removed_count = 0
            
            # 검증 (원본 19열 데이터로 검증 - Due Date 포함 여부는 파라미터로 결정)
            validation_issues, due_date_alerts = self.validate_csv_data(df_filtered.copy(), min_hours=MIN_REQUIRED_HOURS, include_due_date_check=include_due_date_check)
            
            # 열 선택 (최종 파일용 4열만)
            final_columns = ['Tasklist', 'Task', 'Tags', 'Time Spent']
            missing_columns = [col for col in final_columns if col not in df_filtered.columns]
            if missing_columns:
                return None, None, f"열을 찾을 수 없음: {missing_columns}", [], []
            
            selected_df = df_filtered[final_columns]
            
            # ⭐ 최종 파일 저장 시에는 4개 열만 저장 ⭐
            final_df = selected_df[['Tasklist', 'Task', 'Tags', 'Time Spent']]
            
            # 파일 저장
            output_file = OUTPUT_FILENAME
            if os.path.exists(output_file):
                os.remove(output_file)
            
            final_df.to_csv(output_file, index=False, header=False, encoding='utf-8-sig')
            print(f"✅ CSV 처리 완료: {len(final_df)}행 → {output_file} (검증용 열 제외)")
            
            print(f"🔍 process_csv 최종 반환 직전:")
            print(f"  - validation_issues: {len(validation_issues)}개")
            print(f"  - due_date_alerts: {len(due_date_alerts)}개")
            print(f"  - due_date_alerts 내용: {due_date_alerts}")
            
            return selected_df, removed_count, output_file, validation_issues, due_date_alerts
            
        except Exception as e:
            return None, None, f"CSV 처리 오류: {str(e)}", [], []

    # ⭐ 검증 전용 함수들 ⭐

    def send_validation_report_to_slack(self, validation_issues, all_alerts=None, channel_env_var="SLACK_CHANNEL_VALIDATION"):
        """검증 결과 + 점검 필요 알림을 슬랙에 전송 (파일 업로드 없이) - 오류 발견시 해당 인원 표시"""
        if not self.slack_client:
            print("⚠️ 슬랙 클라이언트 없음")
            return False
        
        try:
            # 검증 전용 채널 가져오기
            validation_channel = os.getenv(channel_env_var, "#아트실")
            print(f"📨 검증 리포트 전송 채널: {validation_channel}")
            print(f"🔍 슬랙 함수 내부 디버깅:")
            print(f"  - validation_issues: {len(validation_issues) if validation_issues else 0}개")
            print(f"  - all_alerts: {len(all_alerts) if all_alerts else 0}개")
            print(f"  - all_alerts 타입: {type(all_alerts)}")
            print(f"  - all_alerts 내용: {all_alerts}")
            
            # 메시지 구성
            if not validation_issues and not all_alerts:
                # 모든 검증 성공 + 점검 필요 알림 없음
                message_text = "[태스크월드 검토] 오류 없음 👍\n"
            elif not validation_issues and all_alerts:
                # 검증 성공 + 점검 필요 알림 있음
                message_text = "[태스크월드 검토] 오류 없음 👍\n"
            else:
                # 검증 실패 시 오류 인원 추출
                mentioned_people = self._extract_people_from_issues(validation_issues)
                
                # 메시지 시작
                message_text = "[태스크월드 검토] 오류 발견 ☠️\n"
                
                # 확인 필요한 사람들 표시
                if mentioned_people:
                    people_list = ", ".join(mentioned_people)
                    message_text += f"🧨 확인 필요한 사람 : {people_list}\n"
                
                # 상세 오류 목록
                message_text += f"\n```[오류 내용 확인]"
                for issue in validation_issues:
                    message_text += f"\n- {issue}"
                message_text += f"```"
            
            # 점검 필요 알림 추가 (코드 블록으로 표시)
            if all_alerts:
                message_text += f"\n```[점검 필요]"
                for alert in all_alerts:
                    message_text += f"\n- {alert}"
                message_text += f"\n```"
            
            # 메시지 전송
            msg_response = self.slack_client.chat_postMessage(
                channel=validation_channel,
                text=message_text
            )
            
            if msg_response.get('ok'):
                print("✅ 검증 리포트 전송 완료")
                return True
            else:
                print(f"❌ 메시지 전송 실패: {msg_response.get('error')}")
                return False
        
        except Exception as e:
            print(f"❌ 슬랙 전송 오류: {e}")
            return False

    def _extract_people_from_issues(self, validation_issues):
        """검증 오류에서 사람 이름 추출"""
        people = set()
        try:
            for issue in validation_issues:
                # "배진희님 태그 오류", "배진희님 합산 오류" 등에서 이름 추출
                if "님" in issue:
                    # "님" 앞의 단어를 찾기
                    parts = issue.split("님")
                    if len(parts) > 0:
                        # 첫 번째 부분에서 마지막 단어 (이름) 추출
                        name_part = parts[0].strip()
                        # 공백으로 분리해서 마지막 단어가 이름
                        words = name_part.split()
                        if words:
                            name = words[-1]  # 마지막 단어가 이름
                            # 한글 이름인지 확인 (한글 2글자 이상)
                            if len(name) >= 2 and all('\uac00' <= char <= '\ud7a3' for char in name):
                                people.add(name)
            
            print(f"🔍 검증 오류에서 추출된 인원: {list(people)}")
            return list(people)
            
        except Exception as e:
            print(f"⚠️ 인원 추출 중 오류: {e}")
            return []

    def run_validation_only(self, channel_env_var="SLACK_CHANNEL_VALIDATION"):
        """검증 전용 실행 (전체 프로세스와 동일하되 파일 업로드 없이 검증 결과만 슬랙 전송)"""
        try:
            print("🔍 검증 전용 프로세스 시작 (파일 업로드 없음)")
            print("=" * 60)
            
            # 환경변수에서 로그인 정보 읽기
            email = os.getenv("TASKWORLD_EMAIL")
            password = os.getenv("TASKWORLD_PASSWORD")
            workspace = os.getenv("TASKWORLD_WORKSPACE", WORKSPACE_NAME)
            
            if not email or not password:
                error_msg = "환경변수 필요: TASKWORLD_EMAIL, TASKWORLD_PASSWORD"
                print(f"❌ {error_msg}")
                self.send_validation_report_to_slack([error_msg], [], channel_env_var)
                return False
            
            # 1. 드라이버 설정
            print("1️⃣ 드라이버 설정...")
            if not self.setup_driver():
                error_msg = "브라우저 드라이버 설정 실패"
                self.send_validation_report_to_slack([error_msg], [], channel_env_var)
                return False
            
            # 2. 로그인
            print("\n2️⃣ 로그인...")
            if not self.login_to_taskworld(email, password):
                error_msg = "태스크월드 로그인 실패"
                self.send_validation_report_to_slack([error_msg], [], channel_env_var)
                return False
            
            # 3. 워크스페이스 이동
            print("\n3️⃣ 워크스페이스 이동...")
            if not self.navigate_to_workspace(workspace):
                error_msg = f"워크스페이스 '{workspace}' 접속 실패"
                self.send_validation_report_to_slack([error_msg], [], channel_env_var)
                return False
            
            # 4. CSV 내보내기
            print("\n4️⃣ CSV 내보내기...")
            csv_file = self.export_csv()
            
            if not csv_file:
                error_msg = "CSV 다운로드 실패"
                self.send_validation_report_to_slack([error_msg], [], channel_env_var)
                return False
            
            print(f"\n✅ 태스크월드 CSV 다운로드 완료: {csv_file}")

            # 5. CSV 처리 + 검증 (Due Date 체크 포함)
            print("\n5️⃣ CSV 파일 처리 및 검증...")
            result_df, removed_count, processed_file, validation_issues, all_alerts = self.process_csv(csv_file, include_due_date_check=True)
            
            if result_df is None:
                error_msg = processed_file
                self.send_validation_report_to_slack([error_msg], [], channel_env_var)
                return False
            
            print(f"✅ CSV 처리 완료: {processed_file}")
            
            # 검증 결과 표시
            if validation_issues:
                print(f"⚠️ 검증 이슈 {len(validation_issues)}개 발견:")
                for issue in validation_issues:
                    print(f"  - {issue}")
            else:
                print("✅ 모든 데이터 검증 통과")
            
            # Due Date 알림 표시
            if all_alerts:
                print(f"📅 점검 필요 알림 {len(all_alerts)}개:")
                for alert in all_alerts:
                    print(f"  - {alert}")
            else:
                print("📅 점검 필요한 작업 없음")
            
            # 6. 검증 결과 + 점검 필요 알림 슬랙 전송 (파일 업로드 없음)
            print("\n6️⃣ 검증 결과 슬랙 전송...")
            print(f"🔍 슬랙 전송 직전 디버깅:")
            print(f"  - validation_issues: {len(validation_issues)}개")
            print(f"  - all_alerts: {len(all_alerts)}개")
            print(f"  - all_alerts 내용: {all_alerts}")
            success = self.send_validation_report_to_slack(validation_issues, all_alerts, channel_env_var)
            
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
                
                print(f"📁 검증 완료 파일: {processed_file}")
                print(f"📂 파일 위치: {os.path.abspath(processed_file)}")
                if os.path.exists(processed_file):
                    file_size = os.path.getsize(processed_file)
                    print(f"📊 파일 정보: {file_size} 바이트")
                print("✅ 파일 정리 완료 - 검증된 파일 보존")
            except Exception as e:
                print(f"⚠️ 파일 정리 실패: {e}")
            
            if success:
                print("🎉 검증 전용 프로세스 완료!")
                return True
            else:
                print("❌ 검증 전용 프로세스 실패")
                return False
                
        except Exception as e:
            error_msg = f"검증 전용 프로세스 실패: {str(e)}"
            print(f"❌ {error_msg}")
            
            # 오류도 슬랙에 전송
            try:
                self.send_validation_report_to_slack([error_msg], [], channel_env_var)
            except:
                pass
            
            return False
            
        finally:
            # 브라우저 종료
            if self.driver:
                self.driver.quit()
                print("🔚 브라우저 종료")

    def send_to_slack(self, csv_file_path, stats=None, error_message=None, validation_issues=None, all_alerts=None):
        """
        슬랙에 리포트 전송 (파일 업로드 + 메시지) - 파일명 표시 및 쓰레드 오류 지원 + 점검 필요 알림
        """
        if not self.slack_client:
            print("⚠️ 슬랙 클라이언트가 없어 전송을 건너뜁니다.")
            return False
        
        try:
            # 1. 기본 인증 확인
            auth_response = self.slack_client.auth_test()
            if not auth_response.get('ok'):
                print(f"❌ 슬랙 인증 실패: {auth_response.get('error')}")
                return False
            print("✅ 슬랙 인증 성공")
            
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
                            print(f"✅ 채널 발견: #{found_channel['name']}")
                        else:
                            print(f"⚠️ 채널 '{channel_name}' 미발견, 원본 채널명 사용")
                except Exception as e:
                    print(f"⚠️ 채널 검색 실패, 원본 채널명 사용: {e}")
            
            # 3. 메시지 전송
            today = datetime.now(self.korea_tz).strftime("%Y-%m-%d")
            message_text = f"[{today}] 태스크월드 리포트 ({WORKSPACE_NAME})"

            if error_message:
                message_text += f"\n❌ 파일 업로드 실패: `{error_message}`"
            else:
                message_text += f"\n✅ 파일 업로드 성공: `{OUTPUT_FILENAME}`"

                # ⭐ 검증 결과 추가 (오류가 있을 때만) ⭐
                if validation_issues:
                    message_text += f"\n```"
                    message_text += f"\n[검증 오류]"
                    for issue in validation_issues:
                        message_text += f"\n- {issue}"
                    message_text += f"\n```"
                
                # ⭐ 점검 필요 알림 추가 (코드 블록으로 표시) ⭐
                if all_alerts:
                    message_text += f"\n```[점검 필요]"
                    for alert in all_alerts:
                        message_text += f"\n- {alert}"
                    message_text += f"\n```"
                    
            msg_response = self.slack_client.chat_postMessage(
                channel=actual_channel_id,
                text=message_text
            )
            
            if not msg_response.get('ok'):
                print(f"❌ 메시지 전송 실패: {msg_response.get('error')}")
                return False
            
            print("✅ 메시지 전송 성공")
            message_channel = msg_response.get('channel')  # 실제 전송된 채널 ID
            message_ts = msg_response.get('ts')  # 메시지 타임스탬프 (쓰레드용)
            
            # 4. 파일 업로드 (파일이 있고 에러가 아닌 경우에만)
            if csv_file_path and os.path.exists(csv_file_path) and not error_message:
                filename = os.path.basename(csv_file_path)
                print("📎 파일 업로드 시작...")
                
                try:
                    with open(csv_file_path, 'rb') as file_obj:
                        file_response = self.slack_client.files_upload_v2(
                            channel=message_channel,  # 메시지 전송에 성공한 실제 채널 ID 사용
                            file=file_obj,
                            filename=filename,
                            title=f"태스크월드 리포트 - {today}"
                        )
                    
                    if file_response.get('ok'):
                        print(f"✅ 파일 업로드 성공: \"{filename}\"")
                        return True
                    else:
                        error_detail = file_response.get('error', 'unknown')
                        print(f"❌ 파일 업로드 실패: \"{filename}\"")
                        print("⚠️ 메시지는 전송되었으나 파일 업로드 실패")
                        
                        # 쓰레드에 오류 상세 정보 전송
                        self._send_upload_error_thread(message_channel, message_ts, filename, error_detail, file_response)
                        return False
                        
                except Exception as file_error:
                    filename = os.path.basename(csv_file_path)
                    print(f"❌ 파일 업로드 실패: \"{filename}\"")
                    print("⚠️ 메시지는 전송되었으나 파일 업로드 예외")
                    
                    # 쓰레드에 예외 상세 정보 전송
                    self._send_upload_error_thread(message_channel, message_ts, filename, f"예외 발생: {str(file_error)}", None)
                    return False
            else:
                if error_message:
                    print("⚠️ 에러 알림이므로 파일 업로드 건너뜀")
                else:
                    print("⚠️ 파일이 없어 파일 업로드 건너뜀")
                return True  # 메시지만 전송 성공
        
        except Exception as e:
            print(f"❌ 슬랙 전송 중 오류: {e}")
            return False


    def _send_upload_error_thread(self, channel, thread_ts, filename, error_detail, full_response):
        """파일 업로드 실패 시 쓰레드에 상세 오류 정보 전송"""
        try:
            # 쓰레드 메시지 구성
            thread_text = f"🔍 **파일 업로드 실패 상세 정보**\n\n"
            thread_text += f"📁 파일명: `{filename}`\n"
            thread_text += f"❌ 오류: {error_detail}\n"
            
            # 추가 정보가 있으면 포함
            if full_response:
                if 'needed' in full_response:
                    thread_text += f"🔑 필요한 권한: {full_response.get('needed')}\n"
                if 'provided' in full_response:
                    thread_text += f"🔑 현재 권한: {full_response.get('provided')}\n"
            
            thread_text += f"\n💡 파일은 서버에 생성되었으니 수동으로 업로드 가능합니다."
            
            # 쓰레드 메시지 전송
            self.slack_client.chat_postMessage(
                channel=channel,
                text=thread_text,
                thread_ts=thread_ts
            )
            print("📨 오류 상세 정보를 쓰레드에 전송 완료")
            
        except Exception as e:
            print(f"⚠️ 쓰레드 오류 정보 전송 실패: {e}")

    def _is_clickable_button(self, element):
        """요소가 실제 클릭 가능한 버튼인지 확인"""
        try:
            # 1. 태그 이름으로 확인
            tag_name = element.tag_name.lower()
            if tag_name in ['button', 'input', 'a']:
                return True
            
            # 2. input 타입 확인
            if tag_name == 'input':
                input_type = element.get_attribute('type')
                if input_type in ['button', 'submit']:
                    return True
            
            # 3. 클릭 이벤트가 있는지 확인
            onclick = element.get_attribute('onclick')
            if onclick:
                return True
            
            # 4. CSS cursor가 pointer인지 확인
            cursor_style = element.value_of_css_property('cursor')
            if cursor_style == 'pointer':
                return True
            
            # 5. 역할(role)이 버튼인지 확인
            role = element.get_attribute('role')
            if role == 'button':
                return True
            
            # 6. 부모 요소가 버튼인지 확인
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
            
            # 7. 클래스명에 버튼 관련 키워드 있는지 확인
            class_name = element.get_attribute('class') or ""
            button_keywords = ['btn', 'button', 'clickable', 'action', 'export']
            if any(keyword in class_name.lower() for keyword in button_keywords):
                return True
            
            # 기본적으로 실제 버튼이 아닌 것으로 판단
            return False
            
        except Exception as e:
            print(f"   ⚠️ 버튼 확인 중 오류: {e}")
            return False
    
    def export_csv(self):
        """CSV 내보내기 실행"""
        try:
            print("📊 CSV 내보내기 시작...")
            print(f"📄 현재 URL: {self.driver.current_url}")
            
            # 다운로드 전 기존 CSV 파일 목록 저장 및 정리
            existing_csvs = glob.glob(os.path.join(self.download_dir, "*.csv"))
            print(f"📋 기존 CSV 파일 수: {len(existing_csvs)}")
            
            # 기존 export-projects 관련 파일들 삭제 (중복 방지)
            export_files_pattern = os.path.join(self.download_dir, "export-projects*.csv")
            export_files = glob.glob(export_files_pattern)
            
            for file in export_files:
                try:
                    os.remove(file)
                    print(f"🗑️ 기존 파일 삭제: {os.path.basename(file)}")
                except Exception as e:
                    print(f"⚠️ 파일 삭제 실패: {os.path.basename(file)} - {e}")
            
            # 다운로드 전 기존 CSV 파일 목록 다시 저장
            existing_csvs = glob.glob(os.path.join(self.download_dir, "*.csv"))
            if existing_csvs:
                print(f"📋 정리 후 남은 파일들: {[os.path.basename(f) for f in existing_csvs]}")
            
            time.sleep(3)
            
            # 1단계: URL을 직접 수정해서 설정 페이지로 이동
            print("⚙️ URL을 직접 수정해서 설정 페이지로 이동...")
            current_url = self.driver.current_url
            
            # view=board를 view=settings&menu=general로 교체
            if "view=board" in current_url:
                settings_url = current_url.replace("view=board", "view=settings&menu=general")
                print(f"📄 설정 페이지 URL: {settings_url}")
                self.driver.get(settings_url)
                time.sleep(3)  # 설정 페이지 로딩 대기
                print("✅ 설정 페이지로 이동 완료")
            else:
                print("⚠️ URL에 view=board가 없어서 직접 설정 페이지 구성을 시도합니다...")
                # URL 끝에 view=settings&menu=general 추가
                if "?" in current_url:
                    settings_url = current_url + "&view=settings&menu=general"
                else:
                    settings_url = current_url + "?view=settings&menu=general"
                
                print(f"📄 구성된 설정 URL: {settings_url}")
                self.driver.get(settings_url)
                time.sleep(3)
            
            # 2단계: CSV 내보내기 버튼 찾기
            print("📥 CSV 내보내기 버튼 찾는 중...")
            csv_export_selectors = [
                # 가장 구체적인 선택자들 (우선순위 높음)
                "//button[contains(@class, 'export') and contains(text(), 'CSV')]",
                "//button[contains(@data-action, 'csv') or contains(@data-action, 'export')]",
                "//button[contains(@onclick, 'csv') or contains(@onclick, 'export')]",
                "//input[@type='button' and contains(@value, 'CSV')]",
                "//a[contains(@href, 'csv') or contains(@href, 'export')]",
                
                # 텍스트 기반 (기존)
                "//button[contains(text(), 'CSV로 내보내기')]",
                "//*[contains(text(), 'CSV로 내보내기')]",
                "//div[contains(text(), 'CSV로 내보내기')]",
                "//span[contains(text(), 'CSV로 내보내기')]",
                "//a[contains(text(), 'CSV로 내보내기')]",
                
                # 더 넓은 범위
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
                    print(f"🔍 CSV 내보내기 선택자 시도 ({i+1}/{len(csv_export_selectors)}): {selector}")
                    
                    # 모든 매칭 요소 찾기
                    elements = self.driver.find_elements(By.XPATH, selector)
                    
                    if elements:
                        print(f"   📋 {len(elements)}개 요소 발견")
                        
                        # 각 요소 정보 출력
                        for j, element in enumerate(elements):
                            try:
                                tag_name = element.tag_name
                                text = element.text.strip()
                                is_enabled = element.is_enabled()
                                is_displayed = element.is_displayed()
                                
                                # 실제 버튼인지 확인
                                is_actual_button = self._is_clickable_button(element)
                                
                                print(f"   요소 {j+1}: {tag_name}, 텍스트: '{text}', 활성: {is_enabled}, 표시: {is_displayed}, 버튼: {is_actual_button}")
                                
                                # 클릭 가능한 실제 버튼인 첫 번째 요소 선택
                                if is_enabled and is_displayed and is_actual_button and not export_csv_btn:
                                    export_csv_btn = element
                                    found_selector = selector
                                    print(f"   ✅ 클릭 가능한 실제 버튼 선택!")
                                    
                            except Exception as e:
                                print(f"   ⚠️ 요소 정보 확인 실패: {e}")
                        
                        if export_csv_btn:
                            break
                            
                except Exception as e:
                    print(f"   ❌ 선택자 실패: {e}")
                    continue
            
            if not export_csv_btn:
                print("❌ CSV 내보내기 버튼을 찾을 수 없음")
                print("📋 페이지의 모든 텍스트 확인:")
                try:
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text
                    print(page_text[:500] + "..." if len(page_text) > 500 else page_text)
                except:
                    print("페이지 텍스트 가져오기 실패")
                return None
            
            print(f"✅ 선택된 버튼 - 선택자: {found_selector}")
            print(f"📋 버튼 정보: 태그={export_csv_btn.tag_name}, 텍스트='{export_csv_btn.text}'")
                
            print("🖱️ CSV 내보내기 버튼 클릭...")
            
            # 1차 시도: 일반 클릭
            try:
                export_csv_btn.click()
                print("✅ 일반 클릭 시도 완료")
            except Exception as e:
                print(f"⚠️ 일반 클릭 실패: {str(e).split('Stacktrace:')[0].strip()}")
            
            time.sleep(2)
            
            # 2차 시도: JavaScript 강제 클릭
            try:
                print("🔧 JavaScript 강제 클릭 시도...")
                self.driver.execute_script("arguments[0].click();", export_csv_btn)
                print("✅ JavaScript 클릭 완료")
            except Exception as e:
                print(f"⚠️ JavaScript 클릭 실패: {str(e).split('Stacktrace:')[0].strip()}")
            
            time.sleep(2)
            
            # 3차 시도: ActionChains 클릭
            try:
                print("🎯 ActionChains 클릭 시도...")
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(self.driver)
                actions.move_to_element(export_csv_btn).click().perform()
                print("✅ ActionChains 클릭 완료")
            except Exception as e:
                print(f"⚠️ ActionChains 클릭 실패: {str(e).split('Stacktrace:')[0].strip()}")
                
            time.sleep(3)
            
            print("📥 CSV 다운로드 시작...")
            
            # 다운로드 완료 대기 (새로운 파일이 생성될 때까지)
            timeout = 120  # 120초로 늘림 (원래 60초)
            check_interval = 2  # 2초마다 체크 (원래 1초)
            
            for i in range(0, timeout, check_interval):
                # 현재 CSV 파일 목록 확인
                current_csvs = glob.glob(os.path.join(self.download_dir, "*.csv"))
                new_csvs = [f for f in current_csvs if f not in existing_csvs]
                
                if new_csvs:
                    # 가장 최신 파일 찾기 (생성 시간 기준)
                    latest_file = max(new_csvs, key=os.path.getctime)
                    
                    # 파일 크기 확인 (0바이트가 아닌지)
                    file_size = os.path.getsize(latest_file)
                    print(f"✅ 새로운 CSV 파일 발견: {os.path.basename(latest_file)}")
                    print(f"📊 파일 크기: {file_size} 바이트")
                    
                    if file_size > 0:
                        print(f"🎯 최신 파일 선택: {latest_file}")
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
                        print(f"✅ Downloads 폴더에서 최신 파일 발견: {os.path.basename(latest_download)}")
                        
                        # 현재 폴더로 복사
                        import shutil
                        local_file = os.path.basename(latest_download)
                        shutil.copy(latest_download, local_file)
                        print(f"📋 파일 복사 완료: {local_file}")
                        
                        # Downloads의 원본 파일 삭제 (정리)
                        try:
                            os.remove(latest_download)
                            print(f"🗑️ Downloads 원본 파일 삭제: {os.path.basename(latest_download)}")
                        except:
                            pass
                            
                        return local_file
                
                # .crdownload 파일 확인 (Chrome 다운로드 중 파일)
                downloading_files = glob.glob(os.path.join(self.download_dir, "*.crdownload"))
                downloads_crdownload = glob.glob(os.path.expanduser("~/Downloads/*.crdownload"))
                
                if downloading_files or downloads_crdownload:
                    print(f"⏳ 다운로드 진행 중... ({i+check_interval}/{timeout}초)")
                elif i % 20 == 0:  # 20초마다 상태 출력
                    print(f"⏳ 다운로드 대기 중... ({i+check_interval}/{timeout}초)")
                    # 주기적으로 페이지 새로고침
                    if i > 0 and i % 60 == 0:
                        print("🔄 페이지 상태 확인 중...")
                        try:
                            # 현재 URL이 여전히 설정 페이지인지 확인
                            if "settings" not in self.driver.current_url:
                                print("⚠️ 설정 페이지에서 벗어남, 다시 시도 필요할 수 있음")
                        except:
                            pass
                
                time.sleep(check_interval)
            
            print("❌ CSV 다운로드 시간 초과")
            return None
            
        except Exception as e:
            print(f"❌ CSV 내보내기 실패: {e}")
            print(f"📄 현재 URL: {self.driver.current_url}")
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
            result_df, removed_count, processed_file, validation_issues, all_alerts = self.process_csv(csv_file, include_due_date_check=False)
            
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
            
            # Due Date 알림 표시
            if all_alerts:
                print(f"📅 점검 필요 알림 {len(all_alerts)}개:")
                for alert in all_alerts:
                    print(f"  - {alert}")
            else:
                print("📅 점검 필요한 작업 없음")
            
            # 6. 슬랙 전송 (검증 결과 + 점검 필요 알림 포함)
            print("\n6️⃣ 슬랙 리포트 전송...")
            if self.slack_client:
                # 통계 정보 구성
                stats_info = f"총 {len(result_df) + (removed_count or 0)}행 → 필터링 {removed_count or 0}행 → 최종 {len(result_df)}행"
                
                print(f"📊 전송할 통계: {stats_info}")
                print(f"📁 전송할 파일: {processed_file}")
                
                success = self.send_to_slack(processed_file, stats_info, None, validation_issues, all_alerts)
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


# ⭐ 수정된 메인 실행 부분 ⭐
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
    print(f"🕕 업무 종료 시간: {WORK_END_TIME_HOUR}시")
    
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
            print("\n🎉 완전 자동화 성공!")
            print(f"📁 최종 파일: {result}")
        else:
            print("\n❌ 완전 자동화 실패")
            exit(1)
