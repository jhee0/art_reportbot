#!/usr/bin/env python3
"""
태스크월드 → GitHub CSV 자동화 (카드 등록 불필요)
구글 클라우드 대신 GitHub 저장소에 CSV 파일 직접 저장
"""

import os
import json
import logging
import requests
import csv
import base64
from datetime import datetime
from typing import Dict, List, Optional, Any

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
                
        except Exception as e:
            logger.error(f"❌ 인증 중 오류: {str(e)}")
            return False
    
def find_workspace_by_name(self, workspace_name: str) -> Optional[str]:
    """워크스페이스 이름으로 ID 찾기"""
    try:
        url = f"{self.api_base}/v1/space.get-all"
        payload = {"access_token": self.access_token}
        
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                workspaces = data.get("spaces", [])
                
                # 🔍 상세 디버깅
                logger.info("🔍 === 워크스페이스 디버깅 정보 ===")
                logger.info(f"총 워크스페이스 개수: {len(workspaces)}")
                logger.info(f"찾고 있는 이름: '{workspace_name}' (길이: {len(workspace_name)})")
                
                for i, workspace in enumerate(workspaces):
                    title = workspace.get("title", "Unknown")
                    space_id = workspace.get("space_id", "Unknown")
                    logger.info(f"{i+1}. '{title}' (ID: {space_id})")
                    
                    # 다양한 매칭 방식 테스트
                    exact_match = workspace_name.lower() == title.lower()
                    contains_match = workspace_name.lower() in title.lower()
                    
                    logger.info(f"   - 정확 일치: {exact_match}")
                    logger.info(f"   - 포함 일치: {contains_match}")
                
                logger.info("=================================")
                
                # 기존 로직으로 찾기 시도
                for workspace in workspaces:
                    if workspace_name.lower() in workspace.get("title", "").lower():
                        space_id = workspace.get("space_id")
                        logger.info(f"✅ 매칭된 워크스페이스: '{workspace.get('title')}' (ID: {space_id})")
                        return space_id
        
        logger.error(f"❌ 워크스페이스를 찾을 수 없습니다: '{workspace_name}'")
        return None
        
    except Exception as e:
        logger.error(f"워크스페이스 조회 중 오류: {str(e)}")
        return None
    
    def get_projects(self, space_id: str) -> List[Dict]:
        """프로젝트 목록 조회"""
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
            
            return []
            
        except Exception as e:
            logger.error(f"프로젝트 조회 중 오류: {str(e)}")
            return []
    
    def get_project_tasks(self, space_id: str, project_id: str) -> List[Dict]:
        """프로젝트의 태스크 목록 조회"""
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

class GitHubStorage:
    """GitHub 저장소에 CSV 파일 저장"""
    
    def __init__(self, repo_owner: str, repo_name: str, github_token: str):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.github_token = github_token
        self.api_base = "https://api.github.com"
    
    def save_csv_to_github(self, csv_data: List[List[Any]], filename: str) -> bool:
        """CSV 데이터를 GitHub 저장소에 저장"""
        try:
            # CSV 내용 생성
            csv_content = ""
            for row in csv_data:
                csv_content += ",".join([f'"{str(cell)}"' for cell in row]) + "\n"
            
            # Base64 인코딩
            content_encoded = base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')
            
            # GitHub API로 파일 저장
            url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/contents/data/{filename}"
            
            # 기존 파일 있는지 확인 (업데이트를 위해 SHA 필요)
            existing_file = self._get_file_sha(f"data/{filename}")
            
            payload = {
                "message": f"📊 태스크월드 데이터 업데이트 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "content": content_encoded,
                "branch": "main"
            }
            
            if existing_file:
                payload["sha"] = existing_file  # 기존 파일 업데이트
            
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = requests.put(url, json=payload, headers=headers)
            
            if response.status_code in [200, 201]:
                download_url = f"https://github.com/{self.repo_owner}/{self.repo_name}/blob/main/data/{filename}"
                logger.info(f"✅ GitHub에 저장 완료: {download_url}")
                return True
            else:
                logger.error(f"❌ GitHub 저장 실패: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ GitHub 저장 중 오류: {str(e)}")
            return False
    
    def _get_file_sha(self, file_path: str) -> Optional[str]:
        """기존 파일의 SHA 값 조회 (업데이트용)"""
        try:
            url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json().get("sha")
            return None
            
        except Exception:
            return None

def format_taskworld_data(projects: List[Dict], all_tasks: Dict[str, List[Dict]]) -> List[List[Any]]:
    """태스크월드 데이터를 CSV 형태로 변환"""
    
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
    logger.info("🚀 태스크월드 자동화 시작 (GitHub 저장 방식)")
    
    try:
        # 환경 변수에서 설정 읽기
        taskworld_email = os.environ.get('TASKWORLD_EMAIL')
        taskworld_password = os.environ.get('TASKWORLD_PASSWORD')
        workspace_name = os.environ.get('TASKWORLD_WORKSPACE_NAME', '아트실 일정 - 2025 6주기')
        github_token = os.environ.get('PERSONAL_ACCESS_TOKEN')
        repo_owner = os.environ.get('GITHUB_REPOSITORY_OWNER')
        repo_name = os.environ.get('GITHUB_REPOSITORY_NAME', 'taskworld-automation')
        
        # 필수 환경 변수 확인
        missing_vars = []
        if not taskworld_email:
            missing_vars.append('TASKWORLD_EMAIL')
        if not taskworld_password:
            missing_vars.append('TASKWORLD_PASSWORD')
        if not github_token:
            missing_vars.append('PERSONAL_ACCESS_TOKEN')
        if not repo_owner:
            missing_vars.append('GITHUB_REPOSITORY_OWNER')
            
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
        
        # 6. GitHub에 CSV 저장
        github_storage = GitHubStorage(repo_owner, repo_name, github_token)
        filename = f"taskworld-{datetime.now().strftime('%Y-%m-%d')}.csv"
        
        if github_storage.save_csv_to_github(formatted_data, filename):
            logger.info("🎉 자동화 완료! GitHub에 CSV 파일이 저장되었습니다.")
            print(f"✅ 성공: {len(formatted_data)-1}개 항목이 저장되었습니다")
            print(f"📁 파일 위치: https://github.com/{repo_owner}/{repo_name}/blob/main/data/{filename}")
        else:
            raise Exception("GitHub 저장 실패")
            
    except Exception as e:
        logger.error(f"❌ 자동화 실패: {str(e)}")
        print(f"❌ 실패: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
