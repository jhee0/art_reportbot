# selenium_taskworld_downloader.py - 완전 자동화 스크립트 (간소화 버전)
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

# .env 파일 로드
load_dotenv()

# ==========================================
# 📅 월별 설정 변수 (매월 수정 필요)
# ==========================================
WORKSPACE_NAME = "아트실 일정 - 2025 6주기"  # 🔄 한달마다 수정하세요!
OUTPUT_FILENAME = "25_6.csv"  # 🔄 한달마다 수정하세요!

# ==========================================
# 🔧 검증 설정 변수 (필요시 수정)
# ==========================================
MIN_REQUIRED_HOURS = 160  # 🔄 필요시 수정하세요! (개인별 최소 시간)

# ==========================================
# 🗂️ 파일 경로 설정
# ==========================================
FIRST_TAGS_FILE = "first_tags.txt"
SECOND_TAGS_FILE = "second_tags.txt"
EXCLUDE_VALUES_FILE = "exclude_values.txt"

# ==========================================
# 기타 설정
# ==========================================
DEFAULT_HEADLESS = True  # 브라우저 창 보기/숨기기


class TaskworldSeleniumDownloader:
    def __init__(self, headless=DEFAULT_HEADLESS):
        self.headless = headless
        self.driver = None
        self.wait = None
        self.download_dir = os.path.abspath("./")
        
        # 슬랙 봇 설정
        self.slack_token = os.getenv("SLACK_BOT_TOKEN")
        self.slack_channel = os.getenv("SLACK_CHANNEL", "#아트실")
        self.slack_client = None
        self.korea_tz = timezone(timedelta(hours=9))
        
        print(f"🤖 자동화 다운로더 초기화 - {WORKSPACE_NAME}")
        print(f"📄 출력 파일: {OUTPUT_FILENAME}, 최소시간: {MIN_REQUIRED_HOURS}시간")
        
        # 슬랙 봇 초기화
        if self.slack_token:
            try:
                self.slack_client = WebClient(token=self.slack_token)
                response = self.slack_client.auth_test()
                print(f"✅ 슬랙 봇 연결 성공: {response['user']}")
            except SlackApiError as e:
                print(f"❌ 슬랙 봇 연결 실패: {e.response['error']}")
        else:
            print("⚠️ 슬랙 토큰 없음 - 전송 기능 비활성화")
        
    def setup_driver(self):
        """Chrome 드라이버 설정"""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # 다운로드 설정
            prefs = {
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            }
            chrome_options.add_experimental_option("prefs", prefs)
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 30)
            
            print("✅ Chrome 드라이버 설정 완료")
            return True
            
        except Exception as e:
            print(f"❌ 드라이버 설정 실패: {e}")
            return False
    
    def load_exclude_values(self):
        """제외할 Tasklist 값들을 파일에서 로드"""
        try:
            with open(EXCLUDE_VALUES_FILE, 'r', encoding='utf-8') as f:
                exclude_values = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            print(f"✅ 제외값 로드: {len(exclude_values)}개")
            return exclude_values
        except Exception as e:
            print(f"❌ 제외값 로드 실패: {e}")
            return ["주요일정", "아트실", "UI팀", "리소스팀", "디자인팀", "TA팀"]
    
    def login_to_taskworld(self, email, password):
        """태스크월드 로그인"""
        try:
            print("🔐 태스크월드 로그인...")
            self.driver.get("https://asia-enterprise.taskworld.com/login")
            time.sleep(3)
            
            # 이메일 입력
            email_input = self.wait.until(EC.presence_of_element_located((By.NAME, "email")))
            email_input.clear()
            email_input.send_keys(email)
            
            # 패스워드 입력
            password_input = self.driver.find_element(By.NAME, "password")
            password_input.clear()
            password_input.send_keys(password)
            
            # 로그인 버튼 클릭
            login_btn = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_btn.click()
            
            time.sleep(5)
            print("✅ 로그인 완료")
            return True
            
        except Exception as e:
            print(f"❌ 로그인 실패: {e}")
            return False
    
    def navigate_to_workspace(self, workspace_name=WORKSPACE_NAME):
        """워크스페이스로 이동"""
        try:
            print(f"📂 워크스페이스 '{workspace_name}' 접속...")
            time.sleep(3)
            
            # 프로젝트 페이지로 이동
            current_url = self.driver.current_url
            if "#/home" in current_url:
                project_url = current_url.replace("#/home", "#/projects")
            else:
                project_url = current_url + "#/projects"
            
            self.driver.get(project_url)
            time.sleep(3)
            
            # 워크스페이스 찾기
            workspace_selectors = [
                f"//a[contains(text(), '{workspace_name}')]",
                f"//div[contains(text(), '{workspace_name}')]",
                f"//span[contains(text(), '{workspace_name}')]",
                f"//*[contains(text(), '{workspace_name}')]"
            ]
            
            workspace_link = None
            for selector in workspace_selectors:
                try:
                    workspace_link = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    break
                except:
                    continue
            
            if not workspace_link:
                print("❌ 워크스페이스를 찾을 수 없음")
                return False
            
            workspace_link.click()
            time.sleep(5)
            print("✅ 워크스페이스 접속 완료")
            return True
            
        except Exception as e:
            print(f"❌ 워크스페이스 접속 실패: {e}")
            return False

    def load_allowed_tags(self):
        """태그 설정 파일에서 로드"""
        try:
            with open(FIRST_TAGS_FILE, 'r', encoding='utf-8') as f:
                first_tags = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            
            with open(SECOND_TAGS_FILE, 'r', encoding='utf-8') as f:
                second_tags = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            
            print(f"✅ 태그 설정 로드: 첫번째 {len(first_tags)}개, 두번째 {len(second_tags)}개")
            return first_tags, second_tags
            
        except Exception as e:
            print(f"❌ 태그 설정 로드 실패: {e}")
            return [], []
    
    def validate_tags(self, df, first_tags, second_tags):
        """태그 검증"""
        tag_validation_issues = []
        
        if 'Tags' not in df.columns:
            return ["Tags 열이 존재하지 않습니다."]
        
        for idx, row in df.iterrows():
            person_name = row['Tasklist']
            tags = row['Tags']
            
            if pd.isna(tags) or tags == '' or tags == 0:
                continue
            
            # 이름 그룹핑
            if pd.isna(person_name) or person_name == '':
                person_group = '미분류'
            else:
                name_str = str(person_name).strip()
                person_group = name_str[:3] if len(name_str) >= 3 else name_str
            
            # 태그 분리
            tag_list = str(tags).split(',')
            tag_list = [tag.strip() for tag in tag_list if tag.strip()]
            
            if len(tag_list) == 0:
                continue
            
            # 첫 번째 태그 검증 (부분 일치)
            first_tag = tag_list[0]
            first_tag_valid = any(first_tag.startswith(allowed) for allowed in first_tags)
            
            if not first_tag_valid:
                issue_msg = f"{person_group}님 태그 오류 (첫번째: '{first_tag}')"
                if issue_msg not in tag_validation_issues:
                    tag_validation_issues.append(issue_msg)
                continue
            
            # 두 번째 태그 검증 (완전 일치)
            if len(tag_list) >= 2:
                second_tag = tag_list[1]
                if second_tag not in second_tags:
                    issue_msg = f"{person_group}님 태그 오류 (두번째: '{second_tag}')"
                    if issue_msg not in tag_validation_issues:
                        tag_validation_issues.append(issue_msg)
        
        return tag_validation_issues
    
    def validate_time_totals(self, df, min_hours):
        """시간 합계 검증"""
        validation_issues = []
        
        def convert_time_to_hours(time_str):
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
                        return round(hours + (minutes / 60.0) + (seconds / 3600.0), 1)
                
                return round(float(time_str), 1)
            except:
                return 0.0
        
        def get_name_group(tasklist_name):
            if pd.isna(tasklist_name) or tasklist_name == '':
                return '미분류'
            name_str = str(tasklist_name).strip()
            return name_str[:3] if len(name_str) >= 3 else name_str
        
        # 시간 데이터 변환
        df['Time_Hours'] = df['Time_Spent'].apply(convert_time_to_hours)
        df['Name_Group'] = df['Tasklist'].apply(get_name_group)
        
        # 그룹별 시간 합계 계산
        group_totals = df.groupby('Name_Group')['Time_Hours'].sum()
        
        print(f"📊 개인별 시간 합계 (기준: {min_hours}시간):")
        for name_group, total_hours in group_totals.items():
            total_hours = round(total_hours, 1)
            print(f"  - {name_group}: {total_hours}시간")
            
            if total_hours != min_hours:
                issue_msg = f"{name_group}님 합산 오류 (현재: {total_hours}시간, 기준: {min_hours}시간)"
                validation_issues.append(issue_msg)
        
        return validation_issues
    
    def validate_csv_data(self, df, min_hours=MIN_REQUIRED_HOURS):
        """CSV 데이터 검증"""
        try:
            print("🔍 CSV 데이터 검증 시작...")
            
            if len(df.columns) < 4:
                return ["❌ 열 수가 부족합니다."]
            
            df.columns = ['Tasklist', 'Task', 'Tags', 'Time_Spent']
            
            # 태그 검증
            first_tags, second_tags = self.load_allowed_tags()
            tag_issues = self.validate_tags(df, first_tags, second_tags)
            
            # 시간 검증
            time_issues = self.validate_time_totals(df, min_hours)
            
            all_issues = time_issues + tag_issues
            
            if not all_issues:
                print("✅ 모든 검증 통과!")
            else:
                print(f"❌ {len(all_issues)}개 검증 이슈 발견")
                
            return all_issues
            
        except Exception as e:
            return [f"검증 중 오류: {str(e)}"]
    
    def process_csv(self, input_file, columns=['Tasklist', 'Task', 'Tags', 'Time Spent']):
        """CSV 파일 처리"""
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
            
            # 열 선택
            missing_columns = [col for col in columns if col not in df_filtered.columns]
            if missing_columns:
                return None, None, f"열을 찾을 수 없음: {missing_columns}", []
            
            selected_df = df_filtered[columns]
            
            # 검증
            validation_issues = self.validate_csv_data(selected_df, min_hours=MIN_REQUIRED_HOURS)
            
            # 파일 저장
            output_file = OUTPUT_FILENAME
            if os.path.exists(output_file):
                os.remove(output_file)
            
            selected_df.to_csv(output_file, index=False, header=False, encoding='utf-8-sig')
            print(f"✅ CSV 처리 완료: {len(selected_df)}행 → {output_file}")
            
            return selected_df, removed_count, output_file, validation_issues
            
        except Exception as e:
            return None, None, f"CSV 처리 오류: {str(e)}", []

    def send_to_slack(self, csv_file_path, stats=None, error_message=None, validation_issues=None):
        """슬랙 전송"""
        if not self.slack_client:
            return False
        
        try:
            # 메시지 구성
            today = datetime.now(self.korea_tz).strftime("%Y-%m-%d")
            message_text = f"[{today}] 태스크월드 리포트 ({WORKSPACE_NAME})"

            if error_message:
                message_text += f"\n❌ 실패: {error_message}"
            else:
                message_text += f"\n✅ 성공: {OUTPUT_FILENAME}"
                if validation_issues:
                    message_text += f"\n\n```[검증 오류]"
                    for issue in validation_issues:
                        message_text += f"\n- {issue}"
                    message_text += f"```"
            
            # 메시지 전송
            msg_response = self.slack_client.chat_postMessage(
                channel=self.slack_channel,
                text=message_text
            )
            
            if not msg_response.get('ok'):
                print(f"❌ 메시지 전송 실패")
                return False
            
            # 파일 업로드
            if csv_file_path and os.path.exists(csv_file_path) and not error_message:
                with open(csv_file_path, 'rb') as file_obj:
                    file_response = self.slack_client.files_upload_v2(
                        channel=msg_response.get('channel'),
                        file=file_obj,
                        filename=os.path.basename(csv_file_path),
                        title=f"태스크월드 리포트 - {today}"
                    )
                
                if file_response.get('ok'):
                    print("✅ 슬랙 전송 완료")
                    return True
                else:
                    print("❌ 파일 업로드 실패")
                    return False
            
            return True
        
        except Exception as e:
            print(f"❌ 슬랙 전송 오류: {e}")
            return False
    
    def export_csv(self):
        """CSV 내보내기"""
        try:
            print("📊 CSV 내보내기...")
            
            # 기존 파일 정리
            existing_csvs = glob.glob(os.path.join(self.download_dir, "*.csv"))
            export_files = glob.glob(os.path.join(self.download_dir, "export-projects*.csv"))
            for file in export_files:
                try:
                    os.remove(file)
                except:
                    pass
            
            # 설정 페이지로 이동
            current_url = self.driver.current_url
            if "view=board" in current_url:
                settings_url = current_url.replace("view=board", "view=settings&menu=general")
            else:
                settings_url = current_url + "?view=settings&menu=general"
            
            self.driver.get(settings_url)
            time.sleep(3)
            
            # CSV 내보내기 버튼 찾기
            csv_export_selectors = [
                "//button[contains(text(), 'CSV로 내보내기')]",
                "//button[contains(text(), 'CSV')]",
                "//button[contains(text(), '내보내기')]",
                "//*[contains(text(), 'CSV로 내보내기')]",
            ]
            
            export_csv_btn = None
            for selector in csv_export_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        if element.is_enabled() and element.is_displayed():
                            export_csv_btn = element
                            break
                    if export_csv_btn:
                        break
                except:
                    continue
            
            if not export_csv_btn:
                print("❌ CSV 내보내기 버튼을 찾을 수 없음")
                return None
            
            # 버튼 클릭
            try:
                export_csv_btn.click()
            except:
                self.driver.execute_script("arguments[0].click();", export_csv_btn)
            
            time.sleep(5)
            
            # 다운로드 완료 대기
            timeout = 120
            check_interval = 2
            
            for i in range(0, timeout, check_interval):
                # 새 파일 확인
                current_csvs = glob.glob(os.path.join(self.download_dir, "*.csv"))
                new_csvs = [f for f in current_csvs if f not in existing_csvs]
                
                if new_csvs:
                    latest_file = max(new_csvs, key=os.path.getctime)
                    if os.path.getsize(latest_file) > 0:
                        print(f"✅ CSV 다운로드 완료: {os.path.basename(latest_file)}")
                        return latest_file
                
                # Downloads 폴더 확인
                downloads_csvs = glob.glob(os.path.expanduser("~/Downloads/export-projects*.csv"))
                if downloads_csvs:
                    latest_download = max(downloads_csvs, key=os.path.getctime)
                    if time.time() - os.path.getmtime(latest_download) < 600:
                        import shutil
                        local_file = os.path.basename(latest_download)
                        shutil.copy(latest_download, local_file)
                        os.remove(latest_download)
                        return local_file
                
                time.sleep(check_interval)
            
            print("❌ CSV 다운로드 시간 초과")
            return None
            
        except Exception as e:
            print(f"❌ CSV 내보내기 실패: {e}")
            return None
    
    def run_complete_automation(self, email, password, workspace_name=WORKSPACE_NAME):
        """완전 자동화 실행"""
        try:
            print("🚀 자동화 프로세스 시작")
            
            # 1. 드라이버 설정
            if not self.setup_driver():
                self.send_to_slack(None, None, "드라이버 설정 실패")
                return None
            
            # 2. 로그인
            if not self.login_to_taskworld(email, password):
                self.send_to_slack(None, None, "로그인 실패")
                return None
            
            # 3. 워크스페이스 이동
            if not self.navigate_to_workspace(workspace_name):
                self.send_to_slack(None, None, f"워크스페이스 '{workspace_name}' 접속 실패")
                return None
            
            # 4. CSV 내보내기
            csv_file = self.export_csv()
            if not csv_file:
                self.send_to_slack(None, None, "CSV 다운로드 실패")
                return None
            
            # 5. CSV 처리
            result_df, removed_count, processed_file, validation_issues = self.process_csv(csv_file)
            if result_df is None:
                self.send_to_slack(None, None, processed_file)
                return None
            
            # 6. 슬랙 전송
            if self.slack_client:
                stats_info = f"총 {len(result_df) + (removed_count or 0)}행 → 필터링 {removed_count or 0}행 → 최종 {len(result_df)}행"
                self.send_to_slack(processed_file, stats_info, None, validation_issues)
            
            # 7. 파일 정리
            if os.path.exists(csv_file):
                os.remove(csv_file)
            
            print(f"🎉 자동화 완료! 파일: {processed_file}")
            return processed_file
                
        except Exception as e:
            error_msg = f"자동화 실패: {str(e)}"
            print(f"❌ {error_msg}")
            self.send_to_slack(None, None, error_msg)
            return None
            
        finally:
            if self.driver:
                self.driver.quit()

# 실행 부분
if __name__ == "__main__":
    print(f"🔍 설정: {WORKSPACE_NAME}, {OUTPUT_FILENAME}, {MIN_REQUIRED_HOURS}시간")
    
    email = os.getenv("TASKWORLD_EMAIL")
    password = os.getenv("TASKWORLD_PASSWORD")
    
    if not email or not password:
        print("❌ 환경변수 필요: TASKWORLD_EMAIL, TASKWORLD_PASSWORD")
        exit(1)
    
    downloader = TaskworldSeleniumDownloader(headless=DEFAULT_HEADLESS)
    result = downloader.run_complete_automation(email, password, WORKSPACE_NAME)
    
    if result:
        print("✅ 모든 프로세스 완료!")
    else:
        print("❌ 프로세스 실패")
        exit(1)
