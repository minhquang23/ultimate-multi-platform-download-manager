import sqlite3
import os
import json
import datetime

DB_FILE = "download_history.db"
JSON_FILE = "download_history.json"

def _init_db():
    """Khởi tạo database SQLite và tự động migrate dữ liệu cũ từ JSON nếu có."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Tạo bảng sessions nếu chưa có
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            session_dir TEXT,
            url_count INTEGER,
            video_count INTEGER,
            total_bytes INTEGER,
            duration_seconds REAL,
            urls TEXT
        )
    """)
    conn.commit()
    
    # Kiểm tra migration từ JSON cũ
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                history_data = json.load(f)
                
            if isinstance(history_data, list):
                for item in history_data:
                    date_val = item.get("date", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    session_dir = item.get("session_dir", "")
                    url_count = item.get("url_count", 0)
                    video_count = item.get("video_count", 0)
                    total_bytes = item.get("total_bytes", 0)
                    duration_seconds = item.get("duration_seconds", 0.0)
                    urls_list = item.get("urls", [])
                    urls_json = json.dumps(urls_list, ensure_ascii=False)
                    
                    cursor.execute("""
                        INSERT INTO sessions (date, session_dir, url_count, video_count, total_bytes, duration_seconds, urls)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (date_val, session_dir, url_count, video_count, total_bytes, duration_seconds, urls_json))
                conn.commit()
            
            # Đổi tên tệp cũ để lưu làm backup, tránh migrate lại lần sau
            backup_file = JSON_FILE + ".bak"
            if os.path.exists(backup_file):
                os.remove(backup_file)
            os.rename(JSON_FILE, backup_file)
            print(f"🎉 Đã chuyển đổi dữ liệu từ {JSON_FILE} sang SQLite thành công. Đã backup tệp cũ thành {backup_file}.")
        except Exception as e:
            print(f"Lỗi khi di chuyển dữ liệu JSON sang SQLite: {e}")
            
    conn.close()

# Tự động khởi chạy khi import module này
_init_db()

def load_history(limit=None, offset=None):
    """
    Tải lịch sử tải về từ SQLite.
    Hỗ trợ limit và offset để lazy loading (phân trang) trên UI.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM sessions ORDER BY date DESC"
    params = []
    
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)
            
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    history = []
    for r in rows:
        try:
            urls_list = json.loads(r["urls"])
        except Exception:
            urls_list = []
            
        history.append({
            "id": r["id"],
            "date": r["date"],
            "session_dir": r["session_dir"],
            "url_count": r["url_count"],
            "video_count": r["video_count"],
            "total_bytes": r["total_bytes"],
            "duration_seconds": r["duration_seconds"],
            "urls": urls_list
        })
        
    conn.close()
    return history

def save_session(session_dir, urls, video_count, total_bytes, duration_seconds):
    """Ghi một session tải vào lịch sử SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    date_val = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    urls_json = json.dumps(urls, ensure_ascii=False)
    
    try:
        cursor.execute("""
            INSERT INTO sessions (date, session_dir, url_count, video_count, total_bytes, duration_seconds, urls)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (date_val, session_dir, len(urls), video_count, total_bytes, round(duration_seconds, 1), urls_json))
        conn.commit()
    except Exception as e:
        print(f"Lỗi khi lưu lịch sử SQLite: {e}")
    finally:
        conn.close()

def get_stats():
    """Tổng hợp thống kê toàn bộ lịch sử sử dụng SQL."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                COUNT(*), 
                SUM(video_count), 
                SUM(total_bytes), 
                SUM(duration_seconds) 
            FROM sessions
        """)
        row = cursor.fetchone()
        
        total_sessions = row[0] or 0
        total_videos = row[1] or 0
        total_bytes = row[2] or 0
        total_duration = row[3] or 0.0
        
        return {
            "sessions": total_sessions,
            "videos": total_videos,
            "bytes": total_bytes,
            "duration": total_duration,
        }
    except Exception as e:
        print(f"Lỗi khi lấy thống kê lịch sử: {e}")
        return {
            "sessions": 0,
            "videos": 0,
            "bytes": 0,
            "duration": 0.0,
        }
    finally:
        conn.close()

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
