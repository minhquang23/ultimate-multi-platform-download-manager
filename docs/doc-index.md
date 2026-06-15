# Ultimate Download Manager v3.0 — Tài liệu Kiến trúc Hệ thống

Chào mừng bạn đến với hệ thống tài liệu mô-đun hóa của dự án **Ultimate Multi-Platform Download Manager**. Tài liệu này được xây dựng theo chuẩn **Modular Documentation Architecture (MDA)** giúp đồng bộ đặc tả dự án trực tiếp trong kho mã nguồn Git.

---

## 🗺️ Bản đồ Tài liệu (Document Map)

* **[docs/01.requirement.md](file:///d:/Projects/ultimate-multi-platform-download-manager/docs/01.requirement.md)**: 
  * Khởi nguồn ý tưởng, sứ mệnh, mục tiêu phát triển phiên bản v3.0.
  * Các tính năng nghiệp vụ chính (Chỉ tải Transcript, Tách tự động video ngắn, Xuất 2 bản transcript).
* **[docs/02.entities.md](file:///d:/Projects/ultimate-multi-platform-download-manager/docs/02.entities.md)**:
  * Đặc tả mô hình dữ liệu.
  * Thiết kế lược đồ cơ sở dữ liệu (SQLite DB Schema) và cấu hình Settings JSON.
* **[docs/03.workFlow.md](file:///d:/Projects/ultimate-multi-platform-download-manager/docs/03.workFlow.md)**:
  * Quy trình tải xuống và trích xuất.
  * Luồng vận hành đa tiến trình (Multiprocessing Architecture) & Giao tiếp Queue.
* **[docs/05.aiRules.md](file:///d:/Projects/ultimate-multi-platform-download-manager/docs/05.aiRules.md)**:
  * Quy tắc hoạt động của AI (Local Whisper vs Cloud API, Prompt nhận diện người nói cho Gemini).
  * Ma trận tự động phòng vệ (AI Priority Fallback Matrix).
* **[docs/06.techSpecs.md](file:///d:/Projects/ultimate-multi-platform-download-manager/docs/06.techSpecs.md)**:
  * Biên dịch và đóng gói PyInstaller trên Windows.
  * Cơ chế nâng cấp động yt-dlp qua Wheel zip extraction.

---

## 🛠️ Hướng dẫn Đọc tài liệu cho Lập trình viên mới
1. Đọc **[01.requirement.md](file:///d:/Projects/ultimate-multi-platform-download-manager/docs/01.requirement.md)** để nắm rõ bài toán nghiệp vụ.
2. Xem **[02.entities.md](file:///d:/Projects/ultimate-multi-platform-download-manager/docs/02.entities.md)** và **[03.workFlow.md](file:///d:/Projects/ultimate-multi-platform-download-manager/docs/03.workFlow.md)** để hiểu cấu trúc DB và luồng xử lý ngầm (Multiprocessing).
3. Tra cứu **[05.aiRules.md](file:///d:/Projects/ultimate-multi-platform-download-manager/docs/05.aiRules.md)** và **[06.techSpecs.md](file:///d:/Projects/ultimate-multi-platform-download-manager/docs/06.techSpecs.md)** khi cần sửa đổi/bảo trì lõi AI hoặc đóng gói xuất bản ứng dụng.
