# selenium_taskworld_downloader.py - 브라우저 자동화로 CSV 다운로드 (디버깅 버전)
import os
import time
import glob
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import logging

logger = logging.getLogger(__name__)

class TaskworldSeleniumDownloader:
    def __init__(self, headless=True):
        """
        Selenium 기반 태스크월드 자동 다운로더
        
        Args:
            headless (bool): 브라우저를 숨김 모드로 실행할지 여부
        """
        self.headless = headless
        self.driver = None
        self.wait = None
        self.download_dir = os.path.abspath("./")  # 현재 디렉토리로 통일
        
        print(f"🤖 다운로더 초기화 - headless: {headless}")
        
    def setup_driver(self):
        """Chrome 드라이버 설정 (GitHub Actions용 최적화)"""
        try:
            print("🔧 Chrome 드라이버 설정 시작...")
            chrome_options = Options()
            
            # headless 설정 (조건부) - 사용자가 수정한 부분
            if self.headless:
                chrome_options.add_argument("--headless")
                print("👻 Headless 모드로 실행")
            else:
                print("🖥️ 브라우저 창 보기 모드로 실행")
            
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            
            # headless 설정 (조건부)
            if self.headless:
            chrome_options.add_argument("--headless")
            #chrome_options.add_argument("--disable-web-security")
            
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
            
            # 구글 로그인 버튼 찾기 시도
            try:
                print("🔍 구글 로그인 버튼 찾는 중...")
                google_login_selectors = [
                    "//button[contains(text(), 'Google')]",
                    "//button[contains(@class, 'google')]", 
                    "//a[contains(text(), 'Google')]",
                    "//div[contains(text(), 'Google')]"
                ]
                
                google_login_btn = None
                for selector in google_login_selectors:
                    try:
                        google_login_btn = self.wait.until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        print(f"✅ 구글 로그인 버튼 발견: {selector}")
                        break
                    except:
                        print(f"❌ 선택자 실패: {selector}")
                        continue
                
                if google_login_btn:
                    print("🖱️ 구글 로그인 버튼 클릭...")
                    google_login_btn.click()
                    time.sleep(2)
                    
                    # 구글 로그인 처리
                    return self._handle_google_login(email, password)
                else:
                    print("⚠️ 구글 로그인 버튼을 찾을 수 없음. 일반 로그인 시도...")
                    return self._handle_email_login(email, password)
                
            except Exception as e:
                print(f"⚠️ 구글 로그인 시도 중 오류: {e}")
                print("📧 일반 이메일 로그인으로 전환...")
                return self._handle_email_login(email, password)
                
        except Exception as e:
            print(f"❌ 로그인 전체 프로세스 실패: {e}")
            return False
    
    def _handle_google_login(self, email, password):
        """구글 로그인 처리"""
        try:
            print("🔍 구글 로그인 페이지 처리 시작...")
            time.sleep(3)
            
            print(f"📄 현재 URL: {self.driver.current_url}")
            
            # 구글 로그인 페이지에서 이메일 입력
            print("📧 이메일 입력 필드 찾는 중...")
            email_input = self.wait.until(
                EC.presence_of_element_located((By.ID, "identifierId"))
            )
            print("✅ 이메일 입력 필드 발견")
            
            email_input.clear()
            email_input.send_keys(email)
            print(f"📝 이메일 입력 완료: {email[:3]}***")
            
            # 다음 버튼 클릭
            print("🖱️ 다음 버튼 찾는 중...")
            next_btn = self.driver.find_element(By.ID, "identifierNext")
            next_btn.click()
            print("✅ 다음 버튼 클릭 완료")
            
            time.sleep(3)
            
            # 패스워드 입력
            print("🔒 패스워드 입력 필드 찾는 중...")
            password_input = self.wait.until(
                EC.element_to_be_clickable((By.NAME, "password"))
            )
            print("✅ 패스워드 입력 필드 발견")
            
            password_input.clear()
            password_input.send_keys(password)
            print("🔒 패스워드 입력 완료")
            
            # 패스워드 다음 버튼
            print("🖱️ 로그인 버튼 클릭...")
            password_next = self.driver.find_element(By.ID, "passwordNext")
            password_next.click()
            print("✅ 로그인 버튼 클릭 완료")
            
            # 태스크월드로 리다이렉트 대기
            print("⏳ 태스크월드로 리다이렉트 대기 중...")
            time.sleep(5)
            
            # URL 확인
            current_url = self.driver.current_url
            print(f"📄 리다이렉트 후 URL: {current_url}")
            
            if "taskworld.com" in current_url:
                print("✅ 구글 로그인 성공!")
                return True
            else:
                print("❌ 태스크월드로 리다이렉트되지 않음")
                return False
            
        except Exception as e:
            print(f"❌ 구글 로그인 실패: {e}")
            print(f"📄 현재 URL: {self.driver.current_url}")
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
    
    def navigate_to_workspace(self, workspace_name="아트실 일정 - 2025 6주기"):
        """특정 워크스페이스로 이동"""
        try:
            print(f"📂 워크스페이스 '{workspace_name}' 찾는 중...")
            print(f"📄 현재 URL: {self.driver.current_url}")
            
            time.sleep(3)  # 페이지 로딩 대기
            
            # 여러 선택자로 워크스페이스 찾기 시도
            workspace_selectors = [
                f"//a[contains(text(), '{workspace_name}')]",
                f"//div[contains(text(), '{workspace_name}')]",
                f"//span[contains(text(), '{workspace_name}')]",
                f"//button[contains(text(), '{workspace_name}')]"
            ]
            
            workspace_link = None
            for selector in workspace_selectors:
                try:
                    print(f"🔍 선택자 시도: {selector}")
                    workspace_link = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    print(f"✅ 워크스페이스 링크 발견: {selector}")
                    break
                except:
                    print(f"❌ 선택자 실패: {selector}")
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
    
    def export_csv(self):
        """CSV 내보내기 실행"""
        try:
            print("📊 CSV 내보내기 시작...")
            print(f"📄 현재 URL: {self.driver.current_url}")
            
            # 다운로드 전 기존 CSV 파일 목록 저장
            existing_csvs = glob.glob(os.path.join(self.download_dir, "*.csv"))
            print(f"📋 기존 CSV 파일 수: {len(existing_csvs)}")
            if existing_csvs:
                print(f"📋 기존 파일들: {existing_csvs}")
            
            time.sleep(3)
            
            # 설정 메뉴 찾기 (여러 선택자 시도)
            print("⚙️ 설정 메뉴 찾는 중...")
            settings_selectors = [
                "//button[contains(@class, 'settings')]",
                "//button[contains(@title, '설정')]",
                "//div[contains(@class, 'settings')]",
                "//a[contains(@href, 'settings')]",
                "//i[contains(@class, 'settings')]/..",
                "//button[contains(text(), '설정')]"
            ]
            
            settings_btn = None
            for selector in settings_selectors:
                try:
                    print(f"🔍 설정 선택자 시도: {selector}")
                    settings_btn = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    print(f"✅ 설정 버튼 발견: {selector}")
                    break
                except:
                    print(f"❌ 설정 선택자 실패: {selector}")
                    continue
            
            if not settings_btn:
                print("❌ 설정 버튼을 찾을 수 없음")
                return None
                
            print("🖱️ 설정 버튼 클릭...")
            settings_btn.click()
            time.sleep(3)
            
            # CSV 내보내기 버튼 찾기
            print("📥 CSV 내보내기 버튼 찾는 중...")
            csv_export_selectors = [
                "//button[contains(text(), 'CSV')]",
                "//button[contains(text(), '내보내기')]",
                "//a[contains(text(), 'CSV')]",
                "//div[contains(text(), 'CSV')]",
                "//span[contains(text(), 'CSV')]"
            ]
            
            export_csv_btn = None
            for selector in csv_export_selectors:
                try:
                    print(f"🔍 CSV 내보내기 선택자 시도: {selector}")
                    export_csv_btn = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    print(f"✅ CSV 내보내기 버튼 발견: {selector}")
                    break
                except:
                    print(f"❌ CSV 내보내기 선택자 실패: {selector}")
                    continue
            
            if not export_csv_btn:
                print("❌ CSV 내보내기 버튼을 찾을 수 없음")
                return None
                
            print("🖱️ CSV 내보내기 버튼 클릭...")
            export_csv_btn.click()
            
            print("📥 CSV 다운로드 시작...")
            
            # 다운로드 완료 대기 (새로운 파일이 생성될 때까지)
            timeout = 60  # 60초 대기
            
            for i in range(timeout):
                # 현재 CSV 파일 목록 확인
                current_csvs = glob.glob(os.path.join(self.download_dir, "*.csv"))
                new_csvs = [f for f in current_csvs if f not in existing_csvs]
                
                if new_csvs:
                    # 가장 최신 파일 찾기
                    latest_file = max(new_csvs, key=os.path.getctime)
                    print(f"✅ CSV 다운로드 완료: {latest_file}")
                    
                    # 파일 크기 확인
                    file_size = os.path.getsize(latest_file)
                    print(f"📊 파일 크기: {file_size} 바이트")
                    
                    return latest_file
                
                # .crdownload 파일 확인 (Chrome 다운로드 중 파일)
                downloading_files = glob.glob(os.path.join(self.download_dir, "*.crdownload"))
                if downloading_files:
                    print(f"⏳ 다운로드 진행 중... ({i+1}/{timeout}초)")
                elif i % 10 == 0:  # 10초마다 상태 출력
                    print(f"⏳ 다운로드 대기 중... ({i+1}/{timeout}초)")
                
                time.sleep(1)
            
            print("❌ CSV 다운로드 시간 초과")
            return None
            
        except Exception as e:
            print(f"❌ CSV 내보내기 실패: {e}")
            print(f"📄 현재 URL: {self.driver.current_url}")
            return None
    
    def download_taskworld_csv(self, email, password, workspace_name="아트실 일정 - 2025 6주기"):
        """전체 프로세스 실행"""
        try:
            print("🚀 태스크월드 CSV 자동 다운로드 시작")
            print("=" * 50)
            
            # 1. 드라이버 설정
            print("1️⃣ 드라이버 설정...")
            if not self.setup_driver():
                return None
            
            # 2. 로그인
            print("\n2️⃣ 로그인...")
            if not self.login_to_taskworld(email, password):
                return None
            
            # 3. 워크스페이스 이동
            print("\n3️⃣ 워크스페이스 이동...")
            if not self.navigate_to_workspace(workspace_name):
                return None
            
            # 4. CSV 내보내기
            print("\n4️⃣ CSV 내보내기...")
            csv_file = self.export_csv()
            
            if csv_file:
                print(f"\n🎉 전체 프로세스 완료! 파일: {csv_file}")
                return csv_file
            else:
                print("\n❌ CSV 다운로드 실패")
                return None
                
        except Exception as e:
            print(f"\n❌ 전체 프로세스 실패: {e}")
            return None
            
        finally:
            # 브라우저 종료 (headless=False일 때는 5초 대기)
            if not self.headless:
                print("\n⏳ 브라우저 확인을 위해 5초 후 종료...")
                time.sleep(5)
            
            if self.driver:
                self.driver.quit()
                print("🔚 브라우저 종료")

