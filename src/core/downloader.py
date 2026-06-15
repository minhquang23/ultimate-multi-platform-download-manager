import os
import sys
import shutil
import subprocess
import urllib.parse
import yt_dlp
from src.services.title_cleaner import clean_video_title, detect_platform

def get_ffmpeg_path():
    """Lấy đường dẫn đến ffmpeg binary."""
    # Thử từ imageio_ffmpeg
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.exists(path):
            return path
    except ImportError:
        pass

    # Thử hệ thống PATH
    ffmpeg_sys = shutil.which("ffmpeg")
    if ffmpeg_sys:
        return ffmpeg_sys

    return None

def ensure_ffmpeg_in_path():
    """Đảm bảo thư mục chứa ffmpeg được thêm vào PATH môi trường."""
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path:
        ffmpeg_dir = os.path.dirname(ffmpeg_path)
        if ffmpeg_dir not in os.environ['PATH']:
            os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ['PATH']
        return True
    return False

def guess_language_from_title(title):
    """Đoán mã ngôn ngữ từ tiêu đề video."""
    title = title.lower()
    if 'tiếng việt' in title or 'vietnamese' in title:
        return 'vi'
    if 'tiếng anh' in title or 'english' in title:
        return 'en'
    if 'tiếng trung' in title or 'chinese' in title:
        return 'zh'
    if 'tiếng nhật' in title or 'japanese' in title:
        return 'ja'
    if 'tiếng hàn' in title or 'korean' in title:
        return 'ko'
    if 'tiếng pháp' in title or 'french' in title:
        return 'fr'
    if 'tiếng nga' in title or 'russian' in title:
        return 'ru'
    if 'tiếng tây ban nha' in title or 'spanish' in title:
        return 'es'
    return None

