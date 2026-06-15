import sys
import multiprocessing

# 1. Đảm bảo tiến trình con hoạt động đúng khi đóng gói thành file .exe trên Windows
multiprocessing.freeze_support()

# 2. Cấu hình mã hóa Console UTF-8 để hiển thị chính xác log/ký tự tiếng Việt
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 3. Ưu tiên áp dụng bản cập nhật động yt-dlp nếu có
try:
    from src.core.downloader import apply_ytdlp_update
    apply_ytdlp_update()
except Exception:
    pass

# 4. Khởi chạy giao diện chính của ứng dụng
import customtkinter as ctk
from src.gui.app import App

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    app = App()
    app.mainloop()
