@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ========================================
echo  도파민 지도 — 무료 Render 배포 도우미
echo ========================================
echo.

set ZIP=dopamine-map-deploy.zip
if exist "%ZIP%" del "%ZIP%"

powershell -NoProfile -Command "Compress-Archive -Path 'index.html','admin.html','run.bat','requirements.txt','Dockerfile','render.yaml','render-starter.yaml','render-free.yaml','DEPLOY.md','.env.example','.gitignore','.dockerignore','js','server' -DestinationPath '%ZIP%' -Force"

if not exist "%ZIP%" (
  echo ZIP 생성 실패
  pause
  exit /b 1
)

echo [1/3] ZIP 준비 완료: %CD%\%ZIP%
echo.
echo [2/3] GitHub 새 저장소 페이지를 엽니다...
echo       - Repository name: dopamine-map
echo       - Public 선택
echo       - Create repository 클릭 후
echo       - "uploading an existing file" 클릭
echo       - %ZIP% 파일을 드래그해서 올리고 Commit
echo.
start https://github.com/new

timeout /t 3 >nul

echo [3/3] Render Blueprint 페이지를 엽니다...
echo       - GitHub 연결 후 dopamine-map 저장소 선택
echo       - ADMIN_PASSWORD 에 원하는 비밀번호 입력 (관리자 로그인용)
echo       - Deploy 클릭
echo.
start https://dashboard.render.com/select-repo?type=blueprint

echo.
echo 배포가 끝나면 Render에서 URL 복사 (예: https://dopamine-map.onrender.com)
echo 카카오 developers.kakao.com ^> Web ^> 사이트 도메인에 그 URL 등록
echo.
explorer /select,"%CD%\%ZIP%"
pause