# 디버깅용 함수
def debug_file_system():
    """현재 디렉토리 상태 출력"""
    current_dir = os.getcwd()
    print(f"📁 현재 작업 디렉토리: {current_dir}")
    
    # 모든 파일 목록
    all_files = os.listdir('.')
    print(f"📋 전체 파일 목록: {all_files}")
    
    # CSV 파일만 찾기
    csv_files = glob.glob("*.csv")
    print(f"📊 CSV 파일들: {csv_files}")
    
    if csv_files:
        for csv_file in csv_files:
            file_size = os.path.getsize(csv_file)
            mod_time = datetime.fromtimestamp(os.path.getmtime(csv_file))
            print(f"  - {csv_file}: {file_size}바이트, 수정시간: {mod_time}")

# 사용 예제
if __name__ == "__main__":
    # 먼저 파일 시스템 상태 확인
    print("🔍 현재 파일 시스템 상태:")
    debug_file_system()
    print("=" * 50)
    
    # 환경변수에서 로그인 정보 읽기
    email = os.getenv("TASKWORLD_EMAIL")
    password = os.getenv("TASKWORLD_PASSWORD")
    workspace = os.getenv("TASKWORLD_WORKSPACE", "아트실 일정 - 2025 6주기")
    
    # 환경변수가 없으면 테스트 모드
    if not email or not password:
        print("❌ TASKWORLD_EMAIL, TASKWORLD_PASSWORD 환경변수가 필요합니다.")
        print("🧪 테스트 모드: 브라우저만 열어서 확인")
        
        # 환경변수 없이도 브라우저 열어서 확인 가능
        test_email = input("테스트용 이메일 입력 (또는 Enter로 건너뛰기): ").strip()
        test_password = input("테스트용 패스워드 입력 (또는 Enter로 건너뛰기): ").strip()
        
        if test_email and test_password:
            email, password = test_email, test_password
        else:
            print("⏭️ 로그인 정보 없이 파일 시스템만 확인")
            exit(0)
    
    # 다운로더 실행 (headless=False로 브라우저 창 보기)
    downloader = TaskworldSeleniumDownloader(headless=False)
    csv_file = downloader.download_taskworld_csv(email, password, workspace)
    
    if csv_file:
        print(f"\n✅ 다운로드 성공: {csv_file}")
        
        # 파일을 표준 이름으로 복사
        import shutil
        shutil.copy(csv_file, "taskworld_data.csv")
        print("📋 taskworld_data.csv로 복사 완료")
        
        # 최종 상태 확인
        print("\n🔍 다운로드 후 파일 시스템 상태:")
        debug_file_system()
    else:
        print("\n❌ 다운로드 실패")
        print("\n🔍 실패 후 파일 시스템 상태:")
        debug_file_system()
