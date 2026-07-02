@echo off
cd /d "%~dp0"
set OUT=dopamine-map-deploy.zip
if exist "%OUT%" del "%OUT%"

powershell -NoProfile -Command "Compress-Archive -Path 'index.html','admin.html','run.bat','requirements.txt','Dockerfile','render.yaml','DEPLOY.md','.env.example','.gitignore','.dockerignore','js','server' -DestinationPath '%OUT%' -Force"

echo.
echo 배포용 ZIP 생성: %OUT%
echo GitHub 업로드 후 Render Blueprint로 배포하세요.
echo 자세한 방법: DEPLOY.md
pause
