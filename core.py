import os
import glob
import webvtt
import yt_dlp
import urllib.parse
import time
import random
import shutil
import speaker_diarization
import sys
import re

# Thêm thư mục hiện tại vào PATH để yt-dlp có thể tìm thấy node.exe (nếu có) để giải mã YouTube
os.environ['PATH'] = os.path.abspath('.') + os.pathsep + os.environ['PATH']

# ---------------------------------------------------------------------------
# Tiện ích: Phát hiện nền tảng
# ---------------------------------------------------------------------------

def detect_platform(url):
    """Nhận diện nền tảng từ URL."""
    url_lower = url.lower()
    if "youtube.com/shorts/" in url_lower or "youtu.be/shorts/" in url_lower:
        return "youtube_shorts"
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    elif "tiktok.com" in url_lower:
        return "tiktok"
    elif "facebook.com" in url_lower or "fb.watch" in url_lower or "fb.com" in url_lower:
        return "facebook"
    elif "vimeo.com" in url_lower:
        return "vimeo"
    elif "instagram.com" in url_lower:
        return "instagram"
    else:
        return "generic"

# ---------------------------------------------------------------------------
# Tiện ích: ffmpeg & Timestamp
# ---------------------------------------------------------------------------

def get_ffmpeg_path():
    """
    Tìm ffmpeg theo thứ tự ưu tiên:
    1. Thư mục 'ffmpeg/' kế cạnh app (dùng cho Installer & Portable)
    2. imageio-ffmpeg (nếu được cài qua pip)
    3. ffmpeg trong PATH hệ thống
    Trả về đường dẫn đến ffmpeg.exe hoặc None nếu không tìm thấy.
    """
    # 1. Bundle trong thư mục app (Installer / Portable)
    app_dir = os.path.dirname(os.path.abspath(__file__))
    bundled = os.path.join(app_dir, 'ffmpeg', 'ffmpeg.exe')
    if os.path.exists(bundled):
        return bundled

    # 2. imageio-ffmpeg (cài qua pip, tiện lợi cho Local)
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.exists(path):
            return path
    except ImportError:
        pass

    # 3. ffmpeg trong PATH hệ thống
    path = shutil.which('ffmpeg')
    if path:
        return path

    return None

def ensure_ffmpeg_in_path():
    """Đảm bảo thư mục chứa ffmpeg có trong PATH để Whisper có thể gọi được."""
    ffmpeg_exe = get_ffmpeg_path()
    if ffmpeg_exe:
        ffmpeg_dir = os.path.dirname(ffmpeg_exe)
        
        # Sửa lỗi WinError 2: Nếu file thực thi không có tên 'ffmpeg.exe' (từ imageio_ffmpeg)
        # thì lệnh 'ffmpeg' của Whisper sẽ không tìm thấy. Ta copy thành 'ffmpeg.exe'
        ffmpeg_basename = os.path.basename(ffmpeg_exe).lower()
        if ffmpeg_basename != 'ffmpeg.exe' and ffmpeg_basename != 'ffmpeg':
            target_exe = os.path.join(ffmpeg_dir, 'ffmpeg.exe')
            if not os.path.exists(target_exe):
                try:
                    import shutil
                    shutil.copy2(ffmpeg_exe, target_exe)
                except Exception:
                    pass
                    
        if ffmpeg_dir not in os.environ['PATH']:
            os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ['PATH']
        return True
    return False

