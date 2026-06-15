import PyInstaller.__main__
import os
import customtkinter

# Lấy đường dẫn thư mục cài đặt của customtkinter
customtkinter_path = os.path.dirname(customtkinter.__file__)

# Cấu hình các đối số cho PyInstaller
args = [
    'app.py',
    '--noconfirm',
    '--onefile',                     # Tạo thành 1 file .exe duy nhất
    '--windowed',                    # Chạy ẩn cửa sổ console (GUI mode)
    f'--add-data={customtkinter_path}{os.pathsep}customtkinter',  # Gói thư viện giao diện
    '--add-data=node.exe;.',         # Gói node.exe (dùng cho yt-dlp giải mã YouTube)
    '--name=Ultimate_Download_Manager' # Tên file exe đầu ra
]

print("🚀 Bắt đầu đóng gói ứng dụng bằng PyInstaller...")
print(f"CustomTkinter path: {customtkinter_path}")
print(f"Arguments: {args}")

# Khởi chạy PyInstaller
PyInstaller.__main__.run(args)

print("🎉 Đóng gói hoàn tất! File cài đặt nằm ở thư mục 'dist/Ultimate_Download_Manager.exe'")
