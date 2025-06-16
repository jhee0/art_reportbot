#!/usr/bin/env python3
"""
태스크월드 → 구글 스프레드시트 자동화
매일 7시에 태스크월드 데이터를 가져와서 구글 스프레드시트에 업데이트
"""

import os
import json
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
import gspread
from google.oauth2.service_account import Credentials

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TaskworldAPI:
    """태스크월드 API 클라이언트"""
    
    def __init__(self, email: str, password: str, region: str = "asia"):
        self.email = email
        self.password = password
        self.region = region
        self.api_base = f"https://{region}-api.taskworld.com"
        self.access_token = None
        self.default_space_id = None
        
    def authenticate(self) -> bool:
        """태스크월드 API 인증"""
        try:
            auth_url = f"{self.api_base}/v1/auth"
            payload = {
                "email": self.email,
                "password": self.password
            }
            
            logger.info("태스크월드 인증 시도...")
            response = requests.post(
                auth_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    self.access_token = data.get("access_token")
                    self.default_space_id = data.get("default_space_id")
                    logger.info("✅ 태스크월드 인증 성공")
                    return True
                else:
                    logger.error(f"❌ 인증 실패: {data.get('error_description', '알 수 없는 오류')}")
                    return False
            else:
                logger.error(f"❌ HTTP 에러: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 네트워크 오류: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ 인증 중 오류: {str(e)}")
            return False
    
    def get_workspaces(self) -> List[Dict]:
        """워크스페이스 목록 조회"""
        if not self.access_token:
            logger.error("인증이 필요합니다")
            return []
            
        try:
            url = f"{self.api_base}/v1/space.get-all"
            payload = {"access_token": self.access_token}
            
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    workspaces = data.get("spaces", [])
                    logger.info(f"워크스페이스 {len(workspaces)}개 발견")
                    return workspaces
            
            logger.warning("워크스페이스 조회 실패")
            return []
            
        except Exception as e:
            logger.error(f"워크스페이스 조회 중 오류: {str(e)}")
            return []
    
    def find_workspace_by_name(self, workspace_name: str) -> Optional[str]:
        """워크스페이스 이름으로 ID 찾기"""
        workspaces = self.get_workspaces()
        for workspace in workspaces:
            if workspace_name.lower() in workspace.get("title", "").lower():
                space_id = workspace.get("space_id")
                logger.info(f"워크스페이스 발견: '{workspace.get('title')}' (ID: {space_id})")
                return space_id
        
        logger.error(f"워크스페이스를 찾을 수 없습니다: '{workspace_name}'")
        logger.info("사용 가능한 워크스페이스:")
        for ws in workspaces:
            logger.info(f"  - {ws.get('title', 'Unknown')}")
        return None
    
    def get_projects(self, space_id: str) -> List[Dict]:
        """프로젝트 목록 조회"""
        if not self.access_token:
            logger.error("인증이 필요합니다")
            return []
            
        try:
            url = f"{self.api_base}/v1/project.get-all"
            payload = {
                "access_token": self.access_token,
                "space_id": space_id
            }
            
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    projects = data.get("projects", [])
                    logger.info(f"프로젝트 {len(projects)}개 발견")
                    return projects
            
            logger.warning("프로젝트 조회 실패")
            return []
            
        except Exception as e:
            logger.error(f"프로젝트 조회 중 오류: {str(e)}")
            return []
    
    def get_project_tasks(self, space_id: str, project_id: str) -> List[Dict]:
        """프로젝트의 태스크 목록 조회"""
        if not self.access_token:
            logger.error("인증이 필요합니다")
            return []
            
        try:
            url = f"{self.api_base}/v1/task.get-all"
            payload = {
                "access_token": self.access_token,
                "space_id": space_id,
                "project_id": project_id
            }
            
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    return data.get("tasks", [])
            
            return []
            
        except Exception as e:
            logger.error(f"태스크 조회 중 오류: {str(e)}")
            return []

class GoogleSheetsUpdater:
    """구글 스프레드시트 업데이트 클래스"""
    
    def __init__(self, credentials_json: str, spreadsheet_id: str):
        self.credentials_json = credentials_json
        self.spreadsheet_id = spreadsheet_id
        self.client = None
        
    def authenticate(self) -> bool:
        """구글 스프레드시트 인증"""
        try:
            # JSON 문자열을 파싱
            creds_dict = json.loads(self.credentials_json)
            
            # 서비스 계정 인증
            creds = Credentials.from_service_account_info(
                creds_dict,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            
            self.client = gspread.authorize(creds)
            logger.info("✅ 구글 스프레드시트 인증 성공")
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON 파싱 오류: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ 구글 스프레드시트 인증 실패: {str(e)}")
            return False
    
    def update_sheet_with_data(self, data: List[List[Any]], sheet_name: str = "TaskworldData") -> bool:
        """데이터로 시트 업데이트"""
        try:
            # 스프레드시트 열기
            spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            logger.info(f"스프레드시트 열기 성공: {spreadsheet.title}")
            
            # 워크시트 가져오기 또는 생성
            try:
                worksheet = spreadsheet.worksheet(sheet_name)
                logger.info(f"기존 시트 사용: {sheet_name}")
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
                logger.info(f"새 시트 생성: {sheet_name}")
            
            # 기존 데이터 모두 삭제
            worksheet.clear()
            
            # 새 데이터 업데이트
            if data and len(data) > 0:
                # 셀 범위 계산 (A1부터 필요한 만큼)
                end_col = chr(ord('A') + len(data[0]) - 1)  # 열 개수에 따라 계산
                end_row = len(data)
                range_name = f"A1:{end_col}{end_row}"
                
                worksheet.update(range_name, data)
                logger.info(f"✅ 스프레드시트 업데이트 완료: {len(data)}행 {len(data[0])}열")
                return True
            else:
                logger.warning("업데이트할 데이터가 없습니다")
                return False
                
        except Exception as e:
            logger.error(f"❌ 스프레드시트 업데이트 실패: {str(e)}")
            return False

def format_taskworld_data(projects: List[Dict], all_tasks: Dict[str, List[Dict]]) -> List[List[Any]]:
    """태스크월드 데이터를 스프레드시트 형태로 변환"""
    
    # 헤더 행
    headers = [
        "업데이트 시간",
        "프로젝트 ID",
        "프로젝트 이름",
        "태스크 ID",
        "태스크 이름",
        "상태",
        "담당자",
        "생성일",
        "수정일",
        "마감일",
        "우선순위",
        "설명"
    ]
    
    data = [headers]
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for project in projects:
        project_id = project.get("project_id", "")
        project_name = project.get("title", "")
        
        project_tasks = all_tasks.get(project_id, [])
        
        if not project_tasks:
            # 태스크가 없는 프로젝트
            row = [
                current_time,
                project_id,
                project_name,
                "",
                "",
                "",
                "",
                project.get("created", ""),
                project.get("updated", ""),
                "",
                "",
                project.get("description", "")
            ]
            data.append(row)
        else:
            # 태스크가 있는 프로젝트
            for task in project_tasks:
                row = [
                    current_time,
                    project_id,
                    project_name,
                    task.get("task_id", ""),
                    task.get("title", ""),
                    task.get("status", ""),
                    task.get("assignee_name", ""),
                    task.get("created", ""),
                    task.get("updated", ""),
                    task.get("due_date", ""),
                    task.get("priority", ""),
                    task.get("description", "")
                ]
                data.append(row)
    
    return data

def main():
    """메인 실행 함수"""
    logger.info("🚀 태스크월드 자동화 시작")
    
    try:
        # 환경 변수에서 설정 읽기
        taskworld_email = os.environ.get('TASKWORLD_EMAIL')
        taskworld_password = os.environ.get('TASKWORLD_PASSWORD')
        workspace_name = os.environ.get('TASKWORLD_WORKSPACE_NAME', '아트실 일정 - 2025 6주기')
        google_spreadsheet_id = os.environ.get('GOOGLE_SPREADSHEET_ID')
        google_credentials_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        
        # 필수 환경 변수 확인
        missing_vars = []
        if not taskworld_email:
            missing_vars.append('TASKWORLD_EMAIL')
        if not taskworld_password:
            missing_vars.append('TASKWORLD_PASSWORD')
        if not google_spreadsheet_id:
            missing_vars.append('GOOGLE_SPREADSHEET_ID')
        if not google_credentials_json:
            missing_vars.append('GOOGLE_CREDENTIALS_JSON')
            
        if missing_vars:
            raise Exception(f"필수 환경 변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
        
        logger.info("환경 변수 확인 완료")
        
        # 1. 태스크월드 API 인증
        tw_api = TaskworldAPI(taskworld_email, taskworld_password)
        if not tw_api.authenticate():
            raise Exception("태스크월드 인증 실패")
        
        # 2. 워크스페이스 찾기
        workspace_id = tw_api.find_workspace_by_name(workspace_name)
        if not workspace_id:
            raise Exception(f"워크스페이스를 찾을 수 없습니다: {workspace_name}")
        
        # 3. 프로젝트 데이터 수집
        projects = tw_api.get_projects(workspace_id)
        if not projects:
            logger.warning("프로젝트가 없습니다")
            projects = []
        
        # 4. 각 프로젝트의 태스크 데이터 수집
        all_tasks = {}
        for project in projects:
            project_id = project.get("project_id")
            project_title = project.get("title", "Unknown")
            
            tasks = tw_api.get_project_tasks(workspace_id, project_id)
            all_tasks[project_id] = tasks
            logger.info(f"프로젝트 '{project_title}': 태스크 {len(tasks)}개")
        
        # 5. 데이터 포맷팅
        formatted_data = format_taskworld_data(projects, all_tasks)
        logger.info(f"데이터 포맷팅 완료: {len(formatted_data)}행")
        
        # 6. 구글 스프레드시트 업데이트
        sheets_updater = GoogleSheetsUpdater(google_credentials_json, google_spreadsheet_id)
        if not sheets_updater.authenticate():
            raise Exception("구글 스프레드시트 인증 실패")
        
        if sheets_updater.update_sheet_with_data(formatted_data):
            logger.info("🎉 자동화 완료! 구글 스프레드시트가 업데이트되었습니다.")
            print(f"✅ 성공: {len(formatted_data)-1}개 항목이 업데이트되었습니다")
        else:
            raise Exception("스프레드시트 업데이트 실패")
            
    except Exception as e:
        logger.error(f"❌ 자동화 실패: {str(e)}")
        print(f"❌ 실패: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