def seconds_to_timestamp(seconds):
    """Chuyển giây (float) sang định dạng HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

# ---------------------------------------------------------------------------
# Tiện ích: Xử lý phụ đề VTT → TXT (YouTube)
# ---------------------------------------------------------------------------

def convert_vtt_to_txt(vtt_file_path, txt_dir):
    """
    Đọc file .vtt và chuyển nội dung ra file .txt.
    - Khử trùng lặp các dòng cuộn (rolling subtitles).
    - Dọn dẹp thẻ <c> và chuyển timestamp về định dạng giây.
    - Ưu tiên phụ đề tự chèn (manual) — đã được yt-dlp tải ưu tiên.
    """
    if not os.path.exists(vtt_file_path):
        return None

    base_name = os.path.basename(vtt_file_path)
    txt_name = (base_name[:-4] if base_name.endswith('.vtt') else base_name) + '.txt'
    txt_file_path = os.path.join(txt_dir, txt_name)

    try:
        vtt = webvtt.read(vtt_file_path)
        clean_blocks = []
        seen_lines = []

        for caption in vtt:
            lines = caption.text.split('\n')
            block_output = []

            for line in lines:
                if not line.strip():
                    continue
                # Bỏ qua dòng đang "gõ" (chứa thẻ <c>)
                if '<c>' in line or '</c>' in line:
                    continue
                clean_text = line.strip()
                if not clean_text:
                    continue
                # Khử trùng lặp (rolling subtitles)
                is_duplicate = any(clean_text == seen for seen in seen_lines[-5:])
                if is_duplicate:
                    continue
                seen_lines.append(clean_text)
                block_output.append(clean_text)

            if block_output:
                clean_blocks.append({
                    'start_vtt': caption.start,
                    'end_vtt': caption.end,
                    'start_txt': caption.start.split('.')[0],
                    'end_txt': caption.end.split('.')[0],
                    'text': "\n".join(block_output)
                })

        # Ghi file TXT
        with open(txt_file_path, 'w', encoding='utf-8') as f_txt:
            for b in clean_blocks:
                f_txt.write(f"{b['start_txt']} --> {b['end_txt']}\n")
                f_txt.write(b['text'] + "\n\n")

        # Ghi đè VTT gốc (dạng sạch, dùng cho Premiere/trình phát)
        with open(vtt_file_path, 'w', encoding='utf-8') as f_vtt:
            f_vtt.write("WEBVTT\n\n")
            for b in clean_blocks:
                f_vtt.write(f"{b['start_vtt']} --> {b['end_vtt']}\n")
                f_vtt.write(b['text'] + "\n\n")

        return txt_file_path
    except Exception as e:
        print(f"Lỗi convert VTT: {vtt_file_path}: {e}")
        return None

# ---------------------------------------------------------------------------
# Whisper AI: Transcribe từ file video/audio
# ---------------------------------------------------------------------------

class CancelException(Exception):
    pass

class TqdmInterceptor:
    """Intercepts sys.stderr to parse Whisper's tqdm output and send it to GUI."""
    def __init__(self, callback, original_stderr, log_callback=None, cancel_event=None):
        self.callback = callback
        self.original_stderr = original_stderr
        self.log_callback = log_callback
        self.cancel_event = cancel_event
        # Regex matches tqdm string, e.g. "58%|███   | 53900/92512 [09:20<07:01, 91.65frames/s]"
        self.pattern = re.compile(r'(\d+)%\|.*\|\s*(\d+/\d+)\s*\[(.*?)\]')

    def write(self, s):
        if self.cancel_event and self.cancel_event.is_set():
            raise CancelException("Tiến trình đã bị hủy bởi người dùng.")

        # Always output to original stderr to ensure terminal behaves normally
        self.original_stderr.write(s)
        
        if "%|" in s:
            match = self.pattern.search(s)
            if match and self.callback:
                percent_str = match.group(1)
                progress_stats = match.group(2) + " [" + match.group(3) + "]"
                try:
                    percent = float(percent_str)
                    self.callback(percent, progress_stats)
                except ValueError:
                    pass
        elif "Detected language:" in s:
            if self.log_callback:
                self.log_callback("[Whisper] ✅ " + s.strip())

    def flush(self):
        self.original_stderr.flush()

def check_whisper_available():
    """Kiểm tra xem openai-whisper đã được cài chưa."""
    try:
        import whisper
        return True
    except ImportError:
        return False

def get_available_whisper_models(model_dir='models/whisper'):
    """Trả về list tên các model Whisper đã được tải về máy."""
    known_files = {
        'tiny':     'tiny.pt',
        'base':     'base.pt',
        'small':    'small.pt',
        'medium':   'medium.pt',
        'large':    'large.pt',
        'large-v2': 'large-v2.pt',
        'large-v3': 'large-v3.pt',
    }
    available = []
    if os.path.exists(model_dir):
        for name, fname in known_files.items():
            if os.path.exists(os.path.join(model_dir, fname)):
                available.append(name)
    return available

