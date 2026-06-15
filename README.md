# Ultimate Multi-Platform Download Manager (v3.0)

Đây là công cụ tải và xử lý video đa nền tảng mạnh mẽ, được tích hợp trí tuệ nhân tạo (AI) giúp bạn không chỉ tải video chất lượng cao mà còn tự động trích xuất phụ đề và nhận diện người nói (Speaker Diarization) cực kỳ thông minh. 

Phiên bản **v3.0** mang đến những nâng cấp mang tính đột phá về **Tối ưu hóa tài nguyên**, **Trí tuệ tự động hóa** và **Trải nghiệm người dùng (UI/UX)** đỉnh cao.

---

## 🌟 Các tính năng nổi bật

### 1. Tải Video Đa Nền Tảng & Trích xuất Phụ đề
- Hỗ trợ tải video, âm thanh chất lượng cao từ YouTube, Facebook, TikTok, Vimeo, Instagram... thông qua `yt-dlp`.
- Tự động lấy phụ đề có sẵn (VTT) từ YouTube hoặc tự động tạo phụ đề bằng **Whisper AI** offline nếu video không có sub gốc.

### 2. Chế độ Tải tối ưu "Chỉ lấy Transcript" (Không lưu Video) 📝 [MỚI]
- Dành cho những ai chỉ cần văn bản kịch bản/phụ đề để làm content, không muốn lưu tệp video nặng.
- **Tải luồng âm thanh siêu nhẹ**: Phần mềm tự động cấu hình tải luồng âm thanh cực nhẹ định dạng `.m4a` (chỉ nặng **5% - 10%** so với video 1080p gốc), tiết kiệm tới 95% băng thông mạng.
- **Tự động dọn dẹp (Auto-cleanup)**: Ngay sau khi Whisper dịch xong và ghi file transcript `.txt`, hệ thống lập tức **xóa sạch tệp âm thanh tạm thời** khỏi ổ cứng, đảm bảo bộ nhớ máy tính hoàn toàn sạch sẽ.

### 3. Tự động Phân loại & Tối ưu hóa Video Ngắn (Shorts, TikTok, Reels, Stories) 🧠 [MỚI]
- Hệ thống tự nhận diện các video ngắn (thuộc nền tảng `youtube_shorts`, `tiktok`, `instagram`, các liên kết `/reels/`, `/stories/` trên Facebook, hoặc bất kỳ video nào dưới **3 phút**).
- **Tự động bỏ qua Speaker Diarization để tiết kiệm hạn ngạch API**: Đối với các video ngắn (thường chỉ 1 người nói/đọc script nhanh), hệ thống tự động tắt Diarization của Gemini để **bảo toàn 100% hạn ngạch API** cho bạn và tăng tốc độ xử lý nhanh gấp **5 lần**!
- Đối với video dài (Bài giảng, webinar, replay khóa học): Giữ nguyên tính năng phân tách người nói đầy đủ.

### 4. Xuất song song 2 Định dạng Transcript (Dual-Output Mode) 📄 [MỚI]
Hệ thống tự động xuất đồng thời **2 tệp văn bản** vào thư mục `downloads/txt_convert/`:
- **Tệp Gốc Timeline (`[Tên].txt` / `_whisper_transcript.txt`)**: Giữ nguyên mốc thời gian dạng `00:00:10 --> 00:00:15` để đối chiếu ghép sub trong Premiere/CapCut.
- **Tệp Sạch Content (`[Tên]_clean.txt` / `_whisper_transcript_clean.txt`)**: Loại bỏ hoàn toàn mốc thời gian, tự động ghép tất cả các câu thoại thành một đoạn văn viết liền mạch trôi chảy, sẵn sàng copy-paste làm nguyên liệu cho ChatGPT/Gemini viết bài.

### 5. Ma trận AI Fallback ưu tiên (AI Priority Matrix) 🛡️ [MỚI]
- Hỗ trợ giao diện **Kéo & Thả (Drag & Drop)** trực quan để sắp xếp thứ tự ưu tiên các mô hình AI (như GPT-5, Gemini, DeepSeek...).
- **Cơ chế tự động phòng vệ (Fallback)**: Khi tiến trình Diarization gặp lỗi với một mô hình (ví dụ: API Key bị khóa 401, tài khoản hết tiền 402), hệ thống sẽ **ngay lập tức tự chuyển hướng** sang mô hình tiếp theo trong danh sách ưu tiên, giúp tiến trình xử lý hàng loạt diễn ra liên tục không bao giờ bị dừng giữa chừng.

