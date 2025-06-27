import pandas as pd
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ArtRoomReportBot:
    def __init__(self, bot_token, channel_name="#아트실"):
        """
        아트실 리포트 슬랙 봇 초기화
        
        Args:
            bot_token (str): 슬랙 봇 토큰 (xoxb-...)
            channel_name (str): 리포트를 전송할 채널명
        """
        self.client = WebClient(token=bot_token)
        self.channel = channel_name
        self.bot_name = "아트실 리포트봇"
        
        # 한국 시간대 설정
        self.korea_tz = timezone(timedelta(hours=9))
        
        # 봇 연결 테스트
        try:
            response = self.client.auth_test()
            logger.info(f"✅ 슬랙 봇 연결 성공: {response['user']}")
        except SlackApiError as e:
            logger.error(f"❌ 슬랙 봇 연결 실패: {e.response['error']}")
            raise
    
    def extract_and_filter_columns(self, input_file, output_file, columns=['Tasklist', 'Task', 'Tags', 'Time Spent']):
        """
        기존 CSV_4export.py 로직을 그대로 활용
        특정 열만 추출하고 Tasklist열의 특정 값들을 가진 행을 제거
        """
        try:
            # CSV 파일 읽기
            df = pd.read_csv(input_file)
            original_count = len(df)
            
            logger.info(f"📊 원본 데이터: {original_count}행")
            logger.info(f"📋 발견된 열 이름들: {list(df.columns)}")
            
            # Tasklist열(B열)의 특정 값들을 가진 행 제거
            exclude_values = ["주요일정", "아트실", "UI팀", "리소스팀", "디자인팀", "TA팀"]
            
            # Tasklist열이 존재하는지 확인
            removed_count = 0
            if 'Tasklist' in df.columns:
                df_filtered = df[~df['Tasklist'].isin(exclude_values)]
                removed_count = original_count - len(df_filtered)
                logger.info(f"🚫 Tasklist열 필터링: {removed_count}행 제거됨")
            else:
                logger.warning("⚠️ Tasklist열이 존재하지 않아 필터링을 건너뜁니다.")
                df_filtered = df
            
            # 지정된 열 확인
            missing_columns = [col for col in columns if col not in df_filtered.columns]
            if missing_columns:
                error_msg = f"다음 열들을 찾을 수 없습니다: {missing_columns}"
                logger.error(f"❌ {error_msg}")
                return None, None, error_msg
            
            # 지정된 열만 선택 (B, C, K, N 순서로)
            selected_df = df_filtered[columns]
            
            # 새로운 CSV 파일로 저장 (헤더 제외)
            selected_df.to_csv(output_file, index=False, header=False, encoding='utf-8-sig')
            
            logger.info(f"✅ CSV 처리 완료: {len(selected_df)}행 저장")
            
            return selected_df, removed_count, None
            
        except Exception as e:
            error_msg = f"CSV 처리 중 오류: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return None, None, error_msg
    
    def send_report_to_slack(self, csv_file_path, stats=None, error_message=None):
        """
        슬랙에 리포트 전송 (파일 업로드 + 메시지)
        """
        try:
            # 한국시간 사용
            now = datetime.now(self.korea_tz)
            today = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M")
            
            if error_message:
                # 에러 발생 시
                self._send_error_notification(error_message, today, time_str)
                return False
            
            # 성공 시 리포트 전송
            return self._send_success_report(csv_file_path, stats, today, time_str)
            
        except Exception as e:
            logger.error(f"❌ 슬랙 전송 중 예상치 못한 오류: {e}")
            return False
    
    def _send_success_report(self, csv_file_path, stats, today, time_str):
        """
        성공적인 리포트 전송
        """
        try:
            # 메인 메시지 구성
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"📊 아트실 일일 리포트 ({today})"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*🗓️ 날짜:*\n{today}"
                        },
                        {
                            "type": "mrkdwn", 
                            "text": f"*⏰ 생성 시간:*\n{time_str}"
                        }
                    ]
                }
            ]
            
            # 통계 정보 추가
            if stats:
                stats_text = (
                    f"*📈 처리 결과*\n"
                    f"• 총 태스크: {stats.get('total', 'N/A')}개\n"
                    f"• 필터링됨: {stats.get('filtered', 'N/A')}개\n" 
                    f"• 최종 결과: {stats.get('final', 'N/A')}개"
                )
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": stats_text
                    }
                })
            
            # 구분선 추가
            blocks.append({"type": "divider"})
            
            # 파일 정보
            if csv_file_path and os.path.exists(csv_file_path):
                file_size = os.path.getsize(csv_file_path) / 1024  # KB
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📎 *파일:* `{os.path.basename(csv_file_path)}` ({file_size:.1f}KB)\n💾 필터링된 데이터가 CSV 파일로 첨부되었습니다."
                    }
                })
            
            # 메시지 전송
            message_response = self.client.chat_postMessage(
                channel=self.channel,
                text=f"📊 아트실 일일 리포트 ({today})",
                blocks=blocks,
                username=self.bot_name,
                icon_emoji=":chart_with_upwards_trend:"
            )
            
            # 파일 업로드 (같은 쓰레드에)
            if csv_file_path and os.path.exists(csv_file_path):
                file_response = self.client.files_upload_v2(
                    channel=self.channel,
                    file=csv_file_path,
                    filename=os.path.basename(csv_file_path),
                    title=f"아트실 일일 리포트 - {today}",
                    thread_ts=message_response['ts']  # 쓰레드로 연결
                )
                logger.info(f"📎 파일 업로드 성공: {file_response['file']['name']}")
            
            logger.info("✅ 슬랙 리포트 전송 완료!")
            return True
            
        except SlackApiError as e:
            logger.error(f"❌ 슬랙 API 오류: {e.response['error']}")
            return False
    
    def _send_error_notification(self, error_message, today, time_str):
        """
        에러 발생 시 알림 전송
        """
        try:
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "❌ 리포트 생성 실패"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*🗓️ 날짜:*\n{today}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*⏰ 실패 시간:*\n{time_str}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🚨 오류 내용:*\n```{error_message}```"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "🔄 *다음 시도:* 30분 후 자동 재시도\n👨‍💻 *지속 문제 시:* 개발팀에 문의"
                    }
                }
            ]
            
            self.client.chat_postMessage(
                channel=self.channel,
                text="❌ 아트실 리포트 생성 실패",
                blocks=blocks,
                username=self.bot_name,
                icon_emoji=":warning:"
            )
            
            logger.info("📨 에러 알림 전송 완료")
            
        except SlackApiError as e:
            logger.error(f"❌ 에러 알림 전송 실패: {e.response['error']}")
    
    def download_taskworld_csv(self):
        """
        TODO: 태스크월드 API를 통한 CSV 다운로드
        현재는 수동 다운로드된 파일 사용
        """
        # 향후 태스크월드 GraphQL API 연동 예정
        logger.info("📥 태스크월드 API 연동 예정")
        pass
    
    def run_daily_report(self, input_csv_path=None):
        """
        일일 리포트 자동 생성 및 전송
        """
        logger.info("🚀 아트실 일일 리포트 생성 시작...")
        
        try:
            # 입력 파일 확인
            if not input_csv_path or not os.path.exists(input_csv_path):
                error_msg = "입력 CSV 파일을 찾을 수 없습니다."
                logger.error(f"❌ {error_msg}")
                self.send_report_to_slack(None, None, error_msg)
                return False
            
            # 출력 파일명 생성 (기존 방식과 동일)
            today = datetime.now()
            output_filename = f"{today.strftime('%y_%m_%d')}.csv"
            
            # CSV 처리
            logger.info("📊 CSV 데이터 처리 중...")
            result_df, removed_count, error_msg = self.extract_and_filter_columns(
                input_csv_path, 
                output_filename
            )
            
            if error_msg:
                self.send_report_to_slack(None, None, error_msg)
                return False
            
            # 통계 정보 생성
            stats = {
                'total': len(result_df) + (removed_count or 0),
                'filtered': removed_count or 0,
                'final': len(result_df)
            }
            
            # 슬랙으로 전송
            logger.info("📤 슬랙으로 전송 중...")
            success = self.send_report_to_slack(output_filename, stats)
            
            if success:
                logger.info("✅ 일일 리포트 생성 및 전송 완료!")
                return True
            else:
                logger.error("❌ 슬랙 전송 실패")
                return False
                
        except Exception as e:
            error_msg = f"예상치 못한 오류: {str(e)}"
            logger.error(f"❌ {error_msg}")
            self.send_report_to_slack(None, None, error_msg)
            return False

# 사용 예제
if __name__ == "__main__":
    # 환경 변수에서 토큰 읽기 (보안)
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    CHANNEL_NAME = os.getenv("SLACK_CHANNEL", "#아트실")
    
    if not SLACK_BOT_TOKEN:
        print("❌ SLACK_BOT_TOKEN 환경 변수가 설정되지 않았습니다.")
        exit(1)
    
    # 봇 인스턴스 생성
    bot = ArtRoomReportBot(SLACK_BOT_TOKEN, CHANNEL_NAME)
    
    # 수동 실행 예제
    input_file = input("입력 CSV 파일 경로: ").strip().strip('"').strip("'")
    bot.run_daily_report(input_file)
    
    # 자동화 시에는 이렇게:
    # bot.run_daily_report("downloaded_taskworld_data.csv")