def transcribe_with_whisper(video_path, output_txt_dir, model_name='medium',
                             model_dir='models/whisper', device='auto',
                             log_callback=None, progress_callback=None,
                             whisper_progress_callback=None, cancel_event=None):
    """
    Sử dụng Whisper AI để phân tích âm thanh từ file video và tạo transcript.
    Whisper hoạt động trực tiếp với file video (tự tách audio nội bộ qua ffmpeg).

    Args:
        video_path:       Đường dẫn đến file video đã tải về.
        output_txt_dir:   Thư mục lưu file .txt transcript kết quả.
        model_name:       Tên model Whisper (tiny/base/small/medium/large/large-v3).
        model_dir:        Thư mục chứa (hoặc sẽ tải về) các model Whisper.
        device:           "auto" | "cuda" | "cpu"
        log_callback:     Callback để ghi log.
        progress_callback: Không dùng trực tiếp ở đây (Whisper không expose progress %).

    Returns:
        str: Đường dẫn file .txt nếu thành công, None nếu thất bại.
    """
    # Kiểm tra Whisper đã cài chưa
    try:
        import whisper
    except ImportError:
        if log_callback:
            log_callback("[Whisper] ❌ Chưa cài openai-whisper! Vui lòng chạy setup_local.ps1 để cài đặt.")
        return None

    # Đảm bảo ffmpeg có trong PATH (Whisper cần ffmpeg để tách audio)
    if not ensure_ffmpeg_in_path():
        if log_callback:
            log_callback("[Whisper] ❌ Không tìm thấy ffmpeg! Cần cài ffmpeg để Whisper hoạt động.")
        return None

    if not os.path.exists(video_path):
        if log_callback:
            log_callback(f"[Whisper] ❌ Không tìm thấy file video: {video_path}")
        return None

    # Xác định thiết bị xử lý
    actual_device = device
    if device == 'auto':
        try:
            import torch
            actual_device = 'cuda' if torch.cuda.is_available() else 'cpu'
        except ImportError:
            actual_device = 'cpu'

    if log_callback:
        log_callback(f"[Whisper] 🎙️ Bắt đầu phân tích âm thanh bằng model '{model_name}' trên {actual_device.upper()}...")
        if actual_device == 'cuda' and model_name in ['large', 'large-v2', 'large-v3']:
            log_callback("[Whisper] ⚠️ Lưu ý: large model cần ~3GB VRAM. GTX 950 (2GB) có thể bị OOM, sẽ tự fallback sang CPU.")

    # Load model (tự tải nếu chưa có)
    os.makedirs(model_dir, exist_ok=True)
    try:
        model = whisper.load_model(model_name, device=actual_device, download_root=model_dir)
    except RuntimeError as e:
        if 'out of memory' in str(e).lower() and actual_device == 'cuda':
            if log_callback:
                log_callback("[Whisper] ⚠️ VRAM không đủ! Chuyển sang CPU để xử lý (sẽ chậm hơn)...")
            try:
                import torch
                torch.cuda.empty_cache()
                model = whisper.load_model(model_name, device='cpu', download_root=model_dir)
                actual_device = 'cpu'
            except Exception as e2:
                if log_callback:
                    log_callback(f"[Whisper] ❌ Không thể load model ngay cả trên CPU: {e2}")
                return None
        else:
            if log_callback:
                log_callback(f"[Whisper] ❌ Lỗi load model: {e}")
            return None

    if log_callback:
        log_callback(f"[Whisper] ⏳ Đang nhận diện giọng nói... (Có thể mất vài phút tuỳ độ dài video)")

    # Intercept stderr to parse tqdm
    # Tạo interceptor để chèn vào sys.stderr
    interceptor = TqdmInterceptor(
        callback=whisper_progress_callback, 
        original_stderr=sys.stderr, 
        log_callback=log_callback,
        cancel_event=cancel_event
    )
    sys.stderr = interceptor

    # Transcribe
    try:
        # Tắt cảnh báo FP16 trên CPU
        fp16_flag = True if actual_device == 'cuda' else False
        result = model.transcribe(
            video_path,
            verbose=False,
            word_timestamps=False,
            fp16=fp16_flag,
            # Gợi ý ngôn ngữ: nếu video tiếng Việt thì khai báo để tăng độ chính xác
            # language='vi'  # Bỏ comment nếu muốn force tiếng Việt
        )
    except Exception as e:
        if log_callback:
            log_callback(f"[Whisper] ❌ Lỗi trong quá trình transcribe: {e}")
        return None
    finally:
        # Restore stderr
        sys.stderr = original_stderr

    # Chuẩn bị tên file output
    video_basename = os.path.splitext(os.path.basename(video_path))[0]
    txt_filename = f"{video_basename}_whisper_transcript.txt"
    txt_path = os.path.join(output_txt_dir, txt_filename)

    # Ghi kết quả ra file .txt theo định dạng chuẩn của Tool
    os.makedirs(output_txt_dir, exist_ok=True)
    try:
        segments = result.get('segments', [])
        detected_lang = result.get('language', 'unknown')

        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"# Transcript được tạo bởi Whisper AI ({model_name})\n")
            f.write(f"# Ngôn ngữ phát hiện: {detected_lang}\n")
            f.write(f"# Thiết bị xử lý: {actual_device.upper()}\n\n")

            for seg in segments:
                start_ts = seconds_to_timestamp(seg['start'])
                end_ts = seconds_to_timestamp(seg['end'])
                text = seg['text'].strip()
                if text:
                    f.write(f"{start_ts} --> {end_ts}\n")
                    f.write(f"{text}\n\n")

        if log_callback:
            log_callback(f"[Whisper] ✅ Hoàn thành! Ngôn ngữ: {detected_lang.upper()} | {len(segments)} đoạn | Lưu tại: {txt_filename}")

        return txt_path

    except Exception as e:
        if log_callback:
            log_callback(f"[Whisper] ❌ Lỗi khi ghi file transcript: {e}")
        return None

