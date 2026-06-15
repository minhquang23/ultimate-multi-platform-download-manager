import os
import threading
import customtkinter as ctk
from src.services import hardware_scanner
from src.core.transcriber import check_whisper_available, download_whisper_model

class SettingsTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.build()

    def build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.settings_scroll = ctk.CTkScrollableFrame(self)
        self.settings_scroll.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        self.settings_scroll.grid_columnconfigure(1, weight=1)

        row = 0

        # ---- Nhóm 1: Tránh quét bot ----
        ctk.CTkLabel(self.settings_scroll, text="🛡️ CHỐNG PHÁT HIỆN BOT", font=ctk.CTkFont(weight="bold", size=13)).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(15, 8), sticky="w"); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Khoảng nghỉ tối thiểu (giây):").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.entry_delay_min = ctk.CTkEntry(self.settings_scroll, width=120)
        self.entry_delay_min.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        self.entry_delay_min.insert(0, str(self.app.app_settings.get("delay_min", 3.0))); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Khoảng nghỉ tối đa (giây):").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.entry_delay_max = ctk.CTkEntry(self.settings_scroll, width=120)
        self.entry_delay_max.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        self.entry_delay_max.insert(0, str(self.app.app_settings.get("delay_max", 5.0))); row += 1

        # Divider
        ctk.CTkLabel(self.settings_scroll, text="─" * 60, text_color="#444").grid(
            row=row, column=0, columnspan=2, padx=15, pady=8, sticky="ew"); row += 1

        # ---- Nhóm 2: Download ----
        ctk.CTkLabel(self.settings_scroll, text="📥 DOWNLOAD VIDEO & SUBTITLE", font=ctk.CTkFont(weight="bold", size=13)).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(5, 8), sticky="w"); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Chất lượng Video tối đa:").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.menu_quality = ctk.CTkOptionMenu(self.settings_scroll, values=["4K", "1080p", "720p", "480p", "Tốt nhất"])
        self.menu_quality.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        self.menu_quality.set(self.app.app_settings.get("video_quality", "1080p")); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Mã ngôn ngữ phụ đề (YouTube):").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.entry_sub_lang = ctk.CTkEntry(self.settings_scroll, width=120)
        self.entry_sub_lang.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        self.entry_sub_lang.insert(0, self.app.app_settings.get("subtitle_lang", "vi")); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Đọc Cookies từ trình duyệt:").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.menu_browser = ctk.CTkOptionMenu(self.settings_scroll, values=["chrome", "edge", "firefox", "brave", "opera", "Không dùng"])
        self.menu_browser.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        self.menu_browser.set(self.app.app_settings.get("browser", "chrome")); row += 1

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

        status_text = "✅ Whisper đã cài" if whisper_ok else "❌ Chưa cài Whisper — Chạy setup_local.ps1 để cài đặt"
        status_color = "#2ca02c" if whisper_ok else "#d62728"

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
        saved_model = self.app.app_settings.get("whisper_model", "medium")
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
        saved_device = self.app.app_settings.get("whisper_device", "auto")
        device_display_map = {
            "auto": "auto (tự động)", "cuda": "cuda (GPU — Nhanh)", "cpu": "cpu (CPU — Ổn định)"
        }
        self.menu_whisper_device.set(device_display_map.get(saved_device, "auto (tự động)")); row += 1

        # Frame Đánh giá cấu hình phần cứng
        self.frame_hw_specs = ctk.CTkFrame(self.settings_scroll, fg_color="#1a1c23", corner_radius=8, border_width=1, border_color="#2b303c")
        self.frame_hw_specs.grid(row=row, column=0, columnspan=2, padx=15, pady=(5, 10), sticky="ew")
        self.frame_hw_specs.grid_columnconfigure(0, weight=1)
        row += 1
        
        lbl_hw_title = ctk.CTkLabel(self.frame_hw_specs, text="🖥️ ĐÁNH GIÁ CẤU HÌNH HỆ THỐNG", font=ctk.CTkFont(weight="bold", size=11), text_color="#888")
        lbl_hw_title.pack(anchor="w", padx=10, pady=(6, 4))
        
        self.lbl_hw_cpu = ctk.CTkLabel(self.frame_hw_specs, text="CPU: Đang quét...", font=ctk.CTkFont(size=11), anchor="w", justify="left", wraplength=550)
        self.lbl_hw_cpu.pack(anchor="w", padx=15, pady=2)
        
        self.lbl_hw_ram = ctk.CTkLabel(self.frame_hw_specs, text="RAM: Đang quét...", font=ctk.CTkFont(size=11), anchor="w", justify="left", wraplength=550)
        self.lbl_hw_ram.pack(anchor="w", padx=15, pady=2)
        
        self.lbl_hw_gpu = ctk.CTkLabel(self.frame_hw_specs, text="GPU/VRAM: Đang quét...", font=ctk.CTkFont(size=11), anchor="w", justify="left", wraplength=550)
        self.lbl_hw_gpu.pack(anchor="w", padx=15, pady=2)
        
        self.lbl_hw_recommend = ctk.CTkLabel(self.frame_hw_specs, text="Đang phân tích...", font=ctk.CTkFont(size=11, weight="bold"), anchor="w", justify="left", wraplength=550)
        self.lbl_hw_recommend.pack(anchor="w", padx=15, pady=(2, 8))

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

        # ---- Nhóm 4: Cloud API (Mới chốt) ----
        ctk.CTkLabel(self.settings_scroll, text="☁️ CLOUD API STT (Whisper & Gemini)", font=ctk.CTkFont(weight="bold", size=13)).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(5, 4), sticky="w"); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Sử dụng API đám mây thay thế cho Whisper Local đối với máy cấu hình yếu.", font=ctk.CTkFont(size=11), text_color="#888").grid(
            row=row, column=0, columnspan=2, padx=15, pady=2, sticky="w"); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Sử dụng Cloud API:").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.cb_use_cloud_api = ctk.CTkCheckBox(self.settings_scroll, text="Bật Cloud API")
        self.cb_use_cloud_api.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        if self.app.app_settings.get("use_cloud_api", False):
            self.cb_use_cloud_api.select()
        else:
            self.cb_use_cloud_api.deselect(); 
        row += 1

        ctk.CTkLabel(self.settings_scroll, text="OpenAI API Key:").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.entry_openai_key = ctk.CTkEntry(self.settings_scroll, width=280, show="*")
        self.entry_openai_key.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        self.entry_openai_key.insert(0, self.app.app_settings.get("openai_api_key", "")); row += 1

        # Divider
        ctk.CTkLabel(self.settings_scroll, text="─" * 60, text_color="#444").grid(
            row=row, column=0, columnspan=2, padx=15, pady=8, sticky="ew"); row += 1

        # ---- Nhóm 5: Nhận diện người nói (Model C) ----
        ctk.CTkLabel(self.settings_scroll, text="👥 NHẬN DIỆN NGƯỜI NÓI (SPEAKER DIARIZATION)", font=ctk.CTkFont(weight="bold", size=13)).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(5, 4), sticky="w"); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Tính năng này dùng Heuristics + Gemini LLM để tự động gán tên người nói.", font=ctk.CTkFont(size=11), text_color="#888").grid(
            row=row, column=0, columnspan=2, padx=15, pady=2, sticky="w"); row += 1

        ctk.CTkLabel(self.settings_scroll, text="Bật nhận diện người nói:").grid(row=row, column=0, padx=15, pady=4, sticky="w")
        self.cb_speaker_diarization = ctk.CTkCheckBox(self.settings_scroll, text="Bật Model C")
        self.cb_speaker_diarization.grid(row=row, column=1, padx=15, pady=4, sticky="w")
        if self.app.app_settings.get("enable_speaker_diarization", False):
            self.cb_speaker_diarization.select()
        else:
            self.cb_speaker_diarization.deselect()
        row += 1

        # --- DEV MODE BUTTON & SAVE BUTTONS ---
        self.btn_dev_mode = ctk.CTkButton(
            self.settings_scroll, text="🔒", width=30, fg_color="transparent", text_color="gray", hover_color="#333333",
            command=self.app.toggle_dev_mode
        )
        self.btn_dev_mode.grid(row=row, column=0, padx=15, pady=4, sticky="w")
        row += 1

        # Divider
        ctk.CTkLabel(self.settings_scroll, text="─" * 60, text_color="#444").grid(
            row=row, column=0, columnspan=2, padx=15, pady=8, sticky="ew"); row += 1

        # Nhãn trạng thái lưu + Nút Lưu
        self.lbl_save_status = ctk.CTkLabel(self.settings_scroll, text="", font=ctk.CTkFont(weight="bold"))
        self.lbl_save_status.grid(row=row, column=0, columnspan=2, padx=15, pady=4); row += 1

        self.btn_save_settings = ctk.CTkButton(
            self.settings_scroll,
            text="💾 Lưu",
            command=self.app.save_app_settings,
            fg_color="green",
            hover_color="darkgreen",
            font=ctk.CTkFont(weight="bold")
        )
        self.btn_save_settings.grid(row=row, column=0, columnspan=2, padx=15, pady=(4, 20))

    def update_hardware_requirement_label(self, *args):
        """Quét cấu hình phần cứng thực tế và đánh giá độ tương thích của cấu hình được chọn."""
        try:
            ram_gb = hardware_scanner.get_system_ram()
            gpu_info = hardware_scanner.get_gpu_info()
            cpu_desc = hardware_scanner.get_cpu_info()
            
            rec = hardware_scanner.get_recommendation(ram_gb, gpu_info)
            rec_model = rec["model"]
            rec_device = rec["device"]
            
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
            
            selected_model_str = self.menu_whisper_model.get().split(" ")[0].lower()
            selected_device_str = self.menu_whisper_device.get().split(" ")[0].lower()
            
            ram_ok, vram_ok, overall_ok, ram_req, vram_req = hardware_scanner.check_compatibility(
                selected_model_str, selected_device_str, ram_gb, gpu_info
            )
            
            self.lbl_hw_cpu.configure(text=f"• CPU: {cpu_desc}", text_color="#2ca02c")
            
            ram_text = f"• RAM: {ram_gb} GB / {ram_req} GB (Yêu cầu)"
            if ram_ok:
                self.lbl_hw_ram.configure(text=f"{ram_text} — Đạt yêu cầu", text_color="#2ca02c")
            else:
                self.lbl_hw_ram.configure(text=f"{ram_text} — Thiếu RAM (Có thể crash)", text_color="#d62728")
                
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
                vram_info_str = f" ({gpu_info['name']})" if gpu_info['available'] else " (Không dùng GPU)"
                self.lbl_hw_gpu.configure(text=f"• VRAM GPU: {gpu_info['vram_gb']} GB / 0.0 GB (Không yêu cầu){vram_info_str}", text_color="#2ca02c")
                
            rec_color = "#2ca02c"
            rec_text = "⭐ Lựa chọn tối ưu hiệu năng cho máy của bạn (Recommended)"

            run_device = selected_device_str
            if selected_device_str == "auto":
                run_device = "cuda" if gpu_info["available"] else "cpu"

            if "cuda" in run_device:
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
                else:
                    rec_text = f"💡 Đề xuất: Model {selected_model_str.upper()} chạy siêu nhanh trên GPU nhưng độ chính xác thấp. Nên nâng lên model 'small' hoặc 'medium' để dịch tốt hơn."
                    rec_color = "#ff7f0e"
            else:
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
            if hasattr(self, 'lbl_hw_recommend'):
                self.lbl_hw_recommend.configure(text=f"⚠️ Lỗi quét cấu hình phần cứng: {e}", text_color="#d62728")

    def download_whisper_model_action(self):
        """Tải model Whisper đã chọn về máy."""
        model_raw = self.menu_whisper_model.get().split(" ")[0]
        model_name = 'large-v3' if model_raw == 'large-v3' else model_raw
        model_dir = self.app.app_settings.get("whisper_model_dir", "models/whisper")

        self.btn_dl_model.configure(state="disabled", text="Đang tải...")
        self.lbl_model_dl_status.configure(text=f"⏳ Đang tải model '{model_name}'...", text_color="#4fc1ff")

        def _do_download():
            ok = download_whisper_model(model_name, model_dir, log_callback=self.app.log_message)
            if ok:
                self.after(0, lambda: self.lbl_model_dl_status.configure(
                    text=f"✅ Đã tải xong model '{model_name}'!", text_color="#2ca02c"))
            else:
                self.after(0, lambda: self.lbl_model_dl_status.configure(
                    text=f"❌ Lỗi tải model! Xem Logs ở tab Tải về.", text_color="#d62728"))
            self.after(0, lambda: self.btn_dl_model.configure(
                state="normal", text="⬇️ Tải Model Whisper về máy"))

        threading.Thread(target=_do_download, daemon=True).start()
