import os
import glob
import urllib.parse
import threading
import customtkinter as ctk
from tkinter import filedialog
from src.gui.tooltips import ToolTip
from src.core.downloader import fetch_video_list
from src.services.title_cleaner import clean_video_title, detect_platform, sanitize_filename

# Subtitle languages mapping
SUBTITLE_LANGUAGES = {
    "vi": "Tiếng Việt (vi)",
    "en": "Tiếng Anh (en)",
    "ja": "Tiếng Nhật (ja)",
    "ko": "Tiếng Hàn (ko)",
    "zh-Hans": "Tiếng Trung (zh)",
    "zh": "Tiếng Trung (zh)",
    "es": "Tây Ban Nha (es)",
    "fr": "Tiếng Pháp (fr)",
    "de": "Tiếng Đức (de)",
    "ru": "Tiếng Nga (ru)"
}

class DownloadTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._debounce_timer_id = None
        self._last_scanned_urls_text = ""
        self.video_rows = {}
        self.build()

    def build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0) # Ô URL co giãn
        self.grid_rowconfigure(3, weight=1) # Danh sách video co giãn tối đa
        self.grid_rowconfigure(6, weight=0) # Ô Logs

        # 1. Nhãn & Hộp nhập URL
        self.label_urls = ctk.CTkLabel(self, text="Nhập các URL (YouTube, Shorts, TikTok, Facebook, Vimeo), mỗi dòng 1 URL:", font=ctk.CTkFont(weight="bold"))
        self.label_urls.grid(row=0, column=0, padx=15, pady=(15, 2), sticky="w")
        self.textbox_urls = ctk.CTkTextbox(self, height=110)
        self.textbox_urls.grid(row=1, column=0, padx=15, pady=2, sticky="nsew")
        
        self.textbox_urls.bind("<KeyRelease>", self.on_url_textbox_changed)
        try:
            self.textbox_urls._textbox.bind("<<Modified>>", self.on_url_textbox_modified)
        except Exception:
            self.textbox_urls.bind("<<Modified>>", self.on_url_textbox_modified)

        # 2. Thanh Controls
        self.frame_controls = ctk.CTkFrame(self)
        self.frame_controls.grid(row=2, column=0, padx=15, pady=8, sticky="ew")
        self.frame_controls.grid_columnconfigure(2, weight=1)

        self.btn_scan = ctk.CTkButton(
            self.frame_controls, 
            text="🔍 Quét Link", 
            command=self.scan_urls, 
            fg_color="#2b7a78", 
            hover_color="#17252a", 
            font=ctk.CTkFont(weight="bold")
        )
        
        self.btn_start = ctk.CTkButton(
            self.frame_controls, 
            text="🚀 Bắt đầu Xử lý", 
            command=self.app.start_download, 
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

        self.btn_open_folder = ctk.CTkButton(
            self.frame_controls, 
            text="📂", 
            width=40,
            command=self.app.open_last_session, 
            fg_color="#34495e", 
            hover_color="#2c3e50", 
            font=ctk.CTkFont(weight="bold", size=15),
            state="disabled"
        )
        self.btn_open_folder.grid(row=0, column=2, padx=10, pady=8, sticky="w")
        ToolTip(self.btn_open_folder, text="Mở thư mục kết quả của phiên tải gần nhất")

        self.btn_clear = ctk.CTkButton(
            self.frame_controls, 
            text="🧹 Dọn dẹp URL", 
            command=self.clear_urls, 
            fg_color="#5a6268", 
            hover_color="#495057", 
            width=110
        )
        self.btn_clear.grid(row=0, column=3, padx=10, pady=8, sticky="e")
        self.frame_controls.grid_columnconfigure(3, weight=1)

        # 3. Danh sách check chọn video (Scrollable)
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="Danh sách Video", label_font=ctk.CTkFont(weight="bold"))
        self.scrollable_frame.grid(row=3, column=0, padx=15, pady=5, sticky="nsew")
        self.check_all_var = ctk.StringVar(value="off")

        # 4. Tùy chọn tải (Global Options)
        self.frame_download_options = ctk.CTkFrame(self)
        self.frame_download_options.grid(row=4, column=0, padx=15, pady=(0, 5), sticky="ew")
        
        lbl_options = ctk.CTkLabel(self.frame_download_options, text="Tùy chọn tải:", font=ctk.CTkFont(weight="bold"))
        lbl_options.pack(side="left", padx=10, pady=10)
        
        self.check_global_video_var = ctk.IntVar(value=1 if self.app.app_settings.get("download_video", True) else 0)
        self.cb_global_video = ctk.CTkCheckBox(self.frame_download_options, text="🎬 Tải Tệp Video", variable=self.check_global_video_var)
        self.cb_global_video.pack(side="left", padx=15)
        
        self.check_global_sub_var = ctk.IntVar(value=1 if self.app.app_settings.get("use_global_sub", True) else 0)
        self.cb_global_sub = ctk.CTkCheckBox(self.frame_download_options, text="📝 Lấy Phụ đề gốc (Nếu có)", variable=self.check_global_sub_var)
        self.cb_global_sub.pack(side="left", padx=15)
        
        self.check_global_whisper_var = ctk.IntVar(value=1 if self.app.app_settings.get("use_global_whisper", True) else 0)
        self.cb_global_whisper = ctk.CTkCheckBox(self.frame_download_options, text="🎙️ Dùng Whisper (AI Dịch)", variable=self.check_global_whisper_var)
        self.cb_global_whisper.pack(side="left", padx=15)

        # 5. Logs Console
        self.frame_logs_header = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_logs_header.grid(row=5, column=0, padx=15, pady=(10, 2), sticky="ew")
        self.frame_logs_header.grid_columnconfigure(1, weight=1)

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
        
        self.textbox_logs = ctk.CTkTextbox(self, height=130, state="disabled")
        self.textbox_logs.grid(row=6, column=0, padx=15, pady=(0, 15), sticky="nsew")

    def log_message(self, message):
        self.textbox_logs.configure(state="normal")
        self.textbox_logs.insert("end", message + "\n")
        self.textbox_logs.see("end")
        self.textbox_logs.configure(state="disabled")

    def copy_logs(self):
        try:
            logs_text = self.textbox_logs.get("1.0", "end-1c").strip()
            if logs_text:
                self.app.clipboard_clear()
                self.app.clipboard_append(logs_text)
                self.app.update()
                self.btn_copy_logs.configure(text="✅ Đã sao chép!", fg_color="#28a745")
                self.after(2000, lambda: self.btn_copy_logs.configure(text="📋 Sao chép Logs", fg_color="#343a40"))
            else:
                self.log_message("Hệ thống: Không có nội dung log để sao chép.")
        except Exception as e:
            self.log_message(f"Hệ thống: Lỗi khi sao chép log: {e}")

    def on_url_textbox_modified(self, event=None):
        try:
            self.textbox_urls._textbox.edit_modified(False)
        except Exception:
            try:
                self.textbox_urls.edit_modified(False)
            except Exception:
                pass
        self.on_url_textbox_changed()

    def on_url_textbox_changed(self, event=None):
        if self._debounce_timer_id is not None:
            self.after_cancel(self._debounce_timer_id)
            self._debounce_timer_id = None
        self._debounce_timer_id = self.after(1200, self.auto_scan_urls)

    def auto_scan_urls(self):
        self._debounce_timer_id = None
        urls_text = self.textbox_urls.get("1.0", "end").strip()
        if not urls_text:
            return
            
        if self._last_scanned_urls_text == urls_text:
            return
            
        lines = [line.strip() for line in urls_text.split('\n') if line.strip()]
        if not lines:
            return
            
        valid_urls = [url for url in lines if url.startswith("http://") or url.startswith("https://")]
        if not valid_urls:
            return
            
        self._last_scanned_urls_text = urls_text
        self.log_message("Hệ thống: Phát hiện liên kết mới, đang tự động quét...")
        self.scan_urls()

    def select_local_files(self):
        filetypes = (
            ('Video/Audio Files', '*.mp4;*.mkv;*.webm;*.mov;*.avi;*.mp3;*.wav;*.m4a'),
            ('All files', '*.*')
        )
        filenames = filedialog.askopenfilenames(
            parent=self.app,
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

    def scan_urls(self):
        urls_text = self.textbox_urls.get("1.0", "end").strip()
        if not urls_text:
            self.log_message("Lỗi: Vui lòng nhập ít nhất 1 URL để quét!")
            return
            
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        
        self.btn_scan.configure(state="disabled", text="Đang quét...")
        self.btn_start.configure(state="disabled")
        self.log_message("Bắt đầu quét danh sách video...")
        
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.video_rows.clear()
        
        browser_val = self.app.app_settings.get("browser", "chrome")
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
        
        header_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        header_frame.pack(fill="x", expand=True, padx=5, pady=(5, 10))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0, minsize=120)
        header_frame.grid_columnconfigure(2, weight=0, minsize=110)
        
        header_title_frame = ctk.CTkFrame(header_frame, fg_color="transparent", width=330, height=28)
        header_title_frame.pack_propagate(False)
        header_title_frame.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        
        self.check_all_var = ctk.StringVar(value="off")
        self.cb_all = ctk.CTkCheckBox(
            header_title_frame, 
            text="Chọn tất cả video", 
            variable=self.check_all_var, 
            onvalue="on", 
            offvalue="off", 
            command=self.toggle_all,
            font=ctk.CTkFont(weight="bold")
        )
        self.cb_all.pack(side="left", anchor="w")
        
        lbl_lang = ctk.CTkLabel(header_frame, text="Ngôn ngữ", text_color="#aaa", width=120, anchor="center")
        lbl_lang.grid(row=0, column=1, padx=(5,5), sticky="w")
        
        dummy_status = ctk.CTkFrame(header_frame, fg_color="transparent", width=110, height=28)
        dummy_status.pack_propagate(False)
        dummy_status.grid(row=0, column=2, padx=10, pady=2, sticky="e")
        
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

        for idx, item in enumerate(results):
            title = item.get('title')
            url = item.get('url')
            is_main = item.get('is_main')
            platform = item.get('platform', 'generic')
            
            row_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
            row_frame.pack(fill="x", expand=True, padx=5, pady=4)
            row_frame.grid_columnconfigure(0, weight=1)
            row_frame.grid_columnconfigure(1, weight=0, minsize=120)
            row_frame.grid_columnconfigure(2, weight=0, minsize=110)

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

            title_container = ctk.CTkFrame(row_frame, fg_color="transparent", width=330, height=28)
            title_container.pack_propagate(False)
            title_container.grid(row=0, column=0, padx=5, pady=2, sticky="w")
            
            var = ctk.IntVar()
            full_title = f"{idx+1}. {prefix} {title}"
            display_title = full_title if len(full_title) <= 45 else full_title[:42] + "..."
            cb = ctk.CTkCheckBox(title_container, text=display_title, variable=var)
            cb.pack(side="left", anchor="w")
            
            cb.bind("<Enter>", lambda e, w=cb, t=full_title: start_marquee(e, w, t))
            cb.bind("<Leave>", lambda e, w=cb, t=display_title: stop_marquee(e, w, t))
            
            if is_main:
                cb.select()
            else:
                cb.deselect()

            detected_lang = item.get('language')
            if item.get('is_local', False) or not detected_lang:
                default_lang_display = "Auto-detect"
            else:
                default_lang_display = SUBTITLE_LANGUAGES.get(detected_lang, f"{detected_lang.upper()} ({detected_lang})")
                
            lbl_lang_val = ctk.CTkLabel(row_frame, text=default_lang_display, text_color="#2b7a78", width=120, anchor="w")
            lbl_lang_val.grid(row=0, column=1, padx=(5,5), pady=2, sticky="w")
            
            status_container = ctk.CTkFrame(row_frame, fg_color="transparent", width=180, height=28)
            status_container.pack_propagate(False)
            status_container.grid(row=0, column=2, padx=10, pady=2, sticky="e")
            
            if not item.get('has_subtitles', False) and not item.get('is_local', False):
                initial_status = "❌ Ko Sub YT"
            else:
                initial_status = "Sẵn sàng"
                
            lbl_status = ctk.CTkLabel(status_container, text=initial_status, text_color="#aaa", font=ctk.CTkFont(size=11, weight="bold"))
            lbl_status.pack(fill="both", expand=True)

            self.video_rows[url] = {
                'checkbox': cb,
                'status_label': lbl_status,
                'var': var,
                'lbl_lang_val': lbl_lang_val,
                'title': title,
                'is_local': item.get('is_local', False),
                'platform': platform,
                'duration': item.get('duration')
            }
            
        self.reset_buttons()

    def reset_buttons(self):
        self.btn_scan.configure(state="normal", text="🔍 Quét Link")
        self.btn_start.configure(state="normal")

    def update_whisper_lang(self, url, detected_lang):
        if url in self.video_rows:
            def _update():
                row = self.video_rows[url]
                display_lang = SUBTITLE_LANGUAGES.get(detected_lang, f"{detected_lang.upper()} ({detected_lang})")
                row['lbl_lang_val'].configure(text=display_lang, text_color="#2b7a78")
                row['status_label'].configure(text="Sub/Transcript bởi Whisper", text_color="#2ca02c")
            self.after(0, _update)

    def update_video_progress(self, url, percent, downloaded_bytes, total_bytes):
        if url in self.video_rows:
            row = self.video_rows[url]
            lbl = row['status_label']
            
            from src.services.history_manager import format_size
            pct_str = f"{percent:.1f}%"
            stats_str = f"({format_size(downloaded_bytes)}/{format_size(total_bytes)})"
            
            def _update():
                lbl.configure(text=f"⬇️ {pct_str} {stats_str}", text_color="#1f77b4")
            self.after(0, _update)

    def update_video_delay(self, url, remaining_seconds):
        if url in self.video_rows:
            row = self.video_rows[url]
            lbl = row['status_label']
            def _update():
                if remaining_seconds > 0:
                    lbl.configure(text=f"🛡️ Nghỉ {remaining_seconds:.1f}s", text_color="#ff7f0e")
                else:
                    lbl.configure(text="Sẵn sàng", text_color="#aaa")
            self.after(0, _update)

    def update_diarization_progress(self, url, percent):
        if url in self.video_rows:
            row = self.video_rows[url]
            lbl = row['status_label']
            def _update():
                lbl.configure(text=f"🧠 Phân tích AI: {percent}%", text_color="#9467bd")
            self.after(0, _update)

    def update_whisper_progress(self, url, percent, progress_stats):
        if url in self.video_rows:
            row = self.video_rows[url]
            lbl = row['status_label']
            def _update():
                lbl.configure(text=f"🎙️ Whisper: {percent}% {progress_stats}", text_color="#2ca02c")
            self.after(0, _update)
