import tkinter as tk
from tkinter import filedialog, Toplevel, Label
import customtkinter as ctk
import threading
import datetime
import os
import glob
import urllib.parse
from PIL import Image
import settings
import history
import hardware_scanner
from core import (
    process_multiple_urls, fetch_video_list,
    check_whisper_available, get_available_whisper_models, download_whisper_model
)

SUBTITLE_LANGUAGES = {
    "en": "Tiếng Anh (en)",
    "vi": "Tiếng Việt (vi)",
    "ko": "Tiếng Hàn (ko)",
    "ja": "Tiếng Nhật (ja)",
    "zh-Hans": "Tiếng Trung (zh)",
    "es": "Tây Ban Nha (es)",
    "fr": "Tiếng Pháp (fr)",
    "de": "Tiếng Đức (de)",
    "ru": "Tiếng Nga (ru)"
}

class ToolTip(object):
    """Tạo ghi chú (Tooltip) khi di chuột qua Widget"""
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x, y, cx, cy = self.widget.bbox("insert") or (0,0,0,0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = Label(self.tw, text=self.text, justify='left',
                      background="#ffffe0", relief='solid', borderwidth=1,
                      font=("tahoma", "9", "normal"))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("HiveTech - Ultimate Multi-Platform Download Manager v3.0")
        self.geometry("900x820")
        
        # Load cấu hình
        self.app_settings = settings.load_settings()
        self.cancel_event = threading.Event()
        
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
        
        # Cấu hình tự động quét link khi gõ hoặc dán URL
        self._debounce_timer_id = None
        self._last_scanned_urls_text = ""
        self.textbox_urls.bind("<KeyRelease>", self.on_url_textbox_changed)
        try:
            self.textbox_urls._textbox.bind("<<Modified>>", self.on_url_textbox_modified)
        except Exception:
            self.textbox_urls.bind("<<Modified>>", self.on_url_textbox_modified)

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
        # Ẩn nút Quét Link vì đã có tính năng tự động quét
        # self.btn_scan.grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self.btn_start = ctk.CTkButton(
            self.frame_controls, 
            text="🚀 Bắt đầu Xử lý", 
            command=self.start_download, 
            fg_color="#1f538d", 
            hover_color="#14375e", 
            font=ctk.CTkFont(weight="bold")
        )
        self.btn_start.grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self.btn_select_file = ctk.CTkButton(
            self.frame_controls, 
            text="📂 Chọn Tệp...", 
            command=self.select_local_files, 
            fg_color="#2b7a78", 
            hover_color="#17252a", 
            width=110
        )
        self.btn_select_file.grid(row=0, column=1, padx=10, pady=8, sticky="w")

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
        self.scrollable_frame = ctk.CTkScrollableFrame(self.tab_download, label_text="Danh sách Video", label_font=ctk.CTkFont(weight="bold"))
        self.scrollable_frame.grid(row=3, column=0, padx=15, pady=5, sticky="nsew")
        self.video_rows = {} # Lưu map: url -> {widgets}
        self.check_all_var = ctk.StringVar(value="off")

        # 4. Logs Console
        self.frame_logs_header = ctk.CTkFrame(self.tab_download, fg_color="transparent")
        self.frame_logs_header.grid(row=4, column=0, padx=15, pady=(10, 2), sticky="ew")
        self.frame_logs_header.grid_columnconfigure(1, weight=1) # Spacer giữa nhãn và nút

        self.label_logs = ctk.CTkLabel(self.frame_logs_header, text="Tiến trình hệ thống (Logs):", font=ctk.CTkFont(weight="bold"))
        self.label_logs.grid(row=0, column=0, sticky="w")

        self.btn_copy_logs = ctk.CTkButton(
            self.frame_logs_header, 
            text="📋 Sao chép Logs", 
            command=self.copy_logs,
            fg_color="#343a40",
            hover_color="#495057",
            height=24,
            width=120,
            font=ctk.CTkFont(size=12)
        )
        self.btn_copy_logs.grid(row=0, column=2, sticky="e")
        
        self.textbox_logs = ctk.CTkTextbox(self.tab_download, height=130, state="disabled")
        self.textbox_logs.grid(row=5, column=0, padx=15, pady=(0, 15), sticky="nsew")

    def log_message(self, message):
        """Hàm ghi log an toàn vào console."""
        self.textbox_logs.configure(state="normal")
        self.textbox_logs.insert("end", message + "\n")
        self.textbox_logs.see("end")
        self.textbox_logs.configure(state="disabled")

    def copy_logs(self):
        """Sao chép toàn bộ nội dung logs vào Clipboard."""
        try:
            logs_text = self.textbox_logs.get("1.0", "end-1c").strip()
            if logs_text:
                self.clipboard_clear()
                self.clipboard_append(logs_text)
                self.update() # Cần thiết trên Windows để đảm bảo ghi nhận clipboard
                # Phản hồi trực quan đổi màu nút
                self.btn_copy_logs.configure(text="✅ Đã sao chép!", fg_color="#28a745")
                self.after(2000, lambda: self.btn_copy_logs.configure(text="📋 Sao chép Logs", fg_color="#343a40"))
            else:
                self.log_message("Hệ thống: Không có nội dung log để sao chép.")
        except Exception as e:
            self.log_message(f"Hệ thống: Lỗi khi sao chép log: {e}")

    def on_url_textbox_modified(self, event=None):
        """Callback triggered when the textbox content is modified via paste or click."""
        try:
            # Reset modified state so Tkinter will fire the event again next time
            self.textbox_urls._textbox.edit_modified(False)
        except Exception:
            try:
                self.textbox_urls.edit_modified(False)
            except Exception:
                pass
        self.on_url_textbox_changed()

    def on_url_textbox_changed(self, event=None):
        """Handles key release events to trigger debounced auto-scanning."""
        if hasattr(self, "_debounce_timer_id") and self._debounce_timer_id is not None:
            self.after_cancel(self._debounce_timer_id)
            self._debounce_timer_id = None
        # Set a 1.2 seconds debounce timer before running auto-scan
        self._debounce_timer_id = self.after(1200, self.auto_scan_urls)

    def auto_scan_urls(self):
        """Scans the text area, validates URLs, caches the input, and runs the scanner."""
        self._debounce_timer_id = None
        urls_text = self.textbox_urls.get("1.0", "end").strip()
        if not urls_text:
            return
            
        # Avoid redundant scans of identical text
        if hasattr(self, "_last_scanned_urls_text") and self._last_scanned_urls_text == urls_text:
            return
            
        lines = [line.strip() for line in urls_text.split('\n') if line.strip()]
        if not lines:
            return
            
        # Ensure there is at least one valid URL
        valid_urls = [url for url in lines if url.startswith("http://") or url.startswith("https://")]
        if not valid_urls:
            return
            
        # Cache the current text to prevent duplicate scans
        self._last_scanned_urls_text = urls_text
        self.log_message("Hệ thống: Phát hiện liên kết mới, đang tự động quét...")
        self.scan_urls()

    def select_local_files(self):
        filetypes = (
            ('Video/Audio Files', '*.mp4;*.mkv;*.webm;*.mov;*.avi;*.mp3;*.wav;*.m4a'),
            ('All files', '*.*')
        )
        filenames = filedialog.askopenfilenames(
            title='Chọn tệp Video/Âm thanh',
            initialdir='/',
            filetypes=filetypes
        )
        if filenames:
            current_text = self.textbox_urls.get("1.0", "end").strip()
            new_lines = []
            if current_text:
                new_lines.append(current_text)
            for f in filenames:
                new_lines.append(f)
            
            new_urls_text = "\n".join(new_lines)
            self._last_scanned_urls_text = new_urls_text
            self.textbox_urls.delete("1.0", "end")
            self.textbox_urls.insert("end", new_urls_text)
            self.scan_urls()

    def clear_urls(self):
        self.textbox_urls.delete("1.0", "end")
        self._last_scanned_urls_text = ""
        try:
            self.textbox_urls._textbox.edit_modified(False)
        except Exception:
            pass

    def toggle_all(self):
        val = 1 if self.check_all_var.get() == "on" else 0
        for _, row in self.video_rows.items():
            if val:
                row['checkbox'].select()
            else:
                row['checkbox'].deselect()

    def toggle_all_sub(self):
        val = 1 if self.check_all_sub_var.get() == "on" else 0
        for _, row in self.video_rows.items():
            if row['cb_sub'].cget('state') != 'disabled':
                row['var_sub'].set(val)

    def toggle_all_whisper(self):
        val = 1 if self.check_all_whisper_var.get() == "on" else 0
        for _, row in self.video_rows.items():
            row['var_whisper'].set(val)

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
            results = fetch_video_list(urls, browser=browser_val, log_callback=self.log_message)
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
        
        # Tạo Header chứa các nút Chọn tất cả
        header_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        header_frame.pack(fill="x", expand=True, padx=5, pady=(5, 10))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0, minsize=120)
        header_frame.grid_columnconfigure(2, weight=0, minsize=80)
        header_frame.grid_columnconfigure(3, weight=0, minsize=80)
        header_frame.grid_columnconfigure(4, weight=0, minsize=110)
        
        header_title_frame = ctk.CTkFrame(header_frame, fg_color="transparent", width=330, height=28)
        header_title_frame.pack_propagate(False)
        header_title_frame.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        
        cb_all = ctk.CTkCheckBox(
            header_title_frame, 
            text="Chọn tất cả video", 
            variable=self.check_all_var, 
            onvalue="on", 
            offvalue="off", 
            command=self.toggle_all,
            font=ctk.CTkFont(weight="bold")
        )
        cb_all.pack(side="left", anchor="w")
        
        lbl_lang = ctk.CTkLabel(header_frame, text="Ngôn ngữ", text_color="#aaa", width=120, anchor="center")
        lbl_lang.grid(row=0, column=1, padx=(5,5), sticky="w")
        
        self.check_all_sub_var = ctk.StringVar(value="on")
        cb_all_sub = ctk.CTkCheckBox(header_frame, text="📝 Tất cả", variable=self.check_all_sub_var, command=self.toggle_all_sub)
        cb_all_sub.grid(row=0, column=2, padx=(5,5), sticky="w")
        
        self.check_all_whisper_var = ctk.StringVar(value="on")
        cb_all_whisper = ctk.CTkCheckBox(header_frame, text="🎙️ Tất cả", variable=self.check_all_whisper_var, command=self.toggle_all_whisper)
        cb_all_whisper.grid(row=0, column=3, padx=(5,5), sticky="w")
        
        # Dummy status frame để cân bằng base width với các row_frame bên dưới
        dummy_status = ctk.CTkFrame(header_frame, fg_color="transparent", width=110, height=28)
        dummy_status.pack_propagate(False)
        dummy_status.grid(row=0, column=4, padx=10, pady=2, sticky="e")
        
        # Helper: Marquee event handlers
        def start_marquee(event, widget, full_text):
            if len(full_text) <= 45: return
            widget.marquee_active = True
            widget.marquee_text = full_text + "   ***   "
            def scroll():
                if getattr(widget, 'marquee_active', False):
                    shifted = widget.marquee_text[1:] + widget.marquee_text[0]
                    widget.marquee_text = shifted
                    widget.configure(text=shifted[:45])
                    widget.after(150, scroll)
            scroll()
            
        def stop_marquee(event, widget, original_display):
            if getattr(widget, 'marquee_active', False):
                widget.marquee_active = False
                widget.configure(text=original_display)

        # Render từng hàng cho mỗi video quét được
        for idx, item in enumerate(results):
            title = item.get('title')
            url = item.get('url')
            is_main = item.get('is_main')
            platform = item.get('platform', 'generic')
            
            # Khởi tạo frame con cho hàng video
            row_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
            row_frame.pack(fill="x", expand=True, padx=5, pady=4)
            row_frame.grid_columnconfigure(0, weight=1) # Title chiếm 1/3
            row_frame.grid_columnconfigure(1, weight=0, minsize=120) # Dropdown sub lang
            row_frame.grid_columnconfigure(2, weight=0, minsize=80) # Checkbox sub
            row_frame.grid_columnconfigure(3, weight=0, minsize=80) # Checkbox whisper
            row_frame.grid_columnconfigure(4, weight=0, minsize=110) # Status label

            # Icon tương ứng với từng Platform
            platform_icons = {
                'youtube': '📹 [YouTube]',
                'youtube_shorts': '🩳 [Shorts]',
                'tiktok': '🎵 [TikTok]',
                'facebook': '👥 [Facebook]',
                'vimeo': '🌐 [Vimeo]',
                'local': '📂 [Máy tính]',
                'generic': '🔗 [Link]'
            }
            prefix = platform_icons.get(platform, '🔗')

            # Checkbox Video (với Marquee) được bọc trong Frame kích thước cố định để chống xê dịch
            title_container = ctk.CTkFrame(row_frame, fg_color="transparent", width=330, height=28)
            title_container.pack_propagate(False)
            title_container.grid(row=0, column=0, padx=5, pady=2, sticky="w")
            
            var = ctk.IntVar()
            full_title = f"{idx+1}. {prefix} {title}"
            display_title = full_title if len(full_title) <= 45 else full_title[:42] + "..."
            cb = ctk.CTkCheckBox(title_container, text=display_title, variable=var)
            cb.pack(side="left", anchor="w")
            
            # Bind events for marquee
            cb.bind("<Enter>", lambda e, w=cb, t=full_title: start_marquee(e, w, t))
            cb.bind("<Leave>", lambda e, w=cb, t=display_title: stop_marquee(e, w, t))
            
            if is_main:
                cb.select()
            else:
                cb.deselect()

            # Dropdown Ngôn ngữ Phụ đề (chuyển sang Cột 1)
            detected_lang = item.get('language')
            if item.get('is_local', False):
                default_lang_display = "Auto-detect (Tự động)"
            else:
                detected_lang = detected_lang or 'en'
                default_lang_display = SUBTITLE_LANGUAGES.get(detected_lang, f"{detected_lang.upper()} ({detected_lang})")
            
            lang_options = list(SUBTITLE_LANGUAGES.values())
            if default_lang_display not in lang_options:
                lang_options.insert(0, default_lang_display)
                
            cb_sub_lang = ctk.CTkOptionMenu(row_frame, values=lang_options, width=120)
            cb_sub_lang.set(default_lang_display)
            cb_sub_lang.grid(row=0, column=1, padx=(5,5), pady=2, sticky="w")
            
            # Checkbox Subtitle 📝 (chuyển sang Cột 2)
            var_sub = ctk.IntVar(value=1 if item.get('has_subtitles', False) else 0)
            cb_sub = ctk.CTkCheckBox(row_frame, text="📝", variable=var_sub)
            cb_sub.grid(row=0, column=2, padx=(5,5), pady=2, sticky="w")
            ToolTip(cb_sub, text="Tải Phụ đề (Subtitle)")
                
            # Checkbox Whisper 🎙️ (Cột 3)
            var_whisper = ctk.IntVar(value=1)
            cb_whisper = ctk.CTkCheckBox(row_frame, text="🎙️", variable=var_whisper)
            cb_whisper.grid(row=0, column=3, padx=(5,5), pady=2, sticky="w")
            ToolTip(cb_whisper, text="Nhận diện giọng nói (Whisper/Gemini)")

            # Status label
            status_container = ctk.CTkFrame(row_frame, fg_color="transparent", width=110, height=28)
            status_container.pack_propagate(False)
            status_container.grid(row=0, column=4, padx=10, pady=2, sticky="e")
            
            lbl_status = ctk.CTkLabel(status_container, text="Sẵn sàng", text_color="#aaa", font=ctk.CTkFont(size=11, weight="bold"))
            lbl_status.pack(fill="both", expand=True)

            # Lưu vào dictionary của app
            self.video_rows[url] = {
                'checkbox': cb,
                'status_label': lbl_status,
                'var': var,
                'var_sub': var_sub,
                'cb_sub': cb_sub,
                'cb_sub_lang': cb_sub_lang,
                'var_whisper': var_whisper,
                'title': title,
                'is_local': item.get('is_local', False)
            }
            
        self.reset_buttons()

    def update_video_progress(self, url, percent, downloaded_bytes, total_bytes):
        """Callback cập nhật % tải của từng video lên GUI."""
        if url in self.video_rows:
            row = self.video_rows[url]
            lbl = row['status_label']
            
            if percent == -1.0:
                self.after(0, lambda: lbl.configure(text="Thất bại ❌", text_color="#d62728"))
            elif percent == 100.0:
                self.after(0, lambda: lbl.configure(text="Hoàn thành ✔️", text_color="#2ca02c"))
            else:
                from history import format_size
                downloaded_str = format_size(downloaded_bytes)
                total_str = format_size(total_bytes)
                status_text = f"Đang tải {percent:.1f}% ({downloaded_str}/{total_str})"
                self.after(0, lambda: lbl.configure(text=status_text, text_color="#a855f7"))

    def update_diarization_progress(self, url, percent):
        """Callback cập nhật % nhận diện người nói."""
        if url in self.video_rows:
            row = self.video_rows[url]
            lbl = row['status_label']
            
            status_text = f"Phân tích người nói: {percent}%"
            self.after(0, lambda: lbl.configure(text=status_text, text_color="#a855f7"))

    def update_whisper_progress(self, url, percent, stats):
        """Callback cập nhật % tiến trình từ Whisper tqdm."""
        if url in self.video_rows:
            row = self.video_rows[url]
            lbl = row['status_label']
            
            status_text = f"Nhận diện âm thanh: {percent}% {stats}"
            self.after(0, lambda: lbl.configure(text=status_text, text_color="#a855f7"))

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

    def cancel_download(self):
        self.btn_start.configure(state="disabled", text="Đang hủy...")
        self.log_message("⚠️ Đang gửi yêu cầu hủy tiến trình...")
        self.cancel_event.set()

    def start_download(self):
        # Kiểm tra logic: nếu đang là nút Cancel thì Hủy thay vì Chạy
        if self.btn_start.cget("text") == "🛑 Hủy Tiến Trình":
            self.cancel_download()
            return

        # Lọc danh sách các video đã tích chọn
        selected_items = []
        for url, row in self.video_rows.items():
            if row['var'].get() == 1:
                selected_items.append((url, row))

        if not selected_items:
            self.log_message("Lỗi: Vui lòng quét link và tích chọn ít nhất 1 video để bắt đầu tải!")
            return

        self.cancel_event.clear()

        # Disable buttons để khóa tương tác khi đang tải
        self.btn_start.configure(text="🛑 Hủy Tiến Trình", fg_color="#d62728", hover_color="#9c1b1b")
        self.btn_scan.configure(state="disabled")
        self.btn_select_file.configure(state="disabled")
        self.btn_clear.configure(state="disabled")
        self.textbox_urls.configure(state="disabled")

        # Tạo Session Directory
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = os.path.join("downloads", f"Session_{now}")

        # Dọn dẹp logs cũ
        self.textbox_logs.configure(state="normal")
        self.textbox_logs.delete("1.0", "end")
        self.textbox_logs.configure(state="disabled")

        # Khởi động lại labels hiển thị tiến trình
        for url, row in selected_items:
            row['status_label'].configure(text="Đang chờ...", text_color="#aaa")

        tasks_to_process = []
        for url, row in selected_items:
            use_sub = row['var_sub'].get() == 1
            use_whisper = row['var_whisper'].get() == 1
            is_local = row.get('is_local', False)
            
            lang_display = row['cb_sub_lang'].get()
            lang_code = lang_display
            for k, v in SUBTITLE_LANGUAGES.items():
                if v == lang_display:
                    lang_code = k
                    break
            if lang_code == lang_display and "(" in lang_display:
                lang_code = lang_display.split("(")[-1].strip(")")
                
            tasks_to_process.append({
                'url': url,
                'use_sub': use_sub,
                'use_whisper': use_whisper,
                'is_local': is_local,
                'lang': lang_code
            })

        # Khởi chạy luồng tải ngầm để tránh đơ giao diện
        download_thread = threading.Thread(target=self.run_download_task, args=(tasks_to_process, session_dir))
        download_thread.daemon = True
        download_thread.start()

    def run_download_task(self, tasks, session_dir):
        # Đọc cấu hình mới nhất từ Tab Cài đặt để chạy tải
        lang = self.app_settings.get("subtitle_lang", "vi")
        download_video = self.app_settings.get("download_video", True)
        browser = self.app_settings.get("browser", "chrome")
        video_quality = self.app_settings.get("video_quality", "1080p")
        delay_min = float(self.app_settings.get("delay_min", 3.0))
        delay_max = float(self.app_settings.get("delay_max", 5.0))
        # transcript_mode is now overridden by per-task settings, we don't pass it globally
        whisper_model = self.app_settings.get("whisper_model", "medium")
        whisper_device = self.app_settings.get("whisper_device", "auto")
        whisper_model_dir = self.app_settings.get("whisper_model_dir", "models/whisper")
        enable_speaker_diarization = self.app_settings.get("enable_speaker_diarization", False)
        gemini_api_key = self.app_settings.get("gemini_api_key", "")
        gemini_model = self.app_settings.get("gemini_model", "gemini-2.5-flash")

        try:
            success_count, total_bytes, duration = process_multiple_urls(
                tasks=tasks,
                lang=lang,
                output_dir=session_dir,
                download_video=download_video,
                browser=browser,
                delay_min=delay_min,
                delay_max=delay_max,
                video_quality=video_quality,
                whisper_model=whisper_model,
                whisper_device=whisper_device,
                whisper_model_dir=whisper_model_dir,
                enable_speaker_diarization=enable_speaker_diarization,
                gemini_api_key=gemini_api_key,
                gemini_model=gemini_model,
                progress_callback=self.update_video_progress,
                delay_callback=self.update_delay_countdown,
                log_callback=self.log_message,
                diarization_progress_callback=self.update_diarization_progress,
                whisper_progress_callback=self.update_whisper_progress,
                cancel_event=self.cancel_event
            )

            # Lưu vào lịch sử nếu tải thành công
            if success_count > 0:
                history.save_session(
                    session_dir=session_dir,
                    urls=[t['url'] for t in tasks],
                    video_count=success_count,
                    total_bytes=total_bytes,
                    duration_seconds=duration
                )
                # Reset dashboard và lịch sử cuộn
                self.after(0, self.update_dashboard)
                
        except BaseException as e:
            if "hủy" in str(e).lower() or "cancel" in str(e).lower():
                self.log_message(f"❌ Tiến trình đã bị hủy bởi người dùng.")
            else:
                self.log_message(f"Lỗi nghiêm trọng khi xử lý: {e}")
        finally:
            self.after(0, self.reset_buttons)
            
            # Cập nhật các trạng thái cuối cùng cho giao diện
            for url, row in self.video_rows.items():
                if row['var'].get() == 1:
                    txt = row['status_label'].cget("text")
                    # Nếu status còn dạng đang chờ/đang tải thì chuyển thành Hoàn thành nếu đã kết thúc phiên thành công
                    if "Đang tải" in txt or "Đang chờ" in txt or "Tránh bot" in txt:
                        self.after(0, lambda r=row: r['status_label'].configure(text="Hoàn thành ✔️", text_color="#2ca02c"))

    def reset_buttons(self):
        self.btn_scan.configure(state="normal")
        self.btn_select_file.configure(state="normal")
        self.btn_clear.configure(state="normal")
        self.textbox_urls.configure(state="normal")
        self.btn_start.configure(state="normal", text="🚀 Bắt đầu Xử lý", fg_color="#1f538d", hover_color="#14375e")

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
            self.cb_download_video.deselect()
        row += 1

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
        
        # Sẽ được cập nhật động bằng self.update_hardware_requirement_label()
        whisper_models_initial = [
            "tiny (75MB)",
            "base (145MB)",
            "small (480MB)",
            "medium (1.5GB)",
            "large-v3 (2.9GB — CPU)"
        ]
        
        self.menu_whisper_model = ctk.CTkOptionMenu(
            self.settings_scroll,
            values=whisper_models_initial,
            command=self.update_hardware_requirement_label
        )
        self.menu_whisper_model.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        saved_model = self.app_settings.get("whisper_model", "medium")
        # Tìm model map ban đầu để set
        initial_set = "medium (1.5GB)"
        for opt in whisper_models_initial:
            if saved_model in opt:
                initial_set = opt
                break
        self.menu_whisper_model.set(initial_set); row += 1

        # Thiết bị xử lý
        ctk.CTkLabel(self.settings_scroll, text="Thiết bị xử lý:").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.menu_whisper_device = ctk.CTkOptionMenu(
            self.settings_scroll,
            values=["auto (tự động)", "cuda (GPU — Nhanh)", "cpu (CPU — Ổn định)"],
            command=self.update_hardware_requirement_label
        )
        self.menu_whisper_device.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        saved_device = self.app_settings.get("whisper_device", "auto")
        device_display_map = {
            "auto": "auto (tự động)", "cuda": "cuda (GPU — Nhanh)", "cpu": "cpu (CPU — Ổn định)"
        }
        self.menu_whisper_device.set(device_display_map.get(saved_device, "auto (tự động)")); row += 1

        # Frame Đánh giá Cấu hình Phần cứng tự động quét
        self.frame_hw_specs = ctk.CTkFrame(self.settings_scroll, fg_color="#1a1c23", corner_radius=8, border_width=1, border_color="#2b303c")
        self.frame_hw_specs.grid(row=row, column=0, columnspan=2, padx=15, pady=(5, 10), sticky="ew")
        self.frame_hw_specs.grid_columnconfigure(0, weight=1)
        row += 1
        
        lbl_hw_title = ctk.CTkLabel(self.frame_hw_specs, text="🖥️ ĐÁNH GIÁ CẤU HÌNH HỆ THỐNG", font=ctk.CTkFont(weight="bold", size=11), text_color="#888")
        lbl_hw_title.pack(anchor="w", padx=10, pady=(6, 4))
        
        self.lbl_hw_cpu = ctk.CTkLabel(
            self.frame_hw_specs, 
            text="CPU: Đang quét...", 
            font=ctk.CTkFont(size=11), 
            anchor="w",
            justify="left",
            wraplength=550
        )
        self.lbl_hw_cpu.pack(anchor="w", padx=15, pady=2)
        
        self.lbl_hw_ram = ctk.CTkLabel(
            self.frame_hw_specs, 
            text="RAM: Đang quét...", 
            font=ctk.CTkFont(size=11), 
            anchor="w",
            justify="left",
            wraplength=550
        )
        self.lbl_hw_ram.pack(anchor="w", padx=15, pady=2)
        
        self.lbl_hw_gpu = ctk.CTkLabel(
            self.frame_hw_specs, 
            text="GPU/VRAM: Đang quét...", 
            font=ctk.CTkFont(size=11), 
            anchor="w",
            justify="left",
            wraplength=550
        )
        self.lbl_hw_gpu.pack(anchor="w", padx=15, pady=2)
        
        self.lbl_hw_recommend = ctk.CTkLabel(
            self.frame_hw_specs, 
            text="Đang phân tích cấu hình tối ưu...", 
            font=ctk.CTkFont(size=11, weight="bold"), 
            anchor="w",
            justify="left",
            wraplength=550
        )
        self.lbl_hw_recommend.pack(anchor="w", padx=15, pady=(2, 8))

        # Kích hoạt quét cấu hình và cập nhật nhãn ngay lập tức
        self.update_hardware_requirement_label()

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
            self.cb_speaker_diarization.deselect()
        row += 1

        ctk.CTkLabel(self.settings_scroll, text="Chọn Mô hình Gemini:").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.menu_gemini_model = ctk.CTkOptionMenu(
            self.settings_scroll,
            values=["gemini-2.5-flash", "gemini-3-flash"]
        )
        self.menu_gemini_model.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        self.menu_gemini_model.set(self.app_settings.get("gemini_model", "gemini-2.5-flash")); row += 1

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

    def update_hardware_requirement_label(self, *args):
        """Quét cấu hình phần cứng thực tế và đánh giá độ tương thích của cấu hình được chọn."""
        try:
            # 1. Quét thông số phần cứng
            ram_gb = hardware_scanner.get_system_ram()
            gpu_info = hardware_scanner.get_gpu_info()
            cpu_desc = hardware_scanner.get_cpu_info()
            
            # 2. Xác định các lựa chọn tối ưu
            rec = hardware_scanner.get_recommendation(ram_gb, gpu_info)
            rec_model = rec["model"]
            rec_device = rec["device"]
            
            # 3. Cập nhật động danh sách dropdown Model Whisper để hiển thị chữ Khuyên dùng
            raw_models = [
                ("tiny", "tiny (75MB)"),
                ("base", "base (145MB)"),
                ("small", "small (480MB)"),
                ("medium", "medium (1.5GB)"),
                ("large-v3", "large-v3 (2.9GB — CPU)")
            ]
            
            whisper_models = []
            model_display_map = {}
            for m_id, label in raw_models:
                full_label = f"{label} (Khuyên dùng)" if m_id == rec_model else label
                whisper_models.append(full_label)
                model_display_map[m_id] = full_label
            
            current_model_sel = self.menu_whisper_model.get().split(" ")[0].lower()
            selected_m_id = "medium"
            for m_id, _ in raw_models:
                if m_id in current_model_sel:
                    selected_m_id = m_id
                    break
                    
            self.menu_whisper_model.configure(values=whisper_models)
            self.menu_whisper_model.set(model_display_map.get(selected_m_id, whisper_models[3]))
            
            # 4. Cập nhật động danh sách dropdown Thiết bị xử lý để hiển thị chữ Khuyên dùng
            raw_devices = [
                ("auto", "auto (tự động)"),
                ("cuda", "cuda (GPU — Nhanh)"),
                ("cpu", "cpu (CPU — Ổn định)")
            ]
            
            device_values = []
            device_display_map = {}
            for d_id, label in raw_devices:
                full_label = f"{label} (Khuyên dùng)" if d_id == rec_device else label
                device_values.append(full_label)
                device_display_map[d_id] = full_label
                
            current_device_sel = self.menu_whisper_device.get().split(" ")[0].lower()
            selected_d_id = "auto"
            for d_id, _ in raw_devices:
                if d_id in current_device_sel:
                    selected_d_id = d_id
                    break
                    
            self.menu_whisper_device.configure(values=device_values)
            self.menu_whisper_device.set(device_display_map.get(selected_d_id, device_values[0]))
            
            # 5. Lấy lại các lựa chọn thực tế hiện tại để so khớp phần cứng
            selected_model_str = self.menu_whisper_model.get().split(" ")[0].lower()
            selected_device_str = self.menu_whisper_device.get().split(" ")[0].lower()
            
            # 6. Kiểm tra độ tương thích
            ram_ok, vram_ok, overall_ok, ram_req, vram_req = hardware_scanner.check_compatibility(
                selected_model_str, selected_device_str, ram_gb, gpu_info
            )
            
            # 7. Render thông số và tô màu nhãn theo yêu cầu
            # CPU
            self.lbl_hw_cpu.configure(text=f"• CPU: {cpu_desc}", text_color="#2ca02c")
            
            # RAM [hiện tại] / [required]
            ram_text = f"• RAM: {ram_gb} GB / {ram_req} GB (Yêu cầu)"
            if ram_ok:
                self.lbl_hw_ram.configure(text=f"{ram_text} — Đạt yêu cầu", text_color="#2ca02c")
            else:
                self.lbl_hw_ram.configure(text=f"{ram_text} — Thiếu RAM (Có thể crash)", text_color="#d62728")
                
            # GPU / VRAM
            if "cuda" in selected_device_str or (selected_device_str == "auto" and gpu_info["available"]):
                if gpu_info["available"]:
                    vram_text = f"• VRAM GPU: {gpu_info['vram_gb']} GB / {vram_req} GB (Yêu cầu) ({gpu_info['name']})"
                    if vram_ok:
                        self.lbl_hw_gpu.configure(text=f"{vram_text} — Đạt yêu cầu", text_color="#2ca02c")
                    else:
                        self.lbl_hw_gpu.configure(text=f"{vram_text} — Thiếu VRAM (Có thể bị OOM)", text_color="#d62728")
                else:
                    self.lbl_hw_gpu.configure(text="• GPU/VRAM: Không phát hiện GPU CUDA!", text_color="#d62728")
            else:
                # CPU Mode
                vram_info_str = f" ({gpu_info['name']})" if gpu_info['available'] else " (Không dùng GPU)"
                self.lbl_hw_gpu.configure(text=f"• VRAM GPU: {gpu_info['vram_gb']} GB / 0.0 GB (Không yêu cầu){vram_info_str}", text_color="#2ca02c")
                
            # 8. Hiển thị đề xuất khuyến nghị & Cảnh báo hiệu suất chi tiết
            is_optimal_model = selected_model_str == rec_model
            is_optimal_device = selected_device_str == rec_device or (selected_device_str == "auto" and rec_device == "cuda" and gpu_info["available"])
            
            # Khởi tạo trạng thái màu và text mặc định
            rec_color = "#2ca02c"
            rec_text = "⭐ Lựa chọn tối ưu hiệu năng cho máy của bạn (Recommended)"

            # Xác định thiết bị thực tế sẽ chạy (nếu auto thì phụ thuộc vào GPU khả dụng)
            run_device = selected_device_str
            if selected_device_str == "auto":
                run_device = "cuda" if gpu_info["available"] else "cpu"

            if "cuda" in run_device:
                # Chạy trên GPU CUDA
                if not gpu_info["available"]:
                    rec_text = "❌ Cảnh báo: Chọn CUDA nhưng máy không có GPU NVIDIA hỗ trợ CUDA. Sẽ bị lỗi khi chạy!"
                    rec_color = "#d62728"
                elif selected_model_str in ["large", "large-v3", "large-v2"]:
                    if gpu_info["vram_gb"] < 10.0:
                        rec_text = f"⚠️ Cảnh báo hiệu suất: Model Large cần >= 10GB VRAM. GPU của bạn ({gpu_info['vram_gb']}GB) rất dễ bị lỗi tràn bộ nhớ CUDA Out of Memory (OOM)!"
                        rec_color = "#d62728"
                    else:
                        if is_optimal_model:
                            rec_text = "⭐ Khuyên dùng (Recommended): GPU cực mạnh, đáp ứng hoàn hảo model Large-v3 với độ chính xác cao nhất!"
                            rec_color = "#2ca02c"
                        else:
                            rec_text = f"💡 Đề xuất: GPU mạnh mẽ chạy được Large-v3, nhưng lựa chọn hiện tại ({selected_model_str}) có độ chính xác thấp hơn."
                            rec_color = "#ff7f0e"
                elif selected_model_str == "medium":
                    if gpu_info["vram_gb"] < 5.0:
                        rec_text = f"⚠️ Cảnh báo hiệu suất: Model Medium cần >= 5GB VRAM. GPU của bạn ({gpu_info['vram_gb']}GB) có nguy cơ cao bị tràn bộ nhớ CUDA Out of Memory (OOM)!"
                        rec_color = "#d62728"
                    else:
                        if is_optimal_model:
                            rec_text = "⭐ Khuyên dùng (Recommended): GPU đáp ứng tốt model Medium, chạy cực kỳ nhanh và chuẩn xác!"
                            rec_color = "#2ca02c"
                        else:
                            rec_text = f"💡 Đề xuất: Chạy rất tốt model Medium, nhưng bạn có thể nâng lên Large-v3 để tăng độ chính xác tối đa."
                            rec_color = "#ff7f0e"
                elif selected_model_str == "small":
                    if is_optimal_model:
                        rec_text = "⭐ Khuyên dùng (Recommended): Lựa chọn tối ưu nhất cho GPU tầm trung/VRAM thấp (như GTX 950) của bạn, chạy rất nhanh và ổn định!"
                        rec_color = "#2ca02c"
                    else:
                        rec_text = f"💡 Đề xuất: Small chạy rất mượt trên GPU. Khuyên dùng tối ưu nhất cho máy bạn là model {rec_model}."
                        rec_color = "#ff7f0e"
                else: # tiny, base
                    rec_text = f"💡 Đề xuất: Model {selected_model_str.upper()} chạy siêu nhanh trên GPU nhưng độ chính xác thấp. Nên nâng lên model 'small' hoặc 'medium' để dịch tốt hơn."
                    rec_color = "#ff7f0e"
            else:
                # Chạy trên CPU
                if selected_model_str in ["large", "large-v3", "large-v2"]:
                    rec_text = "⚠️ Cảnh báo hiệu suất: Chạy model Large trên CPU sẽ CỰC KỲ CHẬM (tốn hàng giờ), CPU sẽ quá tải 100% gây nóng máy/lag đơ hệ thống!"
                    rec_color = "#d62728"
                elif selected_model_str == "medium":
                    rec_text = "⚠️ Cảnh báo hiệu suất: Chạy model Medium trên CPU sẽ RẤT CHẬM và tốn tài nguyên máy tính. Khuyên dùng: small."
                    rec_color = "#d62728"
                elif selected_model_str == "small":
                    if is_optimal_model:
                        rec_text = "⭐ Khuyên dùng (Recommended): Model Small là lựa chọn tối ưu nhất trên CPU, cân bằng tuyệt vời giữa tốc độ và độ chính xác!"
                        rec_color = "#2ca02c"
                    else:
                        rec_text = f"💡 Đề xuất: Chạy được model Small nhưng máy bạn thiếu RAM/tài nguyên chưa đạt mức khuyến nghị cao nhất."
                        rec_color = "#ff7f0e"
                elif selected_model_str in ["base", "tiny"]:
                    if is_optimal_model:
                        rec_text = f"⭐ Khuyên dùng (Recommended): Model {selected_model_str.upper()} tối ưu nhất cho cấu hình CPU/RAM hiện tại của máy."
                        rec_color = "#2ca02c"
                    else:
                        rec_text = f"💡 Đề xuất: Chạy siêu nhanh nhưng độ chính xác thấp. Máy bạn dư sức chạy model 'small' để đạt độ chính xác cao hơn."
                        rec_color = "#ff7f0e"

            self.lbl_hw_recommend.configure(text=rec_text, text_color=rec_color)
                
        except Exception as e:
            # Fallback an toàn nếu có lỗi quét
            if hasattr(self, 'lbl_hw_recommend'):
                self.lbl_hw_recommend.configure(text=f"⚠️ Lỗi quét cấu hình phần cứng: {e}", text_color="#d62728")

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
                "gemini_api_key": self.entry_gemini_key.get().strip(),
                "gemini_model": self.menu_gemini_model.get()
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
