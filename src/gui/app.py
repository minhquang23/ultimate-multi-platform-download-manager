import os
import sys
import time
import datetime
import threading
import multiprocessing
import queue
import customtkinter as ctk

# Sửa đổi import cho đúng cấu trúc mới
from src.services import settings_manager as settings
from src.services import history_manager as history
from src.services import ai_manager
from src.gui.tabs.download_tab import DownloadTab
from src.gui.tabs.settings_tab import SettingsTab
from src.gui.tabs.history_tab import HistoryTab
from src.core.processor import _worker_process

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Ultimate Multi-Platform Download Manager v3.0")
        self.geometry("900x820")
        
        # Load cấu hình
        self.app_settings = settings.load_settings()
        self.cancel_event = threading.Event()
        self.last_session_dir = None
        self.download_process = None
        
        # Cấu hình Layout chính (Grid)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Tạo TabView chính
        self.tabview = ctk.CTkTabview(self, segmented_button_selected_color="#1f538d", segmented_button_selected_hover_color="#14375e")
        self.tabview.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")

        # 3 Tab chính của ứng dụng
        self.tab_download_frame = self.tabview.add("🏠 Tải về")
        self.tab_settings_frame = self.tabview.add("⚙️ Cài đặt")
        self.tab_history_frame = self.tabview.add("📋 Lịch sử")

        # Khởi dựng các Tab giao diện
        self.download_tab = DownloadTab(self.tab_download_frame, self)
        self.download_tab.pack(fill="both", expand=True)

        self.settings_tab = SettingsTab(self.tab_settings_frame, self)
        self.settings_tab.pack(fill="both", expand=True)

        self.history_tab = HistoryTab(self.tab_history_frame, self)
        self.history_tab.pack(fill="both", expand=True)

        # Khởi tạo AI Manager và cấu hình thông báo
        self.aim = ai_manager.AIManager()
        self.aim.set_notification_callback(self.on_ai_notification)

        # Cập nhật thông số Dashboard lịch sử ban đầu
        self.history_tab.update_dashboard()

    def log_message(self, message):
        """Ghi log an toàn vào console."""
        self.download_tab.log_message(message)

    def open_session_folder(self, folder_path):
        """Mở thư mục trên Windows Explorer."""
        if os.path.exists(folder_path):
            try:
                os.startfile(os.path.abspath(folder_path))
            except Exception as e:
                self.log_message(f"Lỗi: Không thể mở thư mục: {e}")
        else:
            self.log_message(f"Thư mục lưu trữ không còn tồn tại trên máy tính: {folder_path}")

    def open_last_session(self):
        """Mở nhanh thư mục kết quả của phiên tải gần nhất."""
        if self.last_session_dir:
            self.open_session_folder(self.last_session_dir)

    def cancel_download(self):
        self.download_tab.btn_start.configure(state="disabled", text="Đang hủy...")
        self.log_message("⚠️ Đang gửi lệnh hủy và ép buộc dừng xử lý AI...")
        if self.download_process and self.download_process.is_alive():
            self.download_process.terminate()
            self.log_message("🛑 Đã hủy tiến trình thành công (ép buộc kết thúc).")
        self.reset_buttons()

    def start_download(self):
        # Kiểm tra logic: nếu đang là nút Cancel thì Hủy thay vì Chạy
        if self.download_tab.btn_start.cget("text") == "🛑 Hủy Tiến Trình":
            self.cancel_download()
            return

        # Lọc danh sách các video đã tích chọn
        selected_items = []
        for url, row in self.download_tab.video_rows.items():
            if row['var'].get() == 1:
                selected_items.append((url, row))

        if not selected_items:
            self.log_message("Lỗi: Vui lòng quét link và tích chọn ít nhất 1 video để bắt đầu tải!")
            return

        # Failsafe: Kiểm tra xem người dùng có chọn ít nhất 1 Tùy chọn tải nào không
        if self.download_tab.check_global_video_var.get() == 0 and self.download_tab.check_global_sub_var.get() == 0 and self.download_tab.check_global_whisper_var.get() == 0:
            self.log_message("❌ LỖI: Bạn chưa chọn thành phần nào để tải! Vui lòng chọn ít nhất Video, Phụ đề gốc hoặc Whisper ở phần Tùy chọn bên dưới.")
            return

        self.cancel_event.clear()

        # Disable buttons để khóa tương tác khi đang tải
        self.download_tab.btn_start.configure(text="🛑 Hủy Tiến Trình", fg_color="#d62728", hover_color="#9c1b1b")
        self.download_tab.btn_scan.configure(state="disabled")
        self.download_tab.btn_select_file.configure(state="disabled")
        self.download_tab.btn_clear.configure(state="disabled")
        self.download_tab.textbox_urls.configure(state="disabled")
        
        if hasattr(self.download_tab, 'cb_all'): self.download_tab.cb_all.configure(state="disabled")
        self.download_tab.cb_global_video.configure(state="disabled")
        self.download_tab.cb_global_sub.configure(state="disabled")
        self.download_tab.cb_global_whisper.configure(state="disabled")
        
        for row in self.download_tab.video_rows.values():
            row['checkbox'].configure(state="disabled")

        # Tạo Session Directory
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = os.path.join("downloads", f"Session_{now}")
        self.last_session_dir = session_dir
        self.download_tab.btn_open_folder.configure(state="disabled", fg_color="#34495e", hover_color="#2c3e50")

        # Dọn dẹp logs cũ
        self.download_tab.textbox_logs.configure(state="normal")
        self.download_tab.textbox_logs.delete("1.0", "end")
        self.download_tab.textbox_logs.configure(state="disabled")

        # Khởi động lại labels hiển thị tiến trình
        for url, row in selected_items:
            row['status_label'].configure(text="Đang chờ...", text_color="#aaa")

        tasks_to_process = []
        global_use_sub = self.download_tab.check_global_sub_var.get() == 1
        global_use_whisper = self.download_tab.check_global_whisper_var.get() == 1

        for url, row in selected_items:
            is_local = row.get('is_local', False)
            lang_code = ""
                
            tasks_to_process.append({
                'url': url,
                'use_sub': global_use_sub,
                'use_whisper': global_use_whisper,
                'is_local': is_local,
                'lang': lang_code,
                'platform': row.get('platform', 'generic'),
                'duration': row.get('duration'),
                'title': row.get('title', 'video')
            })

        # Khởi chạy luồng tải ngầm để tránh đơ giao diện
        download_thread = threading.Thread(target=self.run_download_task, args=(tasks_to_process, session_dir))
        download_thread.daemon = True
        download_thread.start()

    def run_download_task(self, tasks, session_dir):
        lang = self.app_settings.get("subtitle_lang", "vi")
        download_video = self.download_tab.check_global_video_var.get() == 1
        
        # Đồng bộ lưu lại thiết lập cấu hình global
        self.app_settings["download_video"] = download_video
        self.app_settings["use_global_sub"] = self.download_tab.check_global_sub_var.get() == 1
        self.app_settings["use_global_whisper"] = self.download_tab.check_global_whisper_var.get() == 1
        settings.save_settings(self.app_settings)

        browser = self.app_settings.get("browser", "chrome")
        video_quality = self.app_settings.get("video_quality", "1080p")
        delay_min = float(self.app_settings.get("delay_min", 3.0))
        delay_max = float(self.app_settings.get("delay_max", 5.0))
        whisper_model = self.app_settings.get("whisper_model", "medium")
        whisper_device = self.app_settings.get("whisper_device", "auto")
        whisper_model_dir = self.app_settings.get("whisper_model_dir", "models/whisper")
        enable_speaker_diarization = self.app_settings.get("enable_speaker_diarization", False)
        
        # Thêm Cloud API Settings
        use_cloud_api = self.app_settings.get("use_cloud_api", False)
        openai_api_key = self.app_settings.get("openai_api_key", "")
        gemini_api_key = self.app_settings.get("gemini_api_key", "")

        settings_dict = {
            'lang': lang,
            'download_video': download_video,
            'browser': browser,
            'delay_min': delay_min,
            'delay_max': delay_max,
            'video_quality': video_quality,
            'whisper_model': whisper_model,
            'whisper_device': whisper_device,
            'whisper_model_dir': whisper_model_dir,
            'enable_speaker_diarization': enable_speaker_diarization,
            'use_cloud_api': use_cloud_api,
            'openai_api_key': openai_api_key,
            'gemini_api_key': gemini_api_key
        }

        self.download_queue = multiprocessing.Queue()
        self.download_process = multiprocessing.Process(
            target=_worker_process,
            args=(self.download_queue, tasks, session_dir, settings_dict)
        )
        self.download_process.start()
        
        self.after(100, lambda: self._poll_queue(tasks, session_dir))

    def _poll_queue(self, tasks, session_dir):
        try:
            while True:
                msg_type, data = self.download_queue.get_nowait()
                if msg_type == "log":
                    self.log_message(data)
                elif msg_type == "prog":
                    self.download_tab.update_video_progress(*data)
                elif msg_type == "delay":
                    self.download_tab.update_video_delay(*data)
                elif msg_type == "d_prog":
                    self.download_tab.update_diarization_progress(*data)
                elif msg_type == "w_prog":
                    self.download_tab.update_whisper_progress(*data)
                elif msg_type == "w_lang":
                    self.download_tab.update_whisper_lang(*data)
                elif msg_type == "error":
                    self.log_message(f"Lỗi nghiêm trọng khi xử lý: {data}")
                    self.reset_buttons()
                    return
                elif msg_type == "done":
                    success_count, total_bytes, duration = data
                    if success_count > 0:
                        history.save_session(
                            session_dir=session_dir,
                            urls=[t['url'] for t in tasks],
                            video_count=success_count,
                            total_bytes=total_bytes,
                            duration_seconds=duration
                        )
                        self.history_tab.update_dashboard()
                    
                    self.reset_buttons()
                    for url, row in self.download_tab.video_rows.items():
                        if row['var'].get() == 1:
                            txt = row['status_label'].cget("text")
                            if "⬇️" in txt or "Đang chờ" in txt or "Nghỉ" in txt or "Whisper" in txt:
                                row['status_label'].configure(text="Hoàn thành ✔️", text_color="#2ca02c")
                    return
        except queue.Empty:
            pass

        if self.download_process and self.download_process.is_alive():
            self.after(100, lambda: self._poll_queue(tasks, session_dir))
        else:
            if self.download_tab.btn_start.cget("text") == "Đang hủy...":
                self.log_message("🛑 Đã hủy tiến trình thành công (ép buộc kết thúc).")
            self.reset_buttons()

    def reset_buttons(self):
        self.download_tab.reset_buttons()
        self.download_tab.btn_scan.configure(state="normal")
        self.download_tab.btn_select_file.configure(state="normal")
        self.download_tab.btn_clear.configure(state="normal")
        self.download_tab.textbox_urls.configure(state="normal")
        self.download_tab.btn_start.configure(state="normal", text="🚀 Bắt đầu Xử lý", fg_color="#1f538d", hover_color="#14375e")
        
        if self.last_session_dir and os.path.exists(self.last_session_dir):
            self.download_tab.btn_open_folder.configure(state="normal", fg_color="#2ca02c", hover_color="#218c21")
        
        if hasattr(self.download_tab, 'cb_all'): self.download_tab.cb_all.configure(state="normal")
        self.download_tab.cb_global_video.configure(state="normal")
        self.download_tab.cb_global_sub.configure(state="normal")
        self.download_tab.cb_global_whisper.configure(state="normal")
        
        for row in self.download_tab.video_rows.values():
            row['checkbox'].configure(state="normal")

    def save_app_settings(self):
        try:
            delay_min = float(self.settings_tab.entry_delay_min.get().strip())
            delay_max = float(self.settings_tab.entry_delay_max.get().strip())

            if delay_min < 0 or delay_max < 0 or delay_min > delay_max:
                self.settings_tab.lbl_save_status.configure(text="Lỗi: Khoảng nghỉ không hợp lệ (Min <= Max và >= 0)!", text_color="red")
                return

            model_display = self.settings_tab.menu_whisper_model.get().split(" ")[0]
            device_display = self.settings_tab.menu_whisper_device.get().split(" ")[0]

            new_settings = {
                "delay_min": delay_min,
                "delay_max": delay_max,
                "video_quality": self.settings_tab.menu_quality.get(),
                "subtitle_lang": self.settings_tab.entry_sub_lang.get().strip(),
                "download_video": self.download_tab.check_global_video_var.get() == 1,
                "browser": self.settings_tab.menu_browser.get(),
                
                # Whisper settings
                "whisper_model": model_display,
                "whisper_device": device_display,
                "transcript_mode": self.app_settings.get("transcript_mode", "prefer_subtitle"),
                "whisper_model_dir": self.app_settings.get("whisper_model_dir", "models/whisper"),
                
                # Cloud API settings
                "use_cloud_api": self.settings_tab.cb_use_cloud_api.get() == 1,
                "openai_api_key": self.settings_tab.entry_openai_key.get().strip(),
                
                # Speaker Diarization / Gemini
                "enable_speaker_diarization": self.settings_tab.cb_speaker_diarization.get() == 1,
                "gemini_api_key": self.app_settings.get("gemini_api_key", ""),
                "gemini_model": self.app_settings.get("gemini_model", "gemini-2.5-flash"),
                "ai_models": self.aim.get_models()
            }

            settings.save_settings(new_settings)
            self.app_settings = new_settings

            self.settings_tab.lbl_save_status.configure(text="💾 Đã lưu cài đặt thành công!", text_color="#2ca02c")
            self.after(3000, lambda: self.settings_tab.lbl_save_status.configure(text=""))
        except ValueError:
            self.settings_tab.lbl_save_status.configure(text="Lỗi: Min/Max khoảng nghỉ phải là các chữ số!", text_color="red")

    def on_ai_notification(self):
        self.settings_tab.btn_dev_mode.configure(text="🔒 (🔴)")
        self.build_ai_models_tab()

    def toggle_dev_mode(self):
        try:
            self.tabview.tab("[DEV] AI Manager")
            exists = True
        except ValueError:
            exists = False

        if exists:
            self.tabview.delete("[DEV] AI Manager")
            self.settings_tab.btn_dev_mode.configure(text="🔒")
            self.aim.clear_notifications()
        else:
            dialog = ctk.CTkInputDialog(text="Nhập mật khẩu Dev Mode:", title="Dev Mode")
            if dialog.get_input() == "minhhq":
                self.tab_dev_mode = self.tabview.add("[DEV] AI Manager")
                self.build_ai_models_tab()
                self.settings_tab.btn_dev_mode.configure(text="🔓")
                self.aim.clear_notifications()
                self.tabview.set("[DEV] AI Manager")
            else:
                self.settings_tab.lbl_save_status.configure(text="Sai mật khẩu!", text_color="red")

    def build_ai_models_tab(self):
        try:
            self.tabview.tab("[DEV] AI Manager")
        except ValueError:
            return

        for widget in self.tab_dev_mode.winfo_children():
            widget.destroy()

        self.scrollable_ai_models = ctk.CTkScrollableFrame(self.tab_dev_mode)
        self.scrollable_ai_models.pack(fill="both", expand=True, padx=5, pady=5)
            
        header_font = ctk.CTkFont(weight="bold", size=13)
        ctk.CTkLabel(self.scrollable_ai_models, text="STT", width=40, font=header_font).grid(row=0, column=0, padx=5, pady=10, sticky="w")
        ctk.CTkLabel(self.scrollable_ai_models, text="Mô hình (Model)", width=180, anchor="w", font=header_font).grid(row=0, column=1, padx=5, pady=10, sticky="w")
        ctk.CTkLabel(self.scrollable_ai_models, text="API Key", width=250, anchor="w", font=header_font).grid(row=0, column=2, padx=5, pady=10, sticky="w")
        ctk.CTkLabel(self.scrollable_ai_models, text="Hạn mức (Quota)", width=120, anchor="w", font=header_font).grid(row=0, column=3, padx=5, pady=10, sticky="w")
        ctk.CTkLabel(self.scrollable_ai_models, text="Trạng thái", width=100, anchor="w", font=header_font).grid(row=0, column=4, padx=5, pady=10, sticky="w")
        ctk.CTkLabel(self.scrollable_ai_models, text="Thao tác", width=120, anchor="w", font=header_font).grid(row=0, column=5, padx=5, pady=10, sticky="w")
        
        models = self.aim.get_models()
        self.ai_row_widgets = []
        self.current_order = list(range(len(models)))
        self.floating_drag_win = None
        self.hole_idx = -1
        
        self._verify_timers = getattr(self, '_verify_timers', {})
        
        def save_key(idx, val):
            m = self.aim.get_models()
            real_idx = self.current_order.index(idx) if idx in self.current_order else idx
            m[real_idx]['api_key'] = val
            self.aim.update_models(m)
            
            if idx in self._verify_timers:
                self.after_cancel(self._verify_timers[idx])
                
            def do_verify():
                model_name = m[real_idx]['name']
                if idx < len(self.ai_row_widgets):
                    lbl_status = self.ai_row_widgets[idx]['lbl_status']
                    lbl_quota = self.ai_row_widgets[idx]['lbl_quota']
                    lbl_status.configure(text="Đang kiểm tra...", text_color="#f97316")
                    
                    def verify_thread():
                        is_valid, status, quota = self.aim.verify_api_key(model_name, val)
                        def update_ui():
                            if idx < len(self.ai_row_widgets):
                                c = "#2ca02c" if is_valid else "#d62728"
                                if status == "Thiếu API Key": c = "#eab308"
                                self.ai_row_widgets[idx]['lbl_status'].configure(text=status, text_color=c)
                                self.ai_row_widgets[idx]['lbl_quota'].configure(text=quota)
                        self.after(0, update_ui)
                    
                    threading.Thread(target=verify_thread, daemon=True).start()
                    
            self._verify_timers[idx] = self.after(1500, do_verify)
            
        def on_drag_start(event, original_idx):
            self.hole_idx = self.current_order.index(original_idx)
            dragged_model = models[original_idx]
            
            for w in self.ai_row_widgets[original_idx]['widgets']:
                w.grid_remove()
            if self.ai_row_widgets[original_idx]['divider']:
                self.ai_row_widgets[original_idx]['divider'].grid_remove()
                
            self.floating_drag_win = ctk.CTkToplevel(self)
            self.floating_drag_win.overrideredirect(True)
            self.floating_drag_win.attributes("-topmost", True)
            self.floating_drag_win.geometry(f"500x40+{event.x_root - 450}+{event.y_root - 20}")
            
            frame = ctk.CTkFrame(self.floating_drag_win, fg_color="#1f538d", border_color="#4fc1ff", border_width=1)
            frame.pack(fill="both", expand=True)
            ctk.CTkLabel(frame, text=f"🔄 Đang kéo: {dragged_model['name']}", font=ctk.CTkFont(weight="bold")).pack(pady=8)
            
        def on_drag_motion(event):
            if not self.floating_drag_win: return
            self.floating_drag_win.geometry(f"+{event.x_root - 450}+{event.y_root - 20}")
            
            scroll_y = self.scrollable_ai_models.winfo_rooty()
            rel_y = event.y_root - scroll_y
            
            row_height = 45
            target_idx = int(max(0, min(len(self.current_order)-1, (rel_y - 40) / row_height)))
            
            if target_idx != self.hole_idx:
                item = self.current_order.pop(self.hole_idx)
                self.current_order.insert(target_idx, item)
                self.hole_idx = target_idx
                regrid_rows()
                
        def on_drag_release(event):
            if self.floating_drag_win:
                self.floating_drag_win.destroy()
                self.floating_drag_win = None
            
            if self.hole_idx != -1:
                new_models = [models[i] for i in self.current_order]
                self.aim.update_models(new_models)
                self.build_ai_models_tab()

        def regrid_rows():
            row_start = 1
            for pos_idx, logical_idx in enumerate(self.current_order):
                row_widgets = self.ai_row_widgets[logical_idx]
                if pos_idx != self.hole_idx:
                    if row_widgets['divider']:
                        row_widgets['divider'].grid(row=row_start, column=0, columnspan=6, sticky="ew", pady=(0, 5))
                    row_start += 1
                    for col, w in enumerate(row_widgets['widgets']):
                        w.grid(row=row_start, column=col, padx=5, pady=8, sticky="w" if col > 0 else "")
                row_start += 1

        def delete_model(idx):
            import tkinter.messagebox as tkmb
            real_idx = self.current_order.index(idx)
            if tkmb.askyesno("Xác nhận", f"Bạn có chắc chắn muốn xóa model này không?"):
                m = self.aim.get_models()
                m.pop(real_idx)
                self.aim.update_models(m)
                self.build_ai_models_tab()
                
        def edit_model(idx):
            real_idx = self.current_order.index(idx)
            self.open_edit_model_dialog(real_idx)
            
        row_idx = 1
        for i, m in enumerate(models):
            divider = ctk.CTkFrame(self.scrollable_ai_models, height=1, fg_color="#444")
            divider.grid(row=row_idx, column=0, columnspan=6, sticky="ew", pady=(0, 5))
            row_idx += 1
            
            lbl_stt = ctk.CTkLabel(self.scrollable_ai_models, text=str(i+1))
            lbl_stt.grid(row=row_idx, column=0, padx=5, pady=8)
            
            frame_model = ctk.CTkFrame(self.scrollable_ai_models, fg_color="transparent")
            frame_model.grid(row=row_idx, column=1, padx=5, pady=8, sticky="w")
            lbl_name = ctk.CTkLabel(frame_model, text=m['name'], font=ctk.CTkFont(weight="bold"))
            lbl_name.pack(anchor="w")
            
            link = m.get('link', '')
            if link:
                lbl_link = ctk.CTkLabel(frame_model, text="Lấy API Key", text_color="#4fc1ff", cursor="hand2", font=ctk.CTkFont(size=10, underline=True))
                lbl_link.pack(anchor="w")
                lbl_link.bind("<Button-1>", lambda e, l=link: os.startfile(l))
            
            frame_key = ctk.CTkFrame(self.scrollable_ai_models, fg_color="transparent")
            frame_key.grid(row=row_idx, column=2, padx=5, pady=8, sticky="w")
            entry_key = ctk.CTkEntry(frame_key, width=200, show="*")
            entry_key.insert(0, m['api_key'])
            entry_key.pack(side="left")
            entry_key.bind("<KeyRelease>", lambda e, idx=i, widget=entry_key: save_key(idx, widget.get()))
            
            btn_eye = ctk.CTkButton(frame_key, text="👁", width=30, fg_color="transparent", border_width=1, 
                                    command=lambda e=entry_key: e.configure(show="" if e.cget("show") == "*" else "*"))
            btn_eye.pack(side="left", padx=(5,0))
            
            lbl_quota = ctk.CTkLabel(self.scrollable_ai_models, text=m.get('quota', '-'))
            lbl_quota.grid(row=row_idx, column=3, padx=5, pady=8, sticky="w")
            
            status_text = m['status']
            if status_text == "Exhausted":
                import time
                wait = max(0, int(m.get('refresh_wait', 60) - (time.time() - m.get('exhausted_time', 0))))
                status_text = f"Đợi {wait}s"
                color = "red"
            elif "Test" in status_text or "kiểm tra" in status_text.lower():
                color = "orange"
            elif status_text == "Thiếu API Key":
                color = "#eab308"
            elif status_text == "Chưa xác thực":
                color = "#888888"
            elif "Lỗi" in status_text or "402" in status_text:
                color = "#d62728"
            else:
                color = "#2ca02c"
            lbl_status = ctk.CTkLabel(self.scrollable_ai_models, text=status_text, text_color=color)
            lbl_status.grid(row=row_idx, column=4, padx=5, pady=8, sticky="w")
            
            frame_actions = ctk.CTkFrame(self.scrollable_ai_models, fg_color="transparent")
            frame_actions.grid(row=row_idx, column=5, padx=5, pady=8, sticky="w")
            
            btn_edit = ctk.CTkButton(frame_actions, text="✏️", width=25, height=25, fg_color="transparent", hover_color="#444", command=lambda idx=i: edit_model(idx))
            btn_edit.pack(side="left", padx=2)
            
            btn_del = ctk.CTkButton(frame_actions, text="🗑️", width=25, height=25, fg_color="transparent", hover_color="#6b1a1a", command=lambda idx=i: delete_model(idx))
            btn_del.pack(side="left", padx=2)
            
            lbl_drag = ctk.CTkLabel(frame_actions, text="≡", width=25, height=25, cursor="fleur", text_color="gray", font=ctk.CTkFont(size=18, weight="bold"))
            lbl_drag.pack(side="left", padx=(5,2))
            
            lbl_drag.bind("<Button-1>", lambda e, idx=i: on_drag_start(e, idx))
            lbl_drag.bind("<B1-Motion>", on_drag_motion)
            lbl_drag.bind("<ButtonRelease-1>", on_drag_release)
            
            self.ai_row_widgets.append({
                'divider': divider,
                'widgets': [lbl_stt, frame_model, frame_key, lbl_quota, lbl_status, frame_actions],
                'lbl_status': lbl_status,
                'lbl_quota': lbl_quota,
                'model_idx': i
            })
            
            row_idx += 1
            
        noti = self.aim.get_notifications()
        if noti:
            lbl_noti = ctk.CTkLabel(self.scrollable_ai_models, text=f"🔔 Thông báo gần nhất: {noti[-1]['msg']}", text_color="yellow")
            lbl_noti.grid(row=row_idx, column=0, columnspan=6, pady=15, sticky="w", padx=15)
            row_idx += 1
            
        frame_bottom = ctk.CTkFrame(self.scrollable_ai_models, fg_color="transparent")
        frame_bottom.grid(row=row_idx, column=0, columnspan=6, pady=15, sticky="ew")
        
        btn_add_model = ctk.CTkButton(frame_bottom, text="➕ Thêm Model", command=self.open_add_model_dialog, fg_color="#1f538d")
        btn_add_model.pack(side="left", padx=15)
        
        def refresh_all_apis():
            for row in self.ai_row_widgets:
                idx = row['model_idx']
                m_info = self.aim.get_models()[idx]
                model_name = m_info['name']
                api_key = m_info['api_key']
                
                if api_key.strip() != "":
                    row['lbl_status'].configure(text="Đang kiểm tra...", text_color="#f97316")
                    
                    def verify_thread(r=row, m_name=model_name, key=api_key):
                        is_valid, status, quota = self.aim.verify_api_key(m_name, key)
                        def update_ui():
                            if r['lbl_status'].winfo_exists():
                                c = "#2ca02c" if is_valid else "#d62728"
                                if status == "Thiếu API Key": c = "#eab308"
                                r['lbl_status'].configure(text=status, text_color=c)
                                r['lbl_quota'].configure(text=quota)
                        self.after(0, update_ui)
                    threading.Thread(target=verify_thread, daemon=True).start()
                    
        btn_refresh_all = ctk.CTkButton(frame_bottom, text="🔄 Làm Mới Xác Thực", command=refresh_all_apis, fg_color="#ea580c", hover_color="#c2410c")
        btn_refresh_all.pack(side="left", padx=15)
        
        btn_save_models = ctk.CTkButton(frame_bottom, text="💾 Lưu Cài Đặt", command=self.flash_save_models, fg_color="green")
        btn_save_models.pack(side="left", padx=15)

    def flash_save_models(self):
        for widget in self.scrollable_ai_models.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                for child in widget.winfo_children():
                    if isinstance(child, ctk.CTkButton) and child.cget("text") == "💾 Lưu Cài Đặt":
                        child.configure(text="✅ Đã Lưu!", fg_color="#28a745")
                        self.after(2000, lambda c=child: c.configure(text="💾 Lưu Cài Đặt", fg_color="green"))
                        break
                        
    def open_edit_model_dialog(self, idx):
        m = self.aim.get_models()[idx]
        dialog = ctk.CTkToplevel(self)
        dialog.title("Sửa Model")
        dialog.geometry("400x500")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Tên hiển thị:").pack(pady=(10,0), padx=10, anchor="w")
        entry_name = ctk.CTkEntry(dialog, width=380)
        entry_name.insert(0, m.get('name', ''))
        entry_name.pack(pady=5, padx=10)
        
        ctk.CTkLabel(dialog, text="Provider (openai / google):").pack(pady=(10,0), padx=10, anchor="w")
        entry_provider = ctk.CTkEntry(dialog, width=380)
        entry_provider.insert(0, m.get('provider', ''))
        entry_provider.pack(pady=5, padx=10)
        
        ctk.CTkLabel(dialog, text="Model ID (ví dụ: gpt-5):").pack(pady=(10,0), padx=10, anchor="w")
        entry_model = ctk.CTkEntry(dialog, width=380)
        entry_model.insert(0, m.get('model', ''))
        entry_model.pack(pady=5, padx=10)
        
        ctk.CTkLabel(dialog, text="Endpoint (Bỏ trống nếu là google):").pack(pady=(10,0), padx=10, anchor="w")
        entry_endpoint = ctk.CTkEntry(dialog, width=380)
        entry_endpoint.insert(0, m.get('endpoint', ''))
        entry_endpoint.pack(pady=5, padx=10)
        
        ctk.CTkLabel(dialog, text="Link lấy Key (Tùy chọn):").pack(pady=(10,0), padx=10, anchor="w")
        entry_link = ctk.CTkEntry(dialog, width=380)
        entry_link.insert(0, m.get('link', ''))
        entry_link.pack(pady=5, padx=10)
        
        ctk.CTkLabel(dialog, text="Quota hiển thị (Tùy chọn):").pack(pady=(10,0), padx=10, anchor="w")
        entry_quota = ctk.CTkEntry(dialog, width=380)
        entry_quota.insert(0, m.get('quota', ''))
        entry_quota.pack(pady=5, padx=10)
        
        def save_edit():
            name = entry_name.get().strip()
            if not name: return
            models = self.aim.get_models()
            models[idx]["name"] = name
            models[idx]["provider"] = entry_provider.get().strip()
            models[idx]["model"] = entry_model.get().strip()
            models[idx]["endpoint"] = entry_endpoint.get().strip()
            models[idx]["link"] = entry_link.get().strip()
            models[idx]["quota"] = entry_quota.get().strip()
            self.aim.update_models(models)
            self.build_ai_models_tab()
            dialog.destroy()
            
        ctk.CTkButton(dialog, text="Lưu thay đổi", command=save_edit).pack(pady=20)

    def open_add_model_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Thêm Model Mới")
        dialog.geometry("400x450")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Tên hiển thị:").pack(pady=(10,0), padx=10, anchor="w")
        entry_name = ctk.CTkEntry(dialog, width=380)
        entry_name.pack(pady=5, padx=10)
        
        ctk.CTkLabel(dialog, text="Provider (openai / google):").pack(pady=(10,0), padx=10, anchor="w")
        entry_provider = ctk.CTkEntry(dialog, width=380)
        entry_provider.insert(0, "openai")
        entry_provider.pack(pady=5, padx=10)
        
        ctk.CTkLabel(dialog, text="Model ID (ví dụ: gpt-5):").pack(pady=(10,0), padx=10, anchor="w")
        entry_model = ctk.CTkEntry(dialog, width=380)
        entry_model.pack(pady=5, padx=10)
        
        ctk.CTkLabel(dialog, text="Endpoint (Bỏ trống nếu là google):").pack(pady=(10,0), padx=10, anchor="w")
        entry_endpoint = ctk.CTkEntry(dialog, width=380)
        entry_endpoint.insert(0, "https://api.openai.com/v1/chat/completions")
        entry_endpoint.pack(pady=5, padx=10)
        
        def save_new():
            name = entry_name.get().strip()
            if not name: return
            new_model = {
                "name": name,
                "provider": entry_provider.get().strip(),
                "model": entry_model.get().strip(),
                "api_key": "",
                "endpoint": entry_endpoint.get().strip(),
                "quota": "Custom",
                "link": "",
                "status": "Sẵn sàng",
                "exhausted_time": 0,
                "refresh_wait": 0
            }
            m = self.aim.get_models()
            m.append(new_model)
            self.aim.update_models(m)
            self.build_ai_models_tab()
            dialog.destroy()
            
        ctk.CTkButton(dialog, text="Thêm", command=save_new).pack(pady=20)
