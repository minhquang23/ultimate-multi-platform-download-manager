# Ultimate Multi-Platform Download Manager (HiveTech Tool)

Đây là công cụ tải và xử lý video đa nền tảng mạnh mẽ, được tích hợp trí tuệ nhân tạo (AI) giúp bạn không chỉ tải video chất lượng cao mà còn tự động trích xuất phụ đề và nhận diện người nói (Speaker Diarization) cực kỳ thông minh.

## 🌟 Các tính năng hiện có

- **Tải Video Đa Nền Tảng:** Hỗ trợ tải video, âm thanh (mp4, m4a) chất lượng cao từ YouTube và nhiều nền tảng khác thông qua `yt-dlp`.
- **Trích xuất & Chuẩn hóa Phụ đề:** Tự động lấy phụ đề có sẵn (VTT) hoặc tạo mới và chuẩn hóa thành định dạng text dễ đọc.
- **Nhận diện Người Nói (Hybrid AI - Model C):** 
  - Kết hợp bộ lọc Heuristics (nhận diện qua lời chào, giới thiệu) và Sức mạnh của LLM (**Gemini 2.5 Flash**).
  - Tự động phân đoạn và gán tên người nói chi tiết cho từng câu trong file phụ đề.
  - Cơ chế dự phòng (Fallback) an toàn cùng giới hạn tốc độ chuẩn giúp hạn chế tối đa lỗi API.
- **Giao diện Trực quan:** Thiết kế bằng giao diện đồ họa hiện đại (CustomTkinter), hỗ trợ theo dõi tiến độ % theo thời gian thực (Progress Bar).
- **Quản lý Cấu hình Tập trung:** Lưu trữ lịch sử tải về, trạng thái UI và các khóa API một cách an toàn.

## 💻 Yêu cầu hệ thống

- **Hệ điều hành:** Windows 10/11, macOS, hoặc Linux.
- **Python:** Phiên bản `3.10` trở lên.
- **FFmpeg:** Cần được cài đặt sẵn trên máy và thêm vào biến môi trường (PATH) để xử lý âm thanh/video.

## 🚀 Hướng dẫn cài đặt

**Bước 1: Clone mã nguồn về máy**
```bash
git clone https://github.com/minhquang23/ultimate-multi-platform-download-manager.git
cd ultimate-multi-platform-download-manager
```

**Bước 2: (Tùy chọn) Tạo môi trường ảo**
```bash
python -m venv .venv
# Kích hoạt môi trường (Windows):
.venv\Scripts\activate
# Kích hoạt môi trường (macOS/Linux):
source .venv/bin/activate
```

**Bước 3: Cài đặt các thư viện cần thiết**
```bash
pip install -r requirements.txt
```

## ⚙️ Thiết lập cấu hình và Chạy ứng dụng

1. **Khởi động ứng dụng:**
   ```bash
   python app.py
   ```
2. **Thiết lập tính năng Nhận diện người nói (AI):**
   - Chuyển sang Tab **Cài đặt** trên giao diện ứng dụng.
   - Đánh dấu tích vào ô **"Bật Model C (Nhận diện Người nói bằng AI)"**.
   - Truy cập [Google AI Studio](https://aistudio.google.com/app/apikey) để lấy một **API Key miễn phí**.
   - Dán API Key vào ô nhập liệu **Gemini API Key**.
   - Bấm **Lưu Tất Cả Cấu Hình**.
3. **Sử dụng:**
   - Chuyển về Tab **Tải về**.
   - Dán link video cần tải, nhấn **Quét Link** và sau đó **Bắt đầu tải**.
   - Kết quả sẽ được lưu tự động trong thư mục `downloads/`, trong đó thư mục `txt_speaker/` sẽ chứa các file kịch bản đã được phân rõ người nói!

## 💡 Lưu ý về Hiệu năng (Dành cho máy không có Card rời)
- **Tính năng Whisper AI (Tạo phụ đề tự động):** Nếu máy bạn không có Card đồ họa (GPU) hoặc VRAM thấp, ứng dụng sẽ tự động nhận diện và chuyển sang xử lý bằng CPU. Bạn nên vào mục Cài đặt và chọn model Whisper là `tiny` hoặc `base` để giảm tải cho máy và tăng tốc độ xử lý.
- **Nhận diện Người Nói (Model C):** Hoàn toàn sử dụng Cloud API của Google nên không yêu cầu phần cứng máy tính cao. Mọi máy tính (kể cả laptop văn phòng) đều có thể chạy mượt mà tính năng này.