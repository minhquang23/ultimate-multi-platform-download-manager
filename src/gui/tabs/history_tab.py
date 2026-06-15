import os
import customtkinter as ctk
from src.services import history_manager as history

class HistoryTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.limit = 10
        self.offset = 0
        self.btn_load_more = None
        self.build()

    def build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 1. Dashboard Thống kê
        self.frame_dashboard = ctk.CTkFrame(self, fg_color="#1e222b", height=95)
        self.frame_dashboard.grid(row=0, column=0, padx=15, pady=15, sticky="ew")
        for col in range(4):
            self.frame_dashboard.grid_columnconfigure(col, weight=1)

        # 4 Thẻ Dashboard
        self.card_sessions = self.create_stat_card(self.frame_dashboard, "📋 Tổng Phiên Tải", "0", 0)
        self.card_videos = self.create_stat_card(self.frame_dashboard, "📹 Video Đã Tải", "0", 1)
        self.card_bytes = self.create_stat_card(self.frame_dashboard, "💾 Tổng Dung Lượng", "0 B", 2)
        self.card_duration = self.create_stat_card(self.frame_dashboard, "⏱️ Tổng Thời Gian", "0s", 3)

        # 2. Scrollable History List
        self.scroll_history = ctk.CTkScrollableFrame(self, label_text="Lịch sử tải xuống (Session)", label_font=ctk.CTkFont(weight="bold"))
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
        """Cập nhật dữ liệu dashboard và tải 10 phiên tải đầu tiên (Reset phân trang)."""
        stats = history.get_stats()
        
        self.card_sessions.configure(text=str(stats.get("sessions", 0)))
        self.card_videos.configure(text=str(stats.get("videos", 0)))
        self.card_bytes.configure(text=history.format_size(stats.get("bytes", 0)))
        self.card_duration.configure(text=history.format_duration(stats.get("duration", 0)))

        # Xóa tất cả widget con cũ
        for widget in self.scroll_history.winfo_children():
            widget.destroy()

        self.offset = 0
        self.btn_load_more = None
        self.load_more_history()

    def load_more_history(self):
        """Tải thêm 10 phiên tải tiếp theo bằng SQLite lazy loading."""
        # Ẩn nút "Xem thêm" cũ nếu có
        if self.btn_load_more:
            self.btn_load_more.destroy()
            self.btn_load_more = None

        history_list = history.load_history(limit=self.limit, offset=self.offset)
        if not history_list and self.offset == 0:
            lbl_empty = ctk.CTkLabel(self.scroll_history, text="Chưa có lịch sử phiên tải nào.", font=ctk.CTkFont(size=13))
            lbl_empty.pack(pady=20)
            return

        for idx, item in enumerate(history_list):
            session_frame = ctk.CTkFrame(self.scroll_history, fg_color="#21252b" if (self.offset + idx) % 2 == 0 else "#282c34", corner_radius=8)
            session_frame.pack(fill="x", expand=True, padx=5, pady=4)
            session_frame.grid_columnconfigure(0, weight=1)

            date_str = item.get("date", "Chưa rõ thời gian")
            url_count = item.get("url_count", 0)
            video_count = item.get("video_count", 0)
            duration_s = item.get("duration_seconds", 0)
            total_b = item.get("total_bytes", 0)
            session_dir = item.get("session_dir", "downloads")

            details = f"📅 {date_str}  |  📹 Đã tải: {video_count}/{url_count} video  |  💾 {history.format_size(total_b)}  |  ⏱️ Thời gian: {history.format_duration(duration_s)}"
            
            lbl_info = ctk.CTkLabel(session_frame, text=details, font=ctk.CTkFont(size=12), anchor="w")
            lbl_info.grid(row=0, column=0, padx=15, pady=(10, 2), sticky="w")

            lbl_path = ctk.CTkLabel(session_frame, text=f"📂 Thư mục: {session_dir}", font=ctk.CTkFont(size=10), text_color="#888", anchor="w")
            lbl_path.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="w")

            btn_open = ctk.CTkButton(
                session_frame, 
                text="📂 Mở thư mục", 
                width=110, 
                fg_color="#3a3f4b", 
                hover_color="#4b5263",
                command=lambda d=session_dir: self.app.open_session_folder(d)
            )
            btn_open.grid(row=0, column=1, rowspan=2, padx=15, pady=10, sticky="e")

        # Cập nhật chỉ số offset
        self.offset += len(history_list)

        # Nếu còn dữ liệu tiếp theo, hiển thị nút "Xem thêm..." ở dưới cùng
        if len(history_list) == self.limit:
            self.btn_load_more = ctk.CTkButton(
                self.scroll_history,
                text="➕ Xem thêm...",
                fg_color="#2c3e50",
                hover_color="#1a252f",
                command=self.load_more_history
            )
            self.btn_load_more.pack(pady=10)
