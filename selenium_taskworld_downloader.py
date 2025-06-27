# selenium_taskworld_downloader.py - 브라우저 자동화로 CSV 다운로드
import os
import time
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
        
    def setup_driver(self):
        """Chrome 드라이버 설정 (GitHub Actions용 최적화)"""
        try:
            chrome_options = Options()
            
            # GitHub Actions를 위한 headless 설정
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # 다운로드 설정
            download_dir = os.path.abspath("./")  # 현재 디렉토리에 다운로드
            
            prefs = {
                "download.default_directory": download_dir,
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
            
            logger.info("✅ Chrome 드라이버 설정 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ 드라이버 설정 실패: {e}")
            return False
    
    def login_to_taskworld(self, email, password):
        """태스크월드 로그인"""
        try:
            logger.info("🔐 태스크월드 로그인 시작...")
            
            # 태스크월드 로그인 페이지로 이동
            self.driver.get("https://asia-enterprise.taskworld.com/login")
            
            # 구글 로그인 버튼 찾기 (사용자가 구글 로그인 사용한다고 했음)
            try:
                google_login_btn = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Google') or contains(@class, 'google')]"))
                )
                google_login_btn.click()
                logger.info("🔍 구글 로그인 버튼 클릭")
                
                # 구글 로그인 처리
                return self._handle_google_login(email, password)
                
            except:
                # 일반 로그인 시도
                logger.info("📧 일반 이메일 로그인 시도")
                return self._handle_email_login(email, password)
                
        except Exception as e:
            logger.error(f"❌ 로그인 실패: {e}")
            return False
    
    def _handle_google_login(self, email, password):
        """구글 로그인 처리"""
        try:
            # 구글 로그인 페이지에서 이메일 입력
            email_input = self.wait.until(
                EC.presence_of_element_located((By.ID, "identifierId"))
            )
            email_input.send_keys(email)
            
            # 다음 버튼 클릭
            next_btn = self.driver.find_element(By.ID, "identifierNext")
            next_btn.click()
            
            # 패스워드 입력
            password_input = self.wait.until(
                EC.element_to_be_clickable((By.NAME, "password"))
            )
            password_input.send_keys(password)
            
            # 패스워드 다음 버튼
            password_next = self.driver.find_element(By.ID, "passwordNext")
            password_next.click()
            
            # 태스크월드로 리다이렉트 대기
            self.wait.until(
                EC.url_contains("taskworld.com")
            )
            
            logger.info("✅ 구글 로그인 성공!")
            return True
            
        except Exception as e:
            logger.error(f"❌ 구글 로그인 실패: {e}")
            return False
    
    def _handle_email_login(self, email, password):
        """일반 이메일 로그인 처리"""
        try:
            # 이메일 입력
            email_input = self.wait.until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            email_input.send_keys(email)
            
            # 패스워드 입력
            password_input = self.driver.find_element(By.NAME, "password")
            password_input.send_keys(password)
            
            # 로그인 버튼 클릭
            login_btn = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_btn.click()
            
            # 로그인 완료 대기 (URL 변경 또는 특정 요소 나타남)
            time.sleep(5)
            
            logger.info("✅ 이메일 로그인 성공!")
            return True
            
        except Exception as e:
            logger.error(f"❌ 이메일 로그인 실패: {e}")
            return False
    
    def navigate_to_workspace(self, workspace_name="아트실 일정 - 2025 6주기"):
        """특정 워크스페이스로 이동"""
        try:
            logger.info(f"📂 워크스페이스 '{workspace_name}' 찾는 중...")
            
            # 워크스페이스 목록에서 찾기
            workspace_link = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, f"//a[contains(text(), '{workspace_name}')]"))
            )
            workspace_link.click()
            
            # 워크스페이스 로딩 대기
            time.sleep(3)
            
            logger.info(f"✅ '{workspace_name}' 워크스페이스 접속 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ 워크스페이스 접속 실패: {e}")
            return False
    
    def export_csv(self):
        """CSV 내보내기 실행"""
        try:
            logger.info("📊 CSV 내보내기 시작...")
            
            # 설정 메뉴 찾기 (기어 아이콘 또는 설정 버튼)
            settings_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'settings') or contains(@title, '설정')]"))
            )
            settings_btn.click()
            
            # CSV 내보내기 버튼 찾기
            export_csv_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'CSV') or contains(text(), '내보내기')]"))
            )
            export_csv_btn.click()
            
            logger.info("📥 CSV 다운로드 시작...")
            
            # 다운로드 완료 대기 (파일이 생성될 때까지)
            download_dir = "./downloads"
            timeout = 60  # 60초 대기
            
            for i in range(timeout):
                csv_files = [f for f in os.listdir(download_dir) if f.endswith('.csv')]
                if csv_files:
                    # 가장 최신 파일 찾기
                    latest_file = max([os.path.join(download_dir, f) for f in csv_files], 
                                    key=os.path.getctime)
                    logger.info(f"✅ CSV 다운로드 완료: {latest_file}")
                    return latest_file
                
                time.sleep(1)
            
            logger.error("❌ CSV 다운로드 시간 초과")
            return None
            
        except Exception as e:
            logger.error(f"❌ CSV 내보내기 실패: {e}")
            return None
    
    def download_taskworld_csv(self, email, password, workspace_name="아트실 일정 - 2025 6주기"):
        """전체 프로세스 실행"""
        try:
            logger.info("🚀 태스크월드 CSV 자동 다운로드 시작")
            
            # 1. 드라이버 설정
            if not self.setup_driver():
                return None
            
            # 2. 로그인
            if not self.login_to_taskworld(email, password):
                return None
            
            # 3. 워크스페이스 이동
            if not self.navigate_to_workspace(workspace_name):
                return None
            
            # 4. CSV 내보내기
            csv_file = self.export_csv()
            
            if csv_file:
                logger.info(f"🎉 전체 프로세스 완료! 파일: {csv_file}")
                return csv_file
            else:
                logger.error("❌ CSV 다운로드 실패")
                return None
                
        except Exception as e:
            logger.error(f"❌ 전체 프로세스 실패: {e}")
            return None
            
        finally:
            # 브라우저 종료
            if self.driver:
                self.driver.quit()
                logger.info("🔚 브라우저 종료")

# 사용 예제
if __name__ == "__main__":
    # 환경변수에서 로그인 정보 읽기
    email = os.getenv("TASKWORLD_EMAIL")
    password = os.getenv("TASKWORLD_PASSWORD")
    workspace = os.getenv("TASKWORLD_WORKSPACE", "아트실 일정 - 2025 6주기")
    
    if not email or not password:
        print("❌ TASKWORLD_EMAIL, TASKWORLD_PASSWORD 환경변수가 필요합니다.")
        exit(1)
    
    # 다운로더 실행
    downloader = TaskworldSeleniumDownloader(headless=True)
    csv_file = downloader.download_taskworld_csv(email, password, workspace)
    
    if csv_file:
        print(f"✅ 다운로드 성공: {csv_file}")
        
        # 파일을 표준 이름으로 복사
        import shutil
        shutil.copy(csv_file, "taskworld_data.csv")
        print("📋 taskworld_data.csv로 복사 완료")
    else:
        print("❌ 다운로드 실패")
        exit(1)
