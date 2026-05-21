import json
import os
import datetime

HISTORY_FILE = "download_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_session(session_dir, urls, video_count, total_bytes, duration_seconds):
    """Ghi một session tải vào lịch sử."""
    history = load_history()
    history.append({
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_dir": session_dir,
        "url_count": len(urls),
        "video_count": video_count,
        "total_bytes": total_bytes,
        "duration_seconds": round(duration_seconds, 1),
        "urls": urls,
    })
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Lỗi khi lưu lịch sử: {e}")

def get_stats():
    """Tổng hợp thống kê toàn bộ lịch sử."""
    history = load_history()
    total_videos = sum(s.get("video_count", 0) for s in history)
    total_bytes = sum(s.get("total_bytes", 0) for s in history)
    total_sessions = len(history)
    total_duration = sum(s.get("duration_seconds", 0) for s in history)
    return {
        "sessions": total_sessions,
        "videos": total_videos,
        "bytes": total_bytes,
        "duration": total_duration,
    }

def format_size(b):
    if b >= 1024**3:
        return f"{b/1024**3:.2f} GB"
    if b >= 1024**2:
        return f"{b/1024**2:.1f} MB"
    if b >= 1024:
        return f"{b/1024:.0f} KB"
    return f"{b} B"

def format_duration(s):
    if s < 60:
        return f"{s:.0f}s"
    if s < 3600:
        return f"{s/60:.1f} phút"
    return f"{s/3600:.1f} giờ"