---

## 🎨 Trải nghiệm giao diện mới (UI/UX Upgrade)

* **Thanh điều khiển trung tâm đặt tại Tab Tải về**: 
  - Dropdown **"Chế độ tải xuống"** đặt trực tiếp tại Tab Tải về để bạn nhanh chóng đổi chế độ tải video hoặc chỉ lấy transcript ngay tại màn hình chính trước khi bấm xử lý.
* **Nút mở nhanh kết quả tối giản `📂`**: 
  - Thiết kế dạng nút hình vuông chỉ chứa duy nhất icon `📂` cực kỳ thanh thoát. 
  - Nút sẽ tự động **sáng xanh lá nổi bật** (`fg_color="#2ca02c"`) ngay khi tiến trình hoàn tất để báo hiệu dữ liệu đã sẵn sàng. Click vào nút sẽ mở trực tiếp thư mục Explorer chứa các file transcript của phiên tải đó.
* **Đường kẻ phân cách (Dividers) & Khung cuộn thông minh**: Giúp quản lý danh sách tải hàng trăm video mượt mà, trực quan.

---

## 💻 Yêu cầu hệ thống

- **Hệ điều hành:** Windows 10/11, macOS, hoặc Linux.
- **Python:** Phiên bản `3.10` trở lên.
- **FFmpeg:** Cần được cài đặt sẵn trên máy và thêm vào biến môi trường (PATH) để Whisper hoạt động.

---

## 🚀 Hướng dẫn cài đặt

**Bước 1: Clone mã nguồn về máy**
```bash
git clone https://github.com/minhquang23/ultimate-multi-platform-download-manager.git
cd ultimate-multi-platform-download-manager
```

**Bước 2: Tạo môi trường ảo (Khuyên dùng)**
```bash
python -m venv .venv
# Kích hoạt môi trường (Windows):
.venv\Scripts\activate
# Kích hoạt môi trường (macOS/Linux):
source .venv/bin/activate
```

**Bước 3: Chạy cài đặt tự động (Quét phần cứng thông minh)**
*Chỉ dành cho Windows (Khuyên dùng):*
Chạy file script tự động quét phần cứng. Nếu máy có GPU NVIDIA Card rời, nó sẽ tự cài PyTorch CUDA để Whisper chạy nhanh gấp 20 lần; nếu không có, nó tự cài bản CPU và hỗ trợ tải trước model Whisper về máy:
```powershell
powershell -ExecutionPolicy Bypass -File .\setup_local.ps1
```

*Cài đặt thủ công (macOS/Linux/CPU):*
```bash
pip install -r requirements.txt
```

---

## ⚙️ Thiết lập cấu hình và Chạy ứng dụng

1. **Khởi động ứng dụng:**
   ```bash
   python app.py
   ```
2. **Thiết lập Nhận diện người nói (AI):**
   - Vào tab **Dev Mode** (mật khẩu mặc định: `minhhq`).
   - Sắp xếp thứ tự ưu tiên các mô hình AI bạn muốn sử dụng (Gemini, GPT, DeepSeek...).
   - Điền API Key tương ứng cho mô hình (ví dụ: [Google AI Studio](https://aistudio.google.com/app/apikey) cho Gemini).
   - Bấm **Lưu ma trận cấu hình**.
3. **Chạy tải:**
   - Chuyển về tab **Tải về**, dán link video, nhấn quét.
   - Chọn chế độ tải (Tải kèm Video hoặc Chỉ tải Transcript) trực tiếp trên dropdown.
   - Nhấn **Bắt đầu xử lý**.
   - Khi hoàn thành, nút **`📂`** sẽ sáng xanh lá, click vào đó để lấy kịch bản!

---

## 💡 Lưu ý về Whisper AI
Nếu máy bạn không có Card đồ họa NVIDIA rời (chạy Whisper bằng CPU), hãy vào mục **⚙️ Cài đặt** chọn các model Whisper cỡ nhỏ như `tiny` hoặc `base` để giảm tải hệ thống và tăng tốc độ xử lý nhanh nhất.