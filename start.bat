@echo off
title Gemini RAG App
echo.
echo  =============================================
echo    Gemini RAG Manager
echo    Opening at: http://127.0.0.1:5000
echo  =============================================
echo.
start /min "" cmd /c "timeout /t 2 >nul && start http://127.0.0.1:5000"
python app.py
pause
