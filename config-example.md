# 🔧 설정 예시 가이드

GitHub Secrets에 입력해야 하는 값들의 예시입니다.

## 📋 GitHub Secrets 설정 목록

### 1. TASKWORLD_EMAIL
```
your-email@company.com
```
- 태스크월드에 로그인할 때 사용하는 이메일 주소
- 예시: `john.doe@company.com`

### 2. TASKWORLD_PASSWORD  
```
your-password-here
```
- 태스크월드 로그인 비밀번호
- 예시: `MySecurePassword123!`

### 3. TASKWORLD_WORKSPACE_NAME
```
아트실 일정 - 2025 6주기
```
- 동기화할 워크스페이스의 정확한 이름
- 태스크월드에서 보이는 이름 그대로 입력
- 예시: `마케팅팀 프로젝트`, `개발 스프린트 2025`

### 4. PERSONAL_ACCESS_TOKEN
```
ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
- GitHub Personal Access Token
- GitHub 설정에서 생성한 토큰
- 예시: `ghp_1234567890abcdefghijklmnopqrstuvwxyz123456`

---

## 🔍 각 값을 찾는 방법

### GitHub Token 만들기
1. **GitHub 프로필 아이콘** → **Settings**
2. **Developer settings** → **Personal access tokens** → **Tokens (classic)**
3. **"Generate new token (classic)"** 클릭
4. **Note**: `taskworld-automation`
5. **Select scopes**: ✅ **repo** (저장소 권한)
6. **"Generate token"** 클릭 → **토큰 복사**

### Taskworld Workspace Name 찾기
1. **태스크월드** 로그인
2. **좌측 메뉴**에서 워크스페이스 이름 확인
3. **정확한 이름** 복사 (대소문자, 공백, 특수문자 포함)

---

## ✅ 설정 체크리스트

### 필수 단계
- [ ] GitHub 계정 생성/로그인
- [ ] 프로젝트 Fork 완료
- [ ] 4개 Secrets 모두 입력 완료
- [ ] GitHub Personal Access Token 생성
- [ ] Token에 repo 권한 부여
- [ ] `PERSONAL_ACCESS_TOKEN` Secret 설정 완료
- [ ] 테스트 실행 성공

### 선택 단계
- [ ] 실행 시간 커스터마이징
- [ ] 알림 설정 추가
- [ ] 여러 워크스페이스 설정

---

## 🚨 주의사항

### 보안
- **절대 개인정보를 코드나 공개 장소에 노출하지 마세요**
- **GitHub Secrets에만 저장하세요**
- **정기적으로 비밀번호와 토큰 변경하세요**

### 권한
- **Personal Access Token에는 repo 권한만 부여하세요**
- **불필요한 권한은 제거하세요**

### 테스트
- **모든 설정 후 반드시 테스트 실행하세요**
- **로그를 확인하여 정상 동작 검증하세요**

---

## 📞 도움이 필요하면

1. **README.md의 문제 해결 섹션** 확인
2. **Actions 탭의 상세 로그** 확인  
3. **프로젝트 관리자에게 연락**
   - 오류 메시지 스크린샷 첨부
   - 어떤 단계에서 문제가 발생했는지 명시

**성공적인 자동화를 위해 화이팅! 🚀**