def fetch_video_list(urls, browser='chrome', log_callback=None):
    """
    Quét danh sách URL để lấy thông tin các video.
    Hỗ trợ YouTube, YouTube Shorts, TikTok, Facebook Reels/Story, Vimeo, Instagram.
    """
    ydl_opts = {
        'extract_flat': 'in_playlist',
        'noplaylist': False,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'js_runtimes': {'node': {}},
        'remote_components': {'ejs:github'},
    }

    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"
    elif browser and browser != "Không dùng":
        ydl_opts['cookiesfrombrowser'] = (browser.lower(), )

    results = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for url in urls:
                url = url.strip()
                if not url:
                    continue

                # Xử lý tệp máy tính (Local file)
                is_local = False
                local_path = url
                if url.startswith("file:///"):
                    local_path = urllib.parse.unquote(url[8:])
                    is_local = True
                elif os.path.exists(url):
                    is_local = True

                if is_local and os.path.exists(local_path):
                    filename = os.path.basename(local_path)
                    results.append({
                        'url': local_path,
                        'title': filename,
                        'is_main': True,
                        'id': filename,
                        'platform': 'local',
                        'is_local': True,
                        'has_subtitles': False
                    })
                    continue

                platform = detect_platform(url)

                try:
                    if platform in ["youtube", "youtube_shorts"]:
                        parsed = urllib.parse.urlparse(url)
                        qs = urllib.parse.parse_qs(parsed.query)
                        main_v_id = qs.get('v', [None])[0]

                        info = ydl.extract_info(url, download=False)
                        if not info:
                            results.append({'url': url, 'title': f"YouTube Video", 'is_main': True, 'id': '', 'platform': platform})
                            continue

                        entries = info.get('entries')
                        if entries is None:
                            entries = [info]
                        else:
                            entries = list(entries)

                        for entry in entries:
                            if not entry:
                                                    continue
                            v_id = entry.get('id', '')
                            title = clean_video_title(entry.get('title', 'Unknown Title'))
                            v_url = entry.get('webpage_url') or (f"https://www.youtube.com/watch?v={v_id}" if v_id else url)
                            is_main = (main_v_id and v_id == main_v_id) or len(entries) == 1
                            
                            has_subs = bool(entry.get('subtitles') or entry.get('automatic_captions'))
                            detected_lang = entry.get('language') or info.get('language') or guess_language_from_title(title)

                            duration = entry.get('duration') or info.get('duration')
                            results.append({
                                'url': v_url, 
                                'title': title, 
                                'is_main': is_main, 
                                'id': v_id, 
                                'platform': platform,
                                'language': detected_lang,
                                'duration': duration,
                                'has_subtitles': has_subs,
                                'is_local': False
                            })

                    else:
                        ydl_fast_opts = {**ydl_opts, 'process': False}
                        with yt_dlp.YoutubeDL(ydl_fast_opts) as ydl_fast:
                            info = ydl_fast.extract_info(url, download=False)
                            title = "Unknown Video"
                            v_id = "unknown"
                            if info:
                                raw_title = info.get('title') or info.get('description') or f"{platform.capitalize()} Video"
                                title = clean_video_title(raw_title)
                                v_id = info.get('id') or "video"
                                if len(title) > 80:
                                    title = title[:77] + "..."

                            duration = info.get('duration') if info else None
                            results.append({
                                'url': url, 
                                'title': title, 
                                'is_main': True, 
                                'id': v_id, 
                                'platform': platform,
                                'language': guess_language_from_title(title),
                                'duration': duration,
                                'has_subtitles': bool(info.get('subtitles') or info.get('automatic_captions')) if info else False,
                                'is_local': False
                            })

                except Exception as e:
                    err_msg = str(e)
                    print(f"Lỗi quét URL {url}: {err_msg}")
                    if log_callback:
                        if "cookie" in err_msg.lower():
                            log_callback(
                                f"❌ LỖI COOKIES KHI QUÉT URL: {url}\n"
                                f"   Chi tiết: {err_msg}\n"
                                f"   👉 NGUYÊN NHÂN: Trình duyệt '{browser}' có thể đang mở và khóa tệp cookie.\n"
                                f"   👉 CÁCH KHẮC PHỤC:\n"
                                f"      1. Tắt HOÀN TOÀN trình duyệt '{browser}' (đảm bảo không còn chạy ngầm trong Task Manager) rồi quét lại.\n"
                                f"      2. Hoặc vào tab '⚙️ Cài đặt' -> Chọn 'Không dùng' ở mục 'Đọc Cookies từ trình duyệt' (nếu không cần tải video riêng tư/giới hạn).\n"
                                f"      3. Hoặc xuất tệp 'cookies.txt' từ trình duyệt bằng tiện ích mở rộng (như 'Get cookies.txt LOCALLY') rồi lưu vào thư mục phần mềm."
                            )
                        else:
                            log_callback(f"❌ Lỗi quét URL {url}: {err_msg}")
                    
                    results.append({
                        'url': url,
                        'title': f"[{platform.upper()}] {url[:40]}...",
                        'is_main': True,
                        'id': 'error_fallback',
                        'platform': platform
                    })
    except Exception as outer_e:
        outer_err = str(outer_e)
        print(f"Lỗi khởi tạo yt-dlp: {outer_err}")
        if log_callback:
            if "cookie" in outer_err.lower():
                log_callback(
                    f"❌ LỖI CẤU HÌNH COOKIES:\n"
                    f"   Chi tiết: {outer_err}\n"
                    f"   👉 NGUYÊN NHÂN: Trình duyệt '{browser}' có thể đang mở và khóa tệp cookie.\n"
                    f"   👉 CÁCH KHẮC PHỤC:\n"
                    f"      1. Tắt HOÀN TOÀN trình duyệt '{browser}' (đảm bảo không còn chạy ngầm trong Task Manager).\n"
                    f"      2. Hoặc vào tab '⚙️ Cài đặt' -> Chọn 'Không dùng' ở mục 'Đọc Cookies từ trình duyệt' (nếu không cần tải video riêng tư/giới hạn).\n"
                    f"      3. Hoặc xuất tệp 'cookies.txt' từ trình duyệt bằng tiện ích mở rộng (như 'Get cookies.txt LOCALLY') rồi lưu vào thư mục phần mềm."
                )
            else:
                log_callback(f"❌ Lỗi khởi tạo yt-dlp: {outer_err}")

    return results