def download_whisper_model(model_name, model_dir='models/whisper', log_callback=None):
    """
    Tải model Whisper về thư mục local.
    Dùng cho nút 'Tải Model' trong Settings UI.
    """
    try:
        import whisper
    except ImportError:
        if log_callback:
            log_callback("❌ Chưa cài openai-whisper!")
        return False

    if log_callback:
        model_sizes = {
            'tiny': '75MB', 'base': '145MB', 'small': '480MB',
            'medium': '1.5GB', 'large': '2.9GB', 'large-v2': '2.9GB', 'large-v3': '2.9GB'
        }
        size = model_sizes.get(model_name, '???')
        log_callback(f"[Whisper] ⬇️ Đang tải model '{model_name}' ({size})...")

    os.makedirs(model_dir, exist_ok=True)
    try:
        whisper.load_model(model_name, download_root=model_dir)
        if log_callback:
            log_callback(f"[Whisper] ✅ Đã tải model '{model_name}' thành công vào: {model_dir}")
        return True
    except Exception as e:
        if log_callback:
            log_callback(f"[Whisper] ❌ Lỗi tải model: {e}")
        return False

# ---------------------------------------------------------------------------
# Fetch: Quét danh sách URL → thông tin video
# ---------------------------------------------------------------------------

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
                            title = entry.get('title', 'Unknown Title')
                            v_url = entry.get('url') or f"https://www.youtube.com/watch?v={v_id}"
                            is_main = (main_v_id and v_id == main_v_id) or len(entries) == 1
                            
                            has_subs = bool(entry.get('subtitles') or entry.get('automatic_captions'))

                            results.append({
                                'url': v_url, 
                                'title': title, 
                                'is_main': is_main, 
                                'id': v_id, 
                                'platform': platform,
                                'has_subtitles': has_subs,
                                'is_local': False
                            })

                    else:
                        # Nền tảng ngoài YouTube — lấy metadata nhanh
                        ydl_fast_opts = {**ydl_opts, 'process': False}
                        with yt_dlp.YoutubeDL(ydl_fast_opts) as ydl_fast:
                            info = ydl_fast.extract_info(url, download=False)
                            title = "Unknown Video"
                            v_id = "unknown"
                            if info:
                                title = info.get('title') or info.get('description') or f"{platform.capitalize()} Video"
                                v_id = info.get('id') or "video"
                                if len(title) > 80:
                                    title = title[:77] + "..."

                            results.append({
                                'url': url, 
                                'title': title, 
                                'is_main': True, 
                                'id': v_id, 
                                'platform': platform,
                                'has_subtitles': False,
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

    return results

# ---------------------------------------------------------------------------
# Download: Tải 1 URL (video + subtitle hoặc Whisper transcript)
# ---------------------------------------------------------------------------

def download_subtitles_for_url(task, lang='vi', output_dir='downloads', download_video=True,
                               browser='chrome', video_quality='1080p',
                               whisper_model='medium', whisper_device='auto',
                               whisper_model_dir='models/whisper',
                               enable_speaker_diarization=False, gemini_api_key='',
                               gemini_model='gemini-2.5-flash',
                               progress_callback=None, log_callback=None, diarization_progress_callback=None,
                               whisper_progress_callback=None, cancel_event=None):
    """
    Tải video và tạo transcript cho 1 tác vụ.
    """
    url = task['url']
    use_subtitle = task.get('use_sub', False)
    use_whisper = task.get('use_whisper', False)
    is_local = task.get('is_local', False)

    videos_dir = os.path.join(output_dir, 'videos')
    vtt_dir = os.path.join(output_dir, 'vtt_goc')
    txt_dir = os.path.join(output_dir, 'txt_convert')
    txt_speaker_dir = os.path.join(output_dir, 'txt_speaker')

    for d in [videos_dir, vtt_dir, txt_dir, txt_speaker_dir]:
        os.makedirs(d, exist_ok=True)

    platform = detect_platform(url)
    is_youtube = platform in ["youtube", "youtube_shorts"]

    download_size = 0

    if is_local:
        if log_callback:
            mode_icon = "🎙️" if use_whisper else "📄"
            log_callback(f"[LOCAL] {mode_icon} Xử lý tệp máy tính: {os.path.basename(url)}")
        
        video_path = url
        download_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0

        if progress_callback:
            progress_callback(url, 100.0, download_size, download_size)

        if use_whisper:
            if log_callback:
                log_callback(f"🎙️ Bắt đầu phân tích Whisper cho tệp {os.path.basename(video_path)}...")
            transcribe_with_whisper(
                video_path=video_path,
                output_txt_dir=txt_dir,
                model_name=whisper_model,
                model_dir=whisper_model_dir,
                device=whisper_device,
                log_callback=log_callback,
                whisper_progress_callback=lambda p, s: whisper_progress_callback(url, p, s) if whisper_progress_callback else None,
                cancel_event=cancel_event
            )

    else:
        # Ghi lại file video đã tải (để Whisper xử lý sau)
        downloaded_video_file = [None]
        files_before_download = set(os.listdir(videos_dir))

        # --- Hook theo dõi tiến trình ---
        def my_hook(d):
            if cancel_event and cancel_event.is_set():
                raise CancelException("Tiến trình đã bị hủy bởi người dùng.")

            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                if total > 0 and progress_callback:
                    percent = (downloaded / total) * 100
                    progress_callback(url, percent, downloaded, total)
            elif d['status'] == 'finished':
                downloaded_video_file[0] = d.get('filename')
                if progress_callback:
                    progress_callback(url, 100.0, d.get('total_bytes', 0), d.get('total_bytes', 0))
                if log_callback:
                    filename = os.path.basename(d.get('filename', 'video'))
                    log_callback(f"✅ Đã tải xong: {filename}")

        # --- Cấu hình yt-dlp ---
        outtmpl_dict = {
            'default': os.path.join(videos_dir, '%(id)s_%(title)s_%(upload_date)s.%(ext)s'),
            'subtitle': os.path.join(vtt_dir, '%(id)s_%(title)s_%(upload_date)s.%(ext)s')
        }

    ydl_opts = {
        'skip_download': not download_video,
        'outtmpl': outtmpl_dict,
        'noplaylist': True,
        'js_runtimes': {'node': {}},
        'remote_components': {'ejs:github'},
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'progress_hooks': [my_hook]
    }

    # Phụ đề: chỉ tải nếu là YouTube và ở chế độ prefer_subtitle
    if use_subtitle:
        ydl_opts.update({
            'writesubtitles': True,      # Ưu tiên sub tự chèn (manual)
            'writeautomaticsub': True,   # Fallback sang sub tự động
            'subtitleslangs': [lang],
            'subtitlesformat': 'vtt'
        })
    else:
        ydl_opts.update({'writesubtitles': False, 'writeautomaticsub': False})

    # Cookie authentication
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"
    elif browser and browser != "Không dùng":
        ydl_opts['cookiesfrombrowser'] = (browser.lower(), )

    # Chất lượng video
    if download_video:
        quality_map = {
            '4K':     'bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160]/best',
            '1080p':  'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best',
            '720p':   'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best',
            '480p':   'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best',
            'Tốt nhất': 'bestvideo+bestaudio/best'
        }
        ydl_opts['format'] = quality_map.get(video_quality, quality_map['1080p'])

        if log_callback:
            mode_icon = "📝" if use_subtitle else "🎙️"
            mode_label = "Subtitle YouTube" if use_subtitle else f"Whisper AI ({whisper_model})"
            log_callback(f"[{platform.upper()}] {mode_icon} Transcript: {mode_label} | URL: {url[:60]}...")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)

                # Kiểm tra tải thất bại (link hết hạn, private, cần login...)
                if not info_dict:
                    if log_callback:
                        log_callback(f"❌ Không thể tải: {url}\n   → Kiểm tra lại link hoặc cấu hình Cookies đăng nhập trong tab ⚙️ Cài đặt.")
                    return False, 0

                # Ước lượng dung lượng
                download_size = (
                    info_dict.get('filesize') or
                    info_dict.get('filesize_approx') or
                    50 * 1024 * 1024
                )

            # --- Xử lý sau khi tải ---
            if use_subtitle:
                # YouTube: Làm sạch VTT → TXT
                if log_callback:
                    log_callback("📝 Đang chuẩn hóa phụ đề VTT → TXT...")
                vtt_files = list(set(
                    glob.glob(os.path.join(vtt_dir, f"*.{lang}.vtt")) +
                    glob.glob(os.path.join(vtt_dir, f"*{lang}.vtt"))
                ))
                converted_any = any(convert_vtt_to_txt(vf, txt_dir) for vf in vtt_files)
                if not converted_any and log_callback:
                    log_callback("⚠️ Không tìm thấy file phụ đề VTT. Video có thể không có subtitle.")
                elif log_callback:
                    log_callback("✅ Chuẩn hóa phụ đề hoàn thành!")

            if use_whisper and download_video:
                # Tìm file video mới nhất vừa tải về
                files_after_download = set(os.listdir(videos_dir))
                new_files = files_after_download - files_before_download
                video_path = None

                # Ưu tiên file từ hook, fallback sang scan thư mục
                if downloaded_video_file[0] and os.path.exists(downloaded_video_file[0]):
                    video_path = downloaded_video_file[0]
                else:
                    for fname in sorted(new_files):
                        if fname.lower().endswith(('.mp4', '.mkv', '.webm', '.mov', '.avi')):
                            video_path = os.path.join(videos_dir, fname)
                            break

                if video_path:
                    if log_callback:
                        log_callback(f"🎙️ Bắt đầu phân tích Whisper cho video tải về...")
                    transcribe_with_whisper(
                        video_path=video_path,
                        output_txt_dir=txt_dir,
                        model_name=whisper_model,
                        model_dir=whisper_model_dir,
                        device=whisper_device,
                        log_callback=log_callback,
                        whisper_progress_callback=lambda p, s: whisper_progress_callback(url, p, s) if whisper_progress_callback else None,
                        cancel_event=cancel_event
                    )
                elif log_callback:
                    log_callback("⚠️ Không tìm thấy file video để chạy Whisper. Hãy bật 'Tải Video' trong cài đặt.")

            # --- Chạy Nhận diện Người Nói (Speaker Diarization) ---
            if enable_speaker_diarization and gemini_api_key:
                txt_files = glob.glob(os.path.join(txt_dir, "*.txt"))
                for txt_file in txt_files:
                    basename = os.path.basename(txt_file)
                    output_txt_path = os.path.join(txt_speaker_dir, basename)
                    
                    # Callback trung gian để truyền url về GUI
                    def d_prog(percent):
                        if diarization_progress_callback:
                            diarization_progress_callback(url, percent)
                            
                    speaker_diarization.process_transcript(
                        input_txt_path=txt_file,
                        output_txt_path=output_txt_path,
                        api_key=gemini_api_key,
                        model_name=gemini_model,
                        log_callback=log_callback,
                        progress_callback=d_prog
                    )
                    
            if log_callback:
                log_callback(f"✅ Hoàn thành xử lý: {url}")

            return True, download_size

        except Exception as e:
            err_msg = str(e)
            if log_callback:
                if "cookie" in err_msg.lower():
                    log_callback(
                        f"❌ LỖI COOKIES KHI TẢI URL: {url}\n"
                        f"   Chi tiết: {err_msg}\n"
                        f"   👉 NGUYÊN NHÂN: Trình duyệt '{browser}' có thể đang mở và khóa tệp cookie.\n"
                        f"   👉 CÁCH KHẮC PHỤC:\n"
                        f"      1. Tắt HOÀN TOÀN trình duyệt '{browser}' (đảm bảo không còn chạy ngầm trong Task Manager) rồi tải lại.\n"
                        f"      2. Hoặc vào tab '⚙️ Cài đặt' -> Chọn 'Không dùng' ở mục 'Đọc Cookies từ trình duyệt' (nếu không cần tải video riêng tư/giới hạn).\n"
                        f"      3. Hoặc xuất tệp 'cookies.txt' từ trình duyệt bằng tiện ích mở rộng (như 'Get cookies.txt LOCALLY') rồi lưu vào thư mục phần mềm."
                    )
                else:
                    log_callback(f"❌ Lỗi khi xử lý {url}: {err_msg}")
            return False, 0

# ---------------------------------------------------------------------------
# Orchestrator: Xử lý nhiều URL tuần tự với anti-bot countdown
# ---------------------------------------------------------------------------

def process_multiple_urls(tasks, lang='vi', output_dir='downloads', download_video=True,
                          browser='chrome', delay_min=3.0, delay_max=5.0,
                          video_quality='1080p',
                          whisper_model='medium', whisper_device='auto',
                          whisper_model_dir='models/whisper',
                          enable_speaker_diarization=False, gemini_api_key='',
                          gemini_model='gemini-2.5-flash',
                          progress_callback=None, delay_callback=None, log_callback=None, 
                          diarization_progress_callback=None, whisper_progress_callback=None,
                          cancel_event=None):
    """
    Xử lý danh sách task tuần tự với khoảng nghỉ chống quét bot (chính xác milisecond).
    """
    if log_callback:
        mode_text = "Video + Transcript" if download_video else "Chỉ Transcript"
        log_callback(f"🚀 Bắt đầu [{mode_text}] — {len(tasks)} video(s) | Thư mục: {output_dir}")

    success_count = 0
    total_bytes = 0
    session_start = time.time()

    for i, task in enumerate(tasks):
        if cancel_event and cancel_event.is_set():
            break

        url = task['url']
        # Khoảng nghỉ anti-bot (từ video thứ 2 trở đi)
        if i > 0 and not task.get('is_local', False):
            delay = random.uniform(float(delay_min), float(delay_max))
            if log_callback:
                log_callback(f"\n🛡️ Khoảng nghỉ bảo vệ Cookie: {delay:.2f} giây...")

            start_delay = time.time()
            while True:
                if cancel_event and cancel_event.is_set():
                    break
                elapsed = time.time() - start_delay
                remaining = delay - elapsed
                if remaining <= 0:
                    break
                if delay_callback:
                    delay_callback(url, remaining)
                time.sleep(0.05)

            if cancel_event and cancel_event.is_set():
                break

            if delay_callback:
                delay_callback(url, 0.0)

        # Tải video
        success, video_bytes = download_subtitles_for_url(
            task=task,
            lang=lang,
            output_dir=output_dir,
            download_video=download_video,
            browser=browser,
            video_quality=video_quality,
            whisper_model=whisper_model,
            whisper_device=whisper_device,
            whisper_model_dir=whisper_model_dir,
            enable_speaker_diarization=enable_speaker_diarization,
            gemini_api_key=gemini_api_key,
            gemini_model=gemini_model,
            progress_callback=progress_callback,
            log_callback=log_callback,
            diarization_progress_callback=diarization_progress_callback,
            whisper_progress_callback=whisper_progress_callback,
            cancel_event=cancel_event
        )

        if success:
            success_count += 1
            total_bytes += video_bytes

    duration = time.time() - session_start
    if log_callback:
        log_callback(f"\n{'='*50}")
        log_callback(f"✅ HOÀN THÀNH: {success_count}/{len(tasks)} video thành công | Thời gian: {duration:.1f}s")
        log_callback(f"{'='*50}")

    return success_count, total_bytes, duration
