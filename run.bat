@echo off
cd /d "%~dp0"

if not exist .env (
  echo .env 파일이 없습니다. 프로젝트 폴더에 .env 를 만들고 KAKAO_REST_API_KEY 를 넣어주세요.
  pause
  exit /b 1
)
python -m pip install -r requirements.txt -q 2>nul
if errorlevel 1 (
  echo Python을 찾을 수 없습니다. Python 3.10+ 설치 후 다시 실행하세요.
  pause
  exit /b 1
)

echo 도파민 지도 서버 시작: http://127.0.0.1:8080
echo   사용자: http://127.0.0.1:8080/index.html
echo   관리자: http://127.0.0.1:8080/admin.html
python -m uvicorn server.main:app --host 127.0.0.1 --port 8080 --reload