def check_and_update_ytdlp(log_callback=None):
    """
    Kiểm tra và tự động nâng cấp yt-dlp từ GitHub (cho bản .exe) hoặc qua pip (cho bản development).
    """
    if log_callback:
        log_callback("🔄 Đang kiểm tra cập nhật cho công cụ tải yt-dlp...")
        
    try:
        # Nếu chạy trực tiếp bằng Python
        if not getattr(sys, 'frozen', False):
            if log_callback:
                log_callback("💡 Đang nâng cấp yt-dlp qua pip...")
            res = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], capture_output=True, text=True)
            if res.returncode == 0:
                if log_callback:
                    log_callback("✅ Nâng cấp yt-dlp thành công qua pip!")
                return True
            else:
                if log_callback:
                    log_callback(f"❌ Lỗi nâng cấp yt-dlp qua pip: {res.stderr}")
                return False
        
        # Nếu chạy bản .exe đóng gói, chúng ta sẽ tải thư viện zip/wheel mới từ PyPI
        # và trích xuất vào updates/yt-dlp
        import requests
        import zipfile
        import io
        
        # API lấy bản phát hành mới nhất từ PyPI
        pypi_url = "https://pypi.org/pypi/yt-dlp/json"
        resp = requests.get(pypi_url, timeout=10)
        if resp.status_code != 200:
            if log_callback:
                log_callback("❌ Không thể kiểm tra phiên bản mới của yt-dlp trên PyPI.")
            return False
            
        data = resp.json()
        latest_version = data["info"]["version"]
        current_version = yt_dlp.version.__version__
        
        if log_callback:
            log_callback(f"💡 Phiên bản yt-dlp hiện tại: {current_version} | Bản mới nhất: {latest_version}")
            
        if latest_version == current_version:
            if log_callback:
                log_callback("✅ yt-dlp đã ở phiên bản mới nhất.")
            return True
            
        # Tìm tệp Wheel hoặc Source Zip để tải về
        url_to_download = None
        for release in data["urls"]:
            if release["packagetype"] == "bdist_wheel": # wheel (.whl) thực chất là file zip
                url_to_download = release["url"]
                break
                
        if not url_to_download:
            if log_callback:
                log_callback("❌ Không tìm thấy tệp thích hợp để tải.")
            return False
            
        if log_callback:
            log_callback("📥 Đang tải bản cập nhật yt-dlp mới nhất từ PyPI...")
            
        r = requests.get(url_to_download, timeout=30)
        if r.status_code == 200:
            update_dir = os.path.abspath("updates")
            ytdlp_update_dir = os.path.join(update_dir, "yt-dlp_lib")
            
            # Xóa thư mục cũ nếu có
            if os.path.exists(ytdlp_update_dir):
                shutil.rmtree(ytdlp_update_dir)
            os.makedirs(ytdlp_update_dir, exist_ok=True)
            
            # Giải nén
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                # Chỉ giải nén thư mục yt_dlp bên trong wheel
                for name in z.namelist():
                    if name.startswith("yt_dlp/"):
                        z.extract(name, ytdlp_update_dir)
            
            # Lưu cấu hình chỉ định đã cập nhật
            if log_callback:
                log_callback("✅ Cập nhật yt-dlp thành công! Vui lòng khởi động lại ứng dụng để áp dụng bản mới.")
            return True
            
    except Exception as e:
        if log_callback:
            log_callback(f"❌ Lỗi trong quá trình tự động cập nhật: {e}")
    return False

def apply_ytdlp_update():
    """
    Hàm này sẽ được gọi ở đầu run.py để ưu tiên import yt-dlp đã cập nhật
    trong thư mục updates/yt-dlp_lib nếu có.
    """
    update_path = os.path.abspath("updates/yt-dlp_lib")
    if os.path.exists(update_path):
        # Thêm thư mục chứa gói yt_dlp đã giải nén vào sys.path
        if update_path not in sys.path:
            sys.path.insert(0, update_path)
