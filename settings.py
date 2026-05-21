import json
import os

SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    # --- Cookie & Anti-Bot ---
    "delay_min": 3.0,
    "delay_max": 5.0,
    "browser": "chrome",

    # --- Download ---
    "video_quality": "1080p",
    "subtitle_lang": "vi",
    "download_video": True,

    # --- Whisper AI ---
    # model: tiny / base / small / medium / large / large-v3
    # Local machine: khuyến nghị "medium" (CUDA GTX 950) hoặc "large-v3" (CPU, cần 16GB RAM)
    # Installer / Portable: "small" (480MB, cân bằng tốt)
    "whisper_model": "medium",
    # device: "auto" | "cuda" | "cpu"
    "whisper_device": "auto",
    # transcript_mode: "prefer_subtitle" = dùng sub YouTube gốc nếu có, Whisper chỉ cho TikTok/Reels...
    #                  "always_whisper"  = luôn dùng Whisper AI kể cả với YouTube
    "transcript_mode": "prefer_subtitle",
    # Thư mục lưu Whisper models (tương đối theo thư mục app — quan trọng với bản Portable)
    "whisper_model_dir": "models/whisper",

    # --- Speaker Diarization (LLM) ---
    "enable_speaker_diarization": False,
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Merge với default để đảm bảo đủ key khi thêm key mới sau này
                merged = DEFAULT_SETTINGS.copy()
                merged.update(data)
                return merged
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()

def save_settings(settings: dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Lỗi khi lưu cài đặt: {e}")
