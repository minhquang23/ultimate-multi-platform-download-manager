import customtkinter as ctk
import threading
import datetime
import os
import settings
import history
from core import (
    process_multiple_urls, fetch_video_list,
    check_whisper_available, get_available_whisper_models, download_whisper_model
)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("HiveTech - Ultimate Multi-Platform Download Manager v3.0")
        self.geometry("900x820")
        
        # Load cấu hình
        self.app_settings = settings.load_settings()
        
        # Cấu hình Layout chính (Grid)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Tạo TabView chính
        self.tabview = ctk.CTkTabview(self, segmented_button_selected_color="#1f538d", segmented_button_selected_hover_color="#14375e")
        self.tabview.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")

        # 3 Tab của ứng dụng
        self.tab_download = self.tabview.add("🏠 Tải về")
        self.tab_settings = self.tabview.add("⚙️ Cài đặt")
        self.tab_history = self.tabview.add("📋 Lịch sử")

        # Khởi dựng các Tab giao diện
        self.build_download_tab()
        self.build_settings_tab()
        self.build_history_tab()

        # Cập nhật thông số Dashboard lịch sử ban đầu
        self.update_dashboard()

    # ================= TAB 1: TẢI VỀ =================
    def build_download_tab(self):
        self.tab_download.grid_columnconfigure(0, weight=1)
        self.tab_download.grid_rowconfigure(1, weight=0) # Ô URL co giãn
        self.tab_download.grid_rowconfigure(3, weight=1) # Danh sách video co giãn tối đa
        self.tab_download.grid_rowconfigure(5, weight=0) # Ô Logs

        # 1. Nhãn & Hộp nhập URL
        self.label_urls = ctk.CTkLabel(self.tab_download, text="Nhập các URL (YouTube, Shorts, TikTok, Facebook, Vimeo), mỗi dòng 1 URL:", font=ctk.CTkFont(weight="bold"))
        self.label_urls.grid(row=0, column=0, padx=15, pady=(15, 2), sticky="w")
        
        self.textbox_urls = ctk.CTkTextbox(self.tab_download, height=110)
        self.textbox_urls.grid(row=1, column=0, padx=15, pady=2, sticky="nsew")

        # 2. Thanh Controls (Quét Link, Tải, Dọn Dẹp)
        self.frame_controls = ctk.CTkFrame(self.tab_download)
        self.frame_controls.grid(row=2, column=0, padx=15, pady=8, sticky="ew")
        self.frame_controls.grid_columnconfigure(2, weight=1) # Khoảng trống giữa các nút

        self.btn_scan = ctk.CTkButton(
            self.frame_controls, 
            text="🔍 Quét Link", 
            command=self.scan_urls, 
            fg_color="#2b7a78", 
            hover_color="#17252a", 
            font=ctk.CTkFont(weight="bold")
        )
        self.btn_scan.grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self.btn_start = ctk.CTkButton(
            self.frame_controls, 
            text="🚀 Bắt đầu Tải", 
            command=self.start_download, 
            fg_color="#1f538d", 
            hover_color="#14375e", 
            font=ctk.CTkFont(weight="bold")
        )
        self.btn_start.grid(row=0, column=1, padx=10, pady=8, sticky="w")

        self.btn_clear = ctk.CTkButton(
            self.frame_controls, 
            text="🧹 Dọn dẹp URL", 
            command=self.clear_urls, 
            fg_color="#5a6268", 
            hover_color="#495057", 
            width=110
        )
        self.btn_clear.grid(row=0, column=3, padx=10, pady=8, sticky="e")

        # 3. Danh sách check chọn video (Scrollable)
        self.scrollable_frame = ctk.CTkScrollableFrame(self.tab_download, label_text="Danh sách Video (Quét link để hiển thị)", label_font=ctk.CTkFont(weight="bold"))
        self.scrollable_frame.grid(row=3, column=0, padx=15, pady=5, sticky="nsew")
        self.video_rows = {} # Lưu map: url -> {widgets}
        self.check_all_var = ctk.StringVar(value="off")

        # 4. Logs Console
        self.label_logs = ctk.CTkLabel(self.tab_download, text="Tiến trình hệ thống (Logs):", font=ctk.CTkFont(weight="bold"))
        self.label_logs.grid(row=4, column=0, padx=15, pady=(10, 2), sticky="w")
        
        self.textbox_logs = ctk.CTkTextbox(self.tab_download, height=130, state="disabled")
        self.textbox_logs.grid(row=5, column=0, padx=15, pady=(0, 15), sticky="nsew")

    def log_message(self, message):
        """Hàm ghi log an toàn vào console."""
        self.textbox_logs.configure(state="normal")
        self.textbox_logs.insert("end", message + "\n")
        self.textbox_logs.see("end")
        self.textbox_logs.configure(state="disabled")

    def clear_urls(self):
        self.textbox_urls.delete("1.0", "end")

    def toggle_all(self):
        val = 1 if self.check_all_var.get() == "on" else 0
        for _, row in self.video_rows.items():
            if val:
                row['checkbox'].select()
            else:
                row['checkbox'].deselect()

    def scan_urls(self):
        urls_text = self.textbox_urls.get("1.0", "end").strip()
        if not urls_text:
            self.log_message("Lỗi: Vui lòng nhập ít nhất 1 URL để quét!")
            return
            
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        
        self.btn_scan.configure(state="disabled", text="Đang quét...")
        self.btn_start.configure(state="disabled")
        self.log_message("Bắt đầu quét danh sách video...")
        
        # Xóa danh sách giao diện video cũ
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.video_rows.clear()
        
        browser_val = self.app_settings.get("browser", "chrome")
        
        scan_thread = threading.Thread(target=self.run_scan_task, args=(urls, browser_val))
        scan_thread.daemon = True
        scan_thread.start()

    def run_scan_task(self, urls, browser_val):
        try:
            results = fetch_video_list(urls, browser=browser_val)
            self.after(0, self.render_video_list, results)
        except Exception as e:
            self.log_message(f"Lỗi hệ thống khi quét link: {e}")
            self.after(0, self.reset_buttons)

    def render_video_list(self, results):
        if not results:
            self.log_message("Không tìm thấy video nào hợp lệ từ danh sách URL!")
            self.reset_buttons()
            return
            
        self.log_message(f"Quét thành công! Đã tìm thấy {len(results)} video. Hãy chọn các video muốn tải.")
        self.scrollable_frame.configure(label_text=f"Danh sách Video ({len(results)} video)")
        
        # Tạo Checkbox "Chọn tất cả"
        cb_all = ctk.CTkCheckBox(
            self.scrollable_frame, 
            text="Chọn tất cả video", 
            variable=self.check_all_var, 
            onvalue="on", 
            offvalue="off", 
            command=self.toggle_all,
            font=ctk.CTkFont(weight="bold")
        )
        cb_all.pack(anchor="w", padx=10, pady=(5, 10))
        
        # Render từng hàng cho mỗi video quét được
        for idx, item in enumerate(results):
            title = item.get('title')
            url = item.get('url')
            is_main = item.get('is_main')
            platform = item.get('platform', 'generic')
            
            # Khởi tạo frame con cho hàng video
            row_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
            row_frame.pack(fill="x", expand=True, padx=5, pady=4)
            row_frame.grid_columnconfigure(0, weight=4) # Title chiếm chỗ nhiều nhất
            row_frame.grid_columnconfigure(1, weight=2) # Status label
            row_frame.grid_columnconfigure(2, weight=2) # Progress bar

            # Icon tương ứng với từng Platform
            platform_icons = {
                'youtube': '📹 [YouTube]',
                'youtube_shorts': '🩳 [Shorts]',
                'tiktok': '🎵 [TikTok]',
                'facebook': '👥 [Facebook]',
                'vimeo': '🌐 [Vimeo]',
                'generic': '🔗 [Link]'
            }
            prefix = platform_icons.get(platform, '🔗')

            # Checkbox
            var = ctk.IntVar()
            cb = ctk.CTkCheckBox(row_frame, text=f"{idx+1}. {prefix} {title}", variable=var)
            cb.grid(row=0, column=0, padx=5, pady=2, sticky="w")
            if is_main:
                cb.select()
            else:
                cb.deselect()

            # Status label
            lbl_status = ctk.CTkLabel(row_frame, text="Sẵn sàng", text_color="#aaa", font=ctk.CTkFont(size=11))
            lbl_status.grid(row=0, column=1, padx=5, pady=2, sticky="w")

            # Progress Bar
            pb = ctk.CTkProgressBar(row_frame, width=160)
            pb.grid(row=0, column=2, padx=5, pady=2, sticky="e")
            pb.set(0.0)

            # Lưu vào dictionary của app
            self.video_rows[url] = {
                'checkbox': cb,
                'status_label': lbl_status,
                'progress_bar': pb,
                'var': var,
                'title': title
            }
            
        self.reset_buttons()

    def update_video_progress(self, url, percent, downloaded_bytes, total_bytes):
        """Callback cập nhật % tải của từng video lên GUI."""
        if url in self.video_rows:
            row = self.video_rows[url]
            pb = row['progress_bar']
            lbl = row['status_label']
            
            if percent == -1.0:
                self.after(0, lambda: pb.set(0.0))
                self.after(0, lambda: lbl.configure(text="Thất bại ❌", text_color="#d62728"))
            elif percent == 100.0:
                self.after(0, lambda: pb.set(1.0))
                self.after(0, lambda: lbl.configure(text="Hoàn thành ✔️", text_color="#2ca02c"))
            else:
                self.after(0, lambda: pb.set(percent / 100.0))
                from history import format_size
                downloaded_str = format_size(downloaded_bytes)
                total_str = format_size(total_bytes)
                status_text = f"Đang tải {percent:.1f}% ({downloaded_str}/{total_str})"
                self.after(0, lambda: lbl.configure(text=status_text, text_color="#1f77b4"))

    def update_diarization_progress(self, url, percent):
        """Callback cập nhật % nhận diện người nói."""
        if url in self.video_rows:
            row = self.video_rows[url]
            pb = row['progress_bar']
            lbl = row['status_label']
            
            self.after(0, lambda: pb.set(percent / 100.0))
            status_text = f"Phân tích người nói: {percent}%"
            self.after(0, lambda: lbl.configure(text=status_text, text_color="#9467bd"))

    def update_delay_countdown(self, url, remaining_seconds):
        """Callback cập nhật thời gian đếm ngược (khoảng nghỉ tránh bot) chính xác miligiây."""
        if url in self.video_rows:
            row = self.video_rows[url]
            lbl = row['status_label']
            
            if remaining_seconds > 0:
                status_text = f"Tránh bot: {remaining_seconds:.2f} giây..."
                self.after(0, lambda: lbl.configure(text=status_text, text_color="#ff7f0e"))
            else:
                self.after(0, lambda: lbl.configure(text="Sẵn sàng", text_color="#aaa"))

    def start_download(self):
        # Lọc danh sách các video đã tích chọn
        selected_items = []
        for url, row in self.video_rows.items():
            if row['var'].get() == 1:
                selected_items.append((url, row))

        if not selected_items:
            self.log_message("Lỗi: Vui lòng quét link và tích chọn ít nhất 1 video để bắt đầu tải!")
            return

        # Disable buttons để khóa tương tác khi đang tải
        self.btn_start.configure(state="disabled", text="Đang xử lý...")
        self.btn_scan.configure(state="disabled")

        # Tạo Session Directory
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = os.path.join("downloads", f"Session_{now}")

        # Dọn dẹp logs cũ
        self.textbox_logs.configure(state="normal")
        self.textbox_logs.delete("1.0", "end")
        self.textbox_logs.configure(state="disabled")

        # Khởi động lại progress bars & labels
        for url, row in selected_items:
            row['progress_bar'].set(0.0)
            row['status_label'].configure(text="Đang chờ...", text_color="#aaa")

        urls_to_download = [item[0] for item in selected_items]

        # Khởi chạy luồng tải ngầm để tránh đơ giao diện
        download_thread = threading.Thread(target=self.run_download_task, args=(urls_to_download, session_dir))
        download_thread.daemon = True
        download_thread.start()

    def run_download_task(self, urls, session_dir):
        # Đọc cấu hình mới nhất từ Tab Cài đặt để chạy tải
        lang = self.app_settings.get("subtitle_lang", "vi")
        download_video = self.app_settings.get("download_video", True)
        browser = self.app_settings.get("browser", "chrome")
        video_quality = self.app_settings.get("video_quality", "1080p")
        delay_min = float(self.app_settings.get("delay_min", 3.0))
        delay_max = float(self.app_settings.get("delay_max", 5.0))
        transcript_mode = self.app_settings.get("transcript_mode", "prefer_subtitle")
        whisper_model = self.app_settings.get("whisper_model", "medium")
        whisper_device = self.app_settings.get("whisper_device", "auto")
        whisper_model_dir = self.app_settings.get("whisper_model_dir", "models/whisper")
        enable_speaker_diarization = self.app_settings.get("enable_speaker_diarization", False)
        gemini_api_key = self.app_settings.get("gemini_api_key", "")

        try:
            success_count, total_bytes, duration = process_multiple_urls(
                urls=urls,
                lang=lang,
                output_dir=session_dir,
                download_video=download_video,
                browser=browser,
                delay_min=delay_min,
                delay_max=delay_max,
                video_quality=video_quality,
                transcript_mode=transcript_mode,
                whisper_model=whisper_model,
                whisper_device=whisper_device,
                whisper_model_dir=whisper_model_dir,
                enable_speaker_diarization=enable_speaker_diarization,
                gemini_api_key=gemini_api_key,
                progress_callback=self.update_video_progress,
                delay_callback=self.update_delay_countdown,
                log_callback=self.log_message,
                diarization_progress_callback=self.update_diarization_progress
            )

            # Lưu vào lịch sử nếu tải thành công
            if success_count > 0:
                history.save_session(
                    session_dir=session_dir,
                    urls=urls,
                    video_count=success_count,
                    total_bytes=total_bytes,
                    duration_seconds=duration
                )
                # Reset dashboard và lịch sử cuộn
                self.after(0, self.update_dashboard)
                
        except Exception as e:
            self.log_message(f"Lỗi nghiêm trọng khi tải: {e}")
        finally:
            self.after(0, self.reset_buttons)
            
            # Cập nhật các trạng thái cuối cùng cho giao diện
            for url, row in self.video_rows.items():
                if row['var'].get() == 1:
                    txt = row['status_label'].cget("text")
                    # Nếu status còn dạng đang chờ/đang tải thì chuyển thành Hoàn thành nếu đã kết thúc phiên thành công
                    if "Đang tải" in txt or "Đang chờ" in txt or "Tránh bot" in txt:
                        self.after(0, lambda r=row: r['status_label'].configure(text="Hoàn thành ✔️", text_color="#2ca02c"))
                        self.after(0, lambda r=row: r['progress_bar'].set(1.0))

    def reset_buttons(self):
        self.btn_scan.configure(state="normal", text="🔍 Quét Link")
        self.btn_start.configure(state="normal", text="🚀 Bắt đầu Tải")

    # ================= TAB 2: CÀI ĐẶT =================
    def build_settings_tab(self):
        self.tab_settings.grid_columnconfigure(0, weight=1)
        self.tab_settings.grid_rowconfigure(0, weight=1)

        # ScrollableFrame để chứa toàn bộ settings (vì có nhiều section hơn)
        self.settings_scroll = ctk.CTkScrollableFrame(self.tab_settings)
        self.settings_scroll.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        self.settings_scroll.grid_columnconfigure(1, weight=1)

        row = 0

        # ---- Nhóm 1: Tránh quét bot ----
        ctk.CTkLabel(self.settings_scroll, text="🛡️ CHỐNG PHÁT HIỆN BOT", font=ctk.CTkFont(weight="bold", size=13)).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(15, 8), sticky="w"); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Khoảng nghỉ tối thiểu (giây):").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.entry_delay_min = ctk.CTkEntry(self.settings_scroll, width=120)
        self.entry_delay_min.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        self.entry_delay_min.insert(0, str(self.app_settings.get("delay_min", 3.0))); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Khoảng nghỉ tối đa (giây):").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.entry_delay_max = ctk.CTkEntry(self.settings_scroll, width=120)
        self.entry_delay_max.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        self.entry_delay_max.insert(0, str(self.app_settings.get("delay_max", 5.0))); row += 1

        # Divider
        ctk.CTkLabel(self.settings_scroll, text="─" * 60, text_color="#444").grid(
            row=row, column=0, columnspan=2, padx=15, pady=8, sticky="ew"); row += 1

        # ---- Nhóm 2: Download ----
        ctk.CTkLabel(self.settings_scroll, text="📥 DOWNLOAD VIDEO & SUBTITLE", font=ctk.CTkFont(weight="bold", size=13)).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(5, 8), sticky="w"); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Tải kèm file Video:").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.cb_download_video = ctk.CTkCheckBox(self.settings_scroll, text="Đồng ý tải Video")
        self.cb_download_video.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        if self.app_settings.get("download_video", True):
            self.cb_download_video.select()
        else:
            self.cb_download_video.deselect(); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Chất lượng Video tối đa:").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.menu_quality = ctk.CTkOptionMenu(self.settings_scroll, values=["4K", "1080p", "720p", "480p", "Tốt nhất"])
        self.menu_quality.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        self.menu_quality.set(self.app_settings.get("video_quality", "1080p")); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Mã ngôn ngữ phụ đề (YouTube):").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.entry_sub_lang = ctk.CTkEntry(self.settings_scroll, width=120)
        self.entry_sub_lang.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        self.entry_sub_lang.insert(0, self.app_settings.get("subtitle_lang", "vi")); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Đọc Cookies từ trình duyệt:").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.menu_browser = ctk.CTkOptionMenu(self.settings_scroll, values=["chrome", "edge", "firefox", "brave", "opera", "Không dùng"])
        self.menu_browser.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        self.menu_browser.set(self.app_settings.get("browser", "chrome")); row += 1

        # Divider
        ctk.CTkLabel(self.settings_scroll, text="─" * 60, text_color="#444").grid(
            row=row, column=0, columnspan=2, padx=15, pady=8, sticky="ew"); row += 1

        # ---- Nhóm 3: Whisper AI ----
        ctk.CTkLabel(self.settings_scroll, text="🎙️ WHISPER AI — SPEECH-TO-TEXT", font=ctk.CTkFont(weight="bold", size=13)).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(5, 4), sticky="w"); row += 1

        # Trạng thái Whisper + GPU
        whisper_ok = check_whisper_available()
        try:
            import torch
            gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
            cuda_ok = torch.cuda.is_available()
        except ImportError:
            gpu_name = None
            cuda_ok = False

        if whisper_ok:
            status_text = "✅ Whisper đã cài"
            status_color = "#2ca02c"
        else:
            status_text = "❌ Chưa cài Whisper — Chạy setup_local.ps1 để cài đặt"
            status_color = "#d62728"

        self.lbl_whisper_status = ctk.CTkLabel(
            self.settings_scroll, text=status_text, text_color=status_color, font=ctk.CTkFont(size=11)
        )
        self.lbl_whisper_status.grid(row=row, column=0, columnspan=2, padx=15, pady=2, sticky="w"); row += 1

        if cuda_ok and gpu_name:
            gpu_text = f"🖥️ GPU: {gpu_name} (CUDA ✅)"
            gpu_color = "#4fc1ff"
        else:
            gpu_text = "🖥️ GPU: Không phát hiện CUDA — Sẽ dùng CPU"
            gpu_color = "#ff7f0e"

        ctk.CTkLabel(self.settings_scroll, text=gpu_text, text_color=gpu_color, font=ctk.CTkFont(size=11)).grid(
            row=row, column=0, columnspan=2, padx=15, pady=2, sticky="w"); row += 1

        # Model Whisper
        ctk.CTkLabel(self.settings_scroll, text="Model Whisper:").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        whisper_models = ["tiny (75MB)", "base (145MB)", "small (480MB)", "medium (1.5GB)", "large-v3 (2.9GB — CPU)"]  
        self.menu_whisper_model = ctk.CTkOptionMenu(self.settings_scroll, values=whisper_models)
        self.menu_whisper_model.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        saved_model = self.app_settings.get("whisper_model", "medium")
        # Map tên ngắn sang tên hiển thị
        model_display_map = {
            "tiny": "tiny (75MB)", "base": "base (145MB)", "small": "small (480MB)",
            "medium": "medium (1.5GB)", "large": "large-v3 (2.9GB — CPU)",
            "large-v2": "large-v3 (2.9GB — CPU)", "large-v3": "large-v3 (2.9GB — CPU)"
        }
        self.menu_whisper_model.set(model_display_map.get(saved_model, "medium (1.5GB)")); row += 1

        # Thiết bị xử lý
        ctk.CTkLabel(self.settings_scroll, text="Thiết bị xử lý:").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.menu_whisper_device = ctk.CTkOptionMenu(
            self.settings_scroll,
            values=["auto (tự động)", "cuda (GPU — Nhanh)", "cpu (CPU — Ổn định)"]
        )
        self.menu_whisper_device.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        device_display_map = {
            "auto": "auto (tự động)", "cuda": "cuda (GPU — Nhanh)", "cpu": "cpu (CPU — Ổn định)"
        }
        self.menu_whisper_device.set(device_display_map.get(self.app_settings.get("whisper_device", "auto"), "auto (tự động)")); row += 1

        # Ghi chú GPU nhỏ
        ctk.CTkLabel(
            self.settings_scroll,
            text="⚠️ GTX 950 (2GB VRAM): Khuyến nghị dùng 'medium' trên CUDA hoặc 'large-v3' trên CPU",
            text_color="#888", font=ctk.CTkFont(size=10)
        ).grid(row=row, column=0, columnspan=2, padx=15, pady=(0, 6), sticky="w"); row += 1

        # Nút Tải Model
        self.lbl_model_dl_status = ctk.CTkLabel(self.settings_scroll, text="", font=ctk.CTkFont(size=11))
        self.lbl_model_dl_status.grid(row=row, column=0, columnspan=2, padx=15, pady=2, sticky="w"); row += 1

        self.btn_dl_model = ctk.CTkButton(
            self.settings_scroll,
            text="⬇️ Tải Model Whisper về máy",
            command=self.download_whisper_model_action,
            fg_color="#2b5797",
            hover_color="#1e3f7a"
        )
        self.btn_dl_model.grid(row=row, column=0, columnspan=2, padx=15, pady=4, sticky="w"); row += 1

        # Divider
        ctk.CTkLabel(self.settings_scroll, text="─" * 60, text_color="#444").grid(
            row=row, column=0, columnspan=2, padx=15, pady=8, sticky="ew"); row += 1

        # ---- Nhóm 4: Nhận diện người nói (Model C) ----
        ctk.CTkLabel(self.settings_scroll, text="👥 NHẬN DIỆN NGƯỜI NÓI (SPEAKER DIARIZATION)", font=ctk.CTkFont(weight="bold", size=13)).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(5, 4), sticky="w"); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Tính năng này dùng Mô hình C (Heuristics + Gemini LLM) để tự động gán tên người nói vào transcript.", font=ctk.CTkFont(size=11), text_color="#888").grid(
            row=row, column=0, columnspan=2, padx=15, pady=2, sticky="w"); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Bật nhận diện người nói:").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.cb_speaker_diarization = ctk.CTkCheckBox(self.settings_scroll, text="Bật Model C")
        self.cb_speaker_diarization.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        if self.app_settings.get("enable_speaker_diarization", False):
            self.cb_speaker_diarization.select()
        else:
            self.cb_speaker_diarization.deselect(); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Gemini API Key:").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.entry_gemini_key = ctk.CTkEntry(self.settings_scroll, width=280, show="*")
        self.entry_gemini_key.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        self.entry_gemini_key.insert(0, self.app_settings.get("gemini_api_key", "")); row += 1

        # Hướng dẫn lấy key
        lbl_key_guide = ctk.CTkLabel(self.settings_scroll, text="Chưa có Key? Lấy miễn phí tại: https://aistudio.google.com/app/apikey", text_color="#4fc1ff", cursor="hand2", font=ctk.CTkFont(size=10, underline=True))
        lbl_key_guide.grid(row=row, column=0, columnspan=2, padx=15, pady=(0, 6), sticky="w")
        lbl_key_guide.bind("<Button-1>", lambda e: os.startfile("https://aistudio.google.com/app/apikey")); row += 1

        # Divider
        ctk.CTkLabel(self.settings_scroll, text="─" * 60, text_color="#444").grid(
            row=row, column=0, columnspan=2, padx=15, pady=8, sticky="ew"); row += 1

        # Nhãn trạng thái lưu + Nút Lưu
        self.lbl_save_status = ctk.CTkLabel(self.settings_scroll, text="", font=ctk.CTkFont(weight="bold"))
        self.lbl_save_status.grid(row=row, column=0, columnspan=2, padx=15, pady=4); row += 1

        self.btn_save_settings = ctk.CTkButton(
            self.settings_scroll,
            text="💾 Lưu Tất Cả Cấu Hình",
            command=self.save_app_settings,
            fg_color="green",
            hover_color="darkgreen",
            font=ctk.CTkFont(weight="bold")
        )
        self.btn_save_settings.grid(row=row, column=0, columnspan=2, padx=15, pady=(4, 20))

    def download_whisper_model_action(self):
        """Tải model Whisper đã chọn về máy (chạy trên thread riêng)."""
        model_raw = self.menu_whisper_model.get().split(" ")[0]  # Lấy tên ngắn: 'tiny', 'base', ...
        if model_raw == 'large-v3':
            model_name = 'large-v3'
        else:
            model_name = model_raw
        model_dir = self.app_settings.get("whisper_model_dir", "models/whisper")

        self.btn_dl_model.configure(state="disabled", text="Đang tải...")
        self.lbl_model_dl_status.configure(text=f"⏳ Đang tải model '{model_name}'...", text_color="#4fc1ff")

        def _do_download():
            ok = download_whisper_model(model_name, model_dir, log_callback=self.log_message)
            if ok:
                self.after(0, lambda: self.lbl_model_dl_status.configure(
                    text=f"✅ Đã tải xong model '{model_name}'!", text_color="#2ca02c"))
            else:
                self.after(0, lambda: self.lbl_model_dl_status.configure(
                    text=f"❌ Lỗi tải model! Xem Logs bên dưới.", text_color="#d62728"))
            self.after(0, lambda: self.btn_dl_model.configure(
                state="normal", text="⬇️ Tải Model Whisper về máy"))

        threading.Thread(target=_do_download, daemon=True).start()

    def save_app_settings(self):
        try:
            delay_min = float(self.entry_delay_min.get().strip())
            delay_max = float(self.entry_delay_max.get().strip())

            if delay_min < 0 or delay_max < 0 or delay_min > delay_max:
                self.lbl_save_status.configure(text="Lỗi: Khoảng nghỉ không hợp lệ (Min <= Max và >= 0)!", text_color="red")
                return

            # Chuyển đổi tên model hiển thị → tên thực
            model_display = self.menu_whisper_model.get().split(" ")[0]  # e.g. "medium", "large-v3"
            # Chuyển đổi device hiển thị → tên thực
            device_display = self.menu_whisper_device.get().split(" ")[0]  # e.g. "auto", "cuda", "cpu"

            new_settings = {
                "delay_min": delay_min,
                "delay_max": delay_max,
                "video_quality": self.menu_quality.get(),
                "subtitle_lang": self.entry_sub_lang.get().strip(),
                "download_video": self.cb_download_video.get() == 1,
                "browser": self.menu_browser.get(),
                # Whisper settings
                "whisper_model": model_display,
                "whisper_device": device_display,
                "transcript_mode": self.app_settings.get("transcript_mode", "prefer_subtitle"),
                "whisper_model_dir": self.app_settings.get("whisper_model_dir", "models/whisper"),
                
                # Speaker Diarization
                "enable_speaker_diarization": self.cb_speaker_diarization.get() == 1,
                "gemini_api_key": self.entry_gemini_key.get().strip()
            }

            settings.save_settings(new_settings)
            self.app_settings = new_settings

            self.lbl_save_status.configure(text="💾 Đã lưu cài đặt thành công!", text_color="#2ca02c")
            self.after(3000, lambda: self.lbl_save_status.configure(text=""))
        except ValueError:
            self.lbl_save_status.configure(text="Lỗi: Min/Max khoảng nghỉ phải là các chữ số!", text_color="red")

    # ================= TAB 3: LỊCH SỬ TẢI =================
    def build_history_tab(self):
        self.tab_history.grid_columnconfigure(0, weight=1)
        self.tab_history.grid_rowconfigure(1, weight=1) # Danh sách chiếm hết chiều cao

        # 1. Dashboard Thống kê
        self.frame_dashboard = ctk.CTkFrame(self.tab_history, fg_color="#1e222b", height=95)
        self.frame_dashboard.grid(row=0, column=0, padx=15, pady=15, sticky="ew")
        for col in range(4):
            self.frame_dashboard.grid_columnconfigure(col, weight=1)

        # 4 Thẻ Dashboard
        self.card_sessions = self.create_stat_card(self.frame_dashboard, "📋 Tổng Phiên Tải", "0", 0)
        self.card_videos = self.create_stat_card(self.frame_dashboard, "📹 Video Đã Tải", "0", 1)
        self.card_bytes = self.create_stat_card(self.frame_dashboard, "💾 Tổng Dung Lượng", "0 B", 2)
        self.card_duration = self.create_stat_card(self.frame_dashboard, "⏱️ Tổng Thời Gian", "0s", 3)

        # 2. Scrollable History List
        self.scroll_history = ctk.CTkScrollableFrame(self.tab_history, label_text="Lịch sử tải xuống (Session)", label_font=ctk.CTkFont(weight="bold"))
        self.scroll_history.grid(row=1, column=0, padx=15, pady=5, sticky="nsew")

    def create_stat_card(self, parent, title, value, col):
        card = ctk.CTkFrame(parent, fg_color="#282c34", corner_radius=10)
        card.grid(row=0, column=col, padx=8, pady=10, sticky="nsew")
        
        lbl_title = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=10, weight="bold"), text_color="#888")
        lbl_title.pack(padx=10, pady=(10, 2))
        
        lbl_val = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=16, weight="bold"), text_color="#4fc1ff")
        lbl_val.pack(padx=10, pady=(2, 10))
        
        return lbl_val

    def update_dashboard(self):
        # 1. Lấy dữ liệu và gán lên Dashboard
        stats = history.get_stats()
        
        from history import format_size, format_duration
        self.card_sessions.configure(text=str(stats.get("sessions", 0)))
        self.card_videos.configure(text=str(stats.get("videos", 0)))
        self.card_bytes.configure(text=format_size(stats.get("bytes", 0)))
        self.card_duration.configure(text=format_duration(stats.get("duration", 0)))

        # 2. Đọc và render lại danh sách các phiên tải cũ
        for widget in self.scroll_history.winfo_children():
            widget.destroy()

        history_list = history.load_history()
        # Hiện Session mới nhất lên trên cùng
        for idx, item in enumerate(reversed(history_list)):
            session_frame = ctk.CTkFrame(self.scroll_history, fg_color="#21252b" if idx % 2 == 0 else "#282c34", corner_radius=8)
            session_frame.pack(fill="x", expand=True, padx=5, pady=4)
            session_frame.grid_columnconfigure(0, weight=1)

            date_str = item.get("date", "Chưa rõ thời gian")
            url_count = item.get("url_count", 0)
            video_count = item.get("video_count", 0)
            duration_s = item.get("duration_seconds", 0)
            total_b = item.get("total_bytes", 0)
            session_dir = item.get("session_dir", "downloads")

            # String chi tiết
            details = f"📅 {date_str}  |  📹 Đã tải: {video_count}/{url_count} video  |  💾 {format_size(total_b)}  |  ⏱️ Thời gian: {format_duration(duration_s)}"
            
            lbl_info = ctk.CTkLabel(session_frame, text=details, font=ctk.CTkFont(size=12), anchor="w")
            lbl_info.grid(row=0, column=0, padx=15, pady=(10, 2), sticky="w")

            lbl_path = ctk.CTkLabel(session_frame, text=f"📂 Thư mục: {session_dir}", font=ctk.CTkFont(size=10), text_color="#888", anchor="w")
            lbl_path.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="w")

            # Nút Mở thư mục local
            btn_open = ctk.CTkButton(
                session_frame, 
                text="📂 Mở thư mục", 
                width=110, 
                fg_color="#3a3f4b", 
                hover_color="#4b5263",
                command=lambda d=session_dir: self.open_session_folder(d)
            )
            btn_open.grid(row=0, column=1, rowspan=2, padx=15, pady=10, sticky="e")

    def open_session_folder(self, folder_path):
        """Mở thư mục trên Windows Explorer."""
        if os.path.exists(folder_path):
            try:
                os.startfile(os.path.abspath(folder_path))
            except Exception as e:
                self.log_message(f"Lỗi: Không thể mở thư mục: {e}")
        else:
            self.log_message(f"Thư mục lưu trữ không còn tồn tại trên máy tính: {folder_path}")

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    app = App()
    app.mainloop()
