@echo off
title Ultimate Download Manager Launcher
cd /d "%~dp0"

:: 1. Ưu tiên chạy tệp cài đặt độc lập nếu có
if exist "dist\Ultimate_Download_Manager.exe" (
    echo Đang khởi chạy bản đóng gói độc lập...
    start "" "dist\Ultimate_Download_Manager.exe"
    exit
)

:: 2. Nếu không có bản exe, tự động kích hoạt môi trường ảo và chạy bằng Python
if exist ".venv\Scripts\python.exe" (
    echo Không tìm thấy bản đóng gói. Đang khởi chạy ứng dụng bằng Python trong môi trường ảo...
    set PYTHONIOENCODING=utf-8
    start "" ".venv\Scripts\python.exe" run.py
    exit
)

:: 3. Lỗi nếu không tìm thấy tệp nào
echo [LỖI] Không tìm thấy tệp dist\Ultimate_Download_Manager.exe hoặc môi trường ảo .venv!
echo Vui lòng kiểm tra lại thư mục hoặc chạy setup_local.ps1 trước.
echo.
pause
