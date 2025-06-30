# selenium_taskworld_downloader.py - 완전 자동화 스크립트
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
# 📅 월별 설정 변수 (매월 수정 필요)
# ==========================================
WORKSPACE_NAME = "아트실 일정 - 2025 6주기"  # 🔄 한달마다 수정하세요!
OUTPUT_FILENAME = "25_6.csv"  # 🔄 한달마다 수정하세요! (예: 25_7.csv, 25_8.csv)

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

    def validate_csv_data(self, df, min_hours=160):
        """
        CSV 데이터 검증 - A열(Tasklist) 기준으로 D열(Time Spent) 합계 확인
        """
        validation_issues = []
        
        try:
            print("🔍 CSV 데이터 검증 시작...")
            
            if len(df.columns) < 4:
                validation_issues.append("❌ 열 수가 부족합니다. 최소 4개 열이 필요합니다.")
                return validation_issues
            
            # 열 이름 설정 (헤더가 없으므로 인덱스 사용)
            df.columns = ['Tasklist', 'Task', 'Tags', 'Time_Spent']
            
            # Time_Spent 열을 숫자로 변환
            df['Time_Spent_Numeric'] = pd.to_numeric(df['Time_Spent'], errors='coerce').fillna(0)
            
            # A열(Tasklist) 기준으로 그룹화하여 D열(Time_Spent) 합계 계산
            group_totals = df.groupby('Tasklist')['Time_Spent_Numeric'].sum()
            
            print(f"📊 검증 기준: 최소 {min_hours}시간")
            print("📋 개인별 시간 합계:")
            
            # 각 그룹별 검증
            for tasklist_name, total_hours in group_totals.items():
                print(f"  - {tasklist_name}: {total_hours}시간")
                
                if total_hours < min_hours:
                    issue_msg = f"{tasklist_name}님 합산 오류 (현재: {total_hours}시간, 기준: {min_hours}시간)"
                    validation_issues.append(issue_msg)
                    print(f"    ⚠️ {issue_msg}")
                else:
                    print(f"    ✅ 기준 충족")
            
            if not validation_issues:
                print("✅ 모든 검증 통과!")
            else:
                print(f"❌ {len(validation_issues)}개의 검증 이슈 발견")
                
            return validation_issues
        
        except Exception as e:
            error_msg = f"검증 중 오류 발생: {str(e)}"
            print(f"❌ {error_msg}")
            return [error_msg]


    
    def process_csv(self, input_file, columns=['Tasklist', 'Task', 'Tags', 'Time Spent']):
        """
        CSV 파일 처리 (기존 CSV_4export.py 로직)
        특정 열만 추출하고 Tasklist열의 특정 값들을 가진 행을 제거
        """
        try:
            print("📊 CSV 파일 처리 시작...")
            
            # CSV 파일 읽기
            df = pd.read_csv(input_file)
            original_count = len(df)
            
            print(f"📊 원본 데이터: {original_count}행")
            print(f"📋 발견된 열 이름들: {list(df.columns)}")
            
            # Tasklist열(B열)의 특정 값들을 가진 행 제거
            exclude_values = ["주요일정", "아트실", "UI팀", "리소스팀", "디자인팀", "TA팀"]
            
            # Tasklist열이 존재하는지 확인
            removed_count = 0
            if 'Tasklist' in df.columns:
                df_filtered = df[~df['Tasklist'].isin(exclude_values)]
                removed_count = original_count - len(df_filtered)
                print(f"🚫 Tasklist열 필터링: {removed_count}행 제거됨")
            else:
                print("⚠️ Tasklist열이 존재하지 않아 필터링을 건너뜁니다.")
                df_filtered = df
            
            # 지정된 열 확인
            missing_columns = [col for col in columns if col not in df_filtered.columns]
            if missing_columns:
                error_msg = f"다음 열들을 찾을 수 없습니다: {missing_columns}"
                print(f"❌ {error_msg}")
                return None, None, error_msg
            
            # 지정된 열만 선택 (B, C, K, N 순서로)
            selected_df = df_filtered[columns]

            # ⭐ 검증 단계 추가 ⭐
            validation_issues = self.validate_csv_data(selected_df, min_hours=160)
            
            # 새로운 CSV 파일명 생성 (설정 변수 사용)
            output_file = OUTPUT_FILENAME
            
            # 기존 파일이 있으면 삭제 (덮어쓰기)
            if os.path.exists(output_file):
                os.remove(output_file)
                print(f"🗑️ 기존 파일 삭제: {output_file}")
            
            # 새로운 CSV 파일로 저장 (헤더 제외)
            selected_df.to_csv(output_file, index=False, header=False, encoding='utf-8-sig')
            
            print(f"✅ CSV 처리 완료: {len(selected_df)}행 저장 → {output_file}")
            
            # ⭐ 반환값 수정 (validation_issues 추가) ⭐
            return selected_df, removed_count, output_file, validation_issues
            
        except Exception as e:
            error_msg = f"CSV 처리 중 오류: {str(e)}"
            print(f"❌ {error_msg}")
            return None, None, error_msg, []  # ⭐ 빈 리스트 추가 ⭐


    def send_to_slack(self, csv_file_path, stats=None, error_message=None, validation_issues=None):
        """
        슬랙에 리포트 전송 (파일 업로드 + 메시지) - 파일명 표시 및 쓰레드 오류 지원
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
                    message_text += f"\n\n```"
                    message_text += f"\n[검증 오류]"
                    for issue in validation_issues:
                        message_text += f"\n- {issue}"
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

            # 5. CSV 처리 + 검증
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
            
            # 6. 슬랙 전송 (검증 결과 포함)
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
    
    # 기존 메서드들도 유지 (호환성을 위해)
    def download_taskworld_csv(self, email, password, workspace_name=WORKSPACE_NAME):
        """기존 호환성을 위한 메서드 (내부적으로 완전 자동화 실행)"""
        return self.run_complete_automation(email, password, workspace_name)

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

    print("🔍 환경변수 확인:")
    print(f"📧 TASKWORLD_EMAIL: {'설정됨' if os.getenv('TASKWORLD_EMAIL') else '❌ 없음'}")
    print(f"🔒 TASKWORLD_PASSWORD: {'설정됨' if os.getenv('TASKWORLD_PASSWORD') else '❌ 없음'}")
    print(f"🤖 SLACK_BOT_TOKEN: {'설정됨' if os.getenv('SLACK_BOT_TOKEN') else '❌ 없음'}")
    print(f"💬 SLACK_CHANNEL: {os.getenv('SLACK_CHANNEL', '❌ 없음')}")
    
    print("🔍 현재 파일 시스템 상태:")
    debug_file_system()
    print("=" * 60)
    
    # 환경변수에서 로그인 정보 읽기
    email = os.getenv("TASKWORLD_EMAIL")
    password = os.getenv("TASKWORLD_PASSWORD")
    workspace = os.getenv("TASKWORLD_WORKSPACE", WORKSPACE_NAME)  # 설정 변수 사용
    
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
    
    # 완전 자동화 실행
    downloader = TaskworldSeleniumDownloader(headless=DEFAULT_HEADLESS)
    result_file = downloader.run_complete_automation(email, password, workspace)
    
    if result_file:
        print(f"\n🎉 완전 자동화 성공!")
        print(f"📁 최종 파일: {result_file}")
        
        # 최종 상태 확인
        print("\n🔍 완료 후 파일 시스템 상태:")
        debug_file_system()
        
        print("\n✅ 모든 프로세스 완료!")
        print("📊 다운로드 → 처리 → 슬랙 전송까지 모두 자동화됨")
    else:
        print("\n❌ 완전 자동화 실패")
        print("\n🔍 실패 후 파일 시스템 상태:")
        debug_file_system()
        exit(1)
