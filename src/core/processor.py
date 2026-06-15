import os
import sys
import glob
import re
import time
import random
import webvtt
import yt_dlp
import urllib.parse
from src.services.title_cleaner import clean_video_title, detect_platform, sanitize_filename
from src.core.downloader import get_ffmpeg_path, ensure_ffmpeg_in_path
from src.core.transcriber import transcribe_with_whisper
from src.core.diarizer import process_transcript
from src.core.interceptors import CancelException

def convert_vtt_to_txt(vtt_file_path, txt_dir, custom_basename=None):
    """
    Đọc file .vtt và chuyển nội dung ra file .txt.
    - Khử trùng lặp các dòng cuộn (rolling subtitles).
    - Dọn dẹp thẻ <c> và chuyển timestamp về định dạng giây.
    """
    if not os.path.exists(vtt_file_path):
        return None

    if custom_basename:
        txt_name = f"{custom_basename}.txt"
    else:
        base_name = os.path.basename(vtt_file_path)
        name_no_ext = base_name[:-4] if base_name.endswith('.vtt') else base_name
        name_no_lang = re.sub(r'\.[a-zA-Z]{2,3}(-[a-zA-Z]{2,4})?$', '', name_no_ext)
        txt_name = name_no_lang + '.txt'
        
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
                if '<c>' in line or '</c>' in line:
                    continue
                clean_text = line.strip()
                if not clean_text:
                    continue
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

        with open(txt_file_path, 'w', encoding='utf-8') as f_txt:
            for b in clean_blocks:
                f_txt.write(f"{b['start_txt']} --> {b['end_txt']}\n")
                f_txt.write(b['text'] + "\n\n")

        if custom_basename:
            clean_txt_name = f"{custom_basename}_clean.txt"
        else:
            base_name = os.path.basename(vtt_file_path)
            name_no_ext = base_name[:-4] if base_name.endswith('.vtt') else base_name
            name_no_lang = re.sub(r'\.[a-zA-Z]{2,3}(-[a-zA-Z]{2,4})?$', '', name_no_ext)
            clean_txt_name = name_no_lang + '_clean.txt'
            
        clean_txt_file_path = os.path.join(txt_dir, clean_txt_name)
        text_list = []
        for b in clean_blocks:
            text_list.append(b['text'].replace('\n', ' ').strip())
        clean_text_content = " ".join(text_list)
        clean_text_content = re.sub(r'\s+', ' ', clean_text_content).strip()
        with open(clean_txt_file_path, 'w', encoding='utf-8') as f_clean:
            f_clean.write(clean_text_content)

        target_vtt_path = vtt_file_path
        if custom_basename:
            lang_match = re.search(r'\.([a-zA-Z]{2,3}(-[a-zA-Z]{2,4})?)\.vtt$', vtt_file_path)
            lang_suffix = f".{lang_match.group(1)}" if lang_match else ""
            target_vtt_path = os.path.join(os.path.dirname(vtt_file_path), f"{custom_basename}{lang_suffix}.vtt")

        with open(target_vtt_path, 'w', encoding='utf-8') as f_vtt:
            f_vtt.write("WEBVTT\n\n")
            for b in clean_blocks:
                f_vtt.write(f"{b['start_vtt']} --> {b['end_vtt']}\n")
                f_vtt.write(b['text'] + "\n\n")

        if custom_basename and vtt_file_path != target_vtt_path:
            try:
                os.remove(vtt_file_path)
            except Exception:
                pass

        return txt_file_path
    except Exception as e:
        print(f"Lỗi convert VTT: {vtt_file_path}: {e}")
        return None

def download_subtitles_for_url(task, lang='vi', output_dir='downloads', download_video=True,
                               browser='chrome', video_quality='1080p',
                               whisper_model='medium', whisper_device='auto',
                               whisper_model_dir='models/whisper',
                               enable_speaker_diarization=False,
                               progress_callback=None, log_callback=None, diarization_progress_callback=None,
                               whisper_progress_callback=None, cancel_event=None, whisper_lang_callback=None,
                               settings_dict=None):
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

    platform = task.get('platform') or detect_platform(url)

    duration = task.get('duration')
    url_lower = url.lower()
    is_fb_short = "facebook.com/reels" in url_lower or "facebook.com/stories" in url_lower or "fb.com/reels" in url_lower or "fb.com/stories" in url_lower
    
    is_short = False
    if platform in ["youtube_shorts", "tiktok", "instagram"] or is_fb_short:
        is_short = True
    elif duration is not None and duration < 180:
        is_short = True

    if is_short and enable_speaker_diarization:
        if log_callback:
            log_callback(f"⚡ [VIDEO NGẮN] Tự động tối ưu: Bỏ qua Speaker Diarization để bảo toàn hạn ngạch API và tăng tốc.")
        enable_speaker_diarization = False

    download_size = 0

    if is_local:
        if log_callback:
            mode_icon = "🎙️" if use_whisper else "📄"
            log_callback(f"[LOCAL] {mode_icon} Xử lý tệp máy tính: {os.path.basename(url)}")
        
        video_path = url
        download_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0

        if progress_callback:
            progress_callback(url, 100.0, download_size, download_size)

        if use_whisper or use_subtitle:
            if log_callback:
                mode_icon = "🎙️" if use_whisper else "📝"
                log_callback(f"{mode_icon} Bắt đầu phân tích Whisper cho tệp {os.path.basename(video_path)}...")
            
            transcribe_with_whisper(
                video_path=video_path,
                output_txt_dir=txt_dir,
                model_name=whisper_model,
                model_dir=whisper_model_dir,
                device=whisper_device,
                log_callback=log_callback,
                whisper_progress_callback=lambda p, s: whisper_progress_callback(url, p, s) if whisper_progress_callback else None,
                cancel_event=cancel_event,
                whisper_lang_callback=lambda l: whisper_lang_callback(url, l) if whisper_lang_callback else None,
                settings_dict=settings_dict
            )

        is_auto_lang = not lang or lang in ["Auto-detect (Tự động)", "Tự động", "auto", ""] or lang.startswith("Auto-detect")
        need_translation = not is_auto_lang
        need_gemini = enable_speaker_diarization or need_translation
        
        if need_gemini:
            txt_files = glob.glob(os.path.join(txt_dir, "*.txt"))
            for txt_file in txt_files:
                if txt_file.endswith("_clean.txt"):
                    continue
                basename = os.path.basename(txt_file)
                output_txt_path = os.path.join(txt_speaker_dir, basename)
                
                process_transcript(
                    input_txt_path=txt_file,
                    output_txt_path=output_txt_path,
                    log_callback=log_callback,
                    progress_callback=lambda p: diarization_progress_callback(url, p) if diarization_progress_callback else None,
                    target_lang=lang if need_translation else None,
                    diarize=enable_speaker_diarization,
                    cancel_event=cancel_event
                )
                
        if log_callback:
            log_callback(f"✅ Hoàn thành xử lý: {url}")

        return True, download_size

    else:
        downloaded_video_file = [None]
        files_before_download = set(os.listdir(videos_dir))

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

        outtmpl_dict = {
            'default': os.path.join(videos_dir, '%(title.80)s.%(ext)s'),
            'subtitle': os.path.join(vtt_dir, '%(title.80)s.%(ext)s')
        }

    is_whisper_only = use_whisper and not download_video

    ydl_opts = {
        'trim_file_name': 100,
        'skip_download': not download_video if not is_whisper_only else False,
        'outtmpl': outtmpl_dict,
        'noplaylist': True,
        'js_runtimes': {'node': {}},
        'remote_components': {'ejs:github'},
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'progress_hooks': [my_hook]
    }

    ffmpeg_exe = get_ffmpeg_path()
    if ffmpeg_exe:
        ydl_opts['ffmpeg_location'] = ffmpeg_exe

    if use_subtitle:
        ydl_opts.update({
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': [lang],
            'subtitlesformat': 'vtt'
        })
    else:
        ydl_opts.update({'writesubtitles': False, 'writeautomaticsub': False})

    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"
    elif browser and browser != "Không dùng":
        ydl_opts['cookiesfrombrowser'] = (browser.lower(), )

    if is_whisper_only:
        ydl_opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
        if log_callback:
            log_callback(f"[{platform.upper()}] 🎙️ Transcript: Whisper AI ({whisper_model}) (Chỉ tải luồng âm thanh siêu nhẹ) | URL: {url[:60]}...")
    elif download_video:
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
            if not info_dict:
                if log_callback:
                    log_callback(f"❌ Không thể tải: {url}\n   → Kiểm tra lại link hoặc cấu hình Cookies đăng nhập trong tab ⚙️ Cài đặt.")
                return False, 0

            download_size = (
                info_dict.get('filesize') or
                info_dict.get('filesize_approx') or
                50 * 1024 * 1024
            )

        video_path = None
        if download_video or is_whisper_only:
            files_after_download = set(os.listdir(videos_dir))
            new_files = files_after_download - files_before_download

            if downloaded_video_file[0] and os.path.exists(downloaded_video_file[0]):
                video_path = downloaded_video_file[0]
            else:
                for fname in sorted(new_files):
                    if fname.lower().endswith(('.mp4', '.mkv', '.webm', '.mov', '.avi', '.m4a', '.mp3', '.ogg', '.wav')):
                        video_path = os.path.join(videos_dir, fname)
                        break

            if video_path:
                sanitized_title = sanitize_filename(task.get('title', 'video'))
                ext = os.path.splitext(video_path)[1]
                new_video_path = os.path.join(videos_dir, f"{sanitized_title}{ext}")
                if video_path != new_video_path:
                    try:
                        if os.path.exists(new_video_path):
                            os.remove(new_video_path)
                        os.rename(video_path, new_video_path)
                        video_path = new_video_path
                        if log_callback:
                            log_callback(f"🧹 Đổi tên tệp video thành: {os.path.basename(video_path)}")
                    except Exception as e:
                        if log_callback:
                            log_callback(f"⚠️ Không thể đổi tên tệp video: {e}")

        if use_subtitle:
            if log_callback:
                log_callback("📝 Đang chuẩn hóa phụ đề VTT → TXT...")
            vtt_files = list(set(
                glob.glob(os.path.join(vtt_dir, f"*.{lang}.vtt")) +
                glob.glob(os.path.join(vtt_dir, f"*{lang}.vtt"))
            ))
            custom_basename = sanitize_filename(task.get('title', 'video'))
            converted_any = any(convert_vtt_to_txt(vf, txt_dir, custom_basename) for vf in vtt_files)
            if not converted_any and log_callback:
                log_callback("⚠️ Không tìm thấy file phụ đề VTT. Video có thể không có subtitle.")
            elif log_callback:
                log_callback("✅ Chuẩn hóa phụ đề hoàn thành!")

        if use_whisper:
            if video_path:
                if log_callback:
                    msg = "🎙️ Bắt đầu phân tích Whisper cho âm thanh tạm thời..." if not download_video else "🎙️ Bắt đầu phân tích Whisper cho video tải về..."
                    log_callback(msg)
                
                transcribe_with_whisper(
                    video_path=video_path,
                    output_txt_dir=txt_dir,
                    model_name=whisper_model,
                    model_dir=whisper_model_dir,
                    device=whisper_device,
                    log_callback=log_callback,
                    whisper_progress_callback=lambda p, s: whisper_progress_callback(url, p, s) if whisper_progress_callback else None,
                    cancel_event=cancel_event,
                    settings_dict=settings_dict
                )
                
                if not download_video:
                    try:
                        if os.path.exists(video_path):
                            os.remove(video_path)
                            if log_callback:
                                log_callback(f"🧹 Đã dọn dẹp tệp âm thanh tạm thời: {os.path.basename(video_path)}")
                    except Exception as e:
                        if log_callback:
                            log_callback(f"⚠️ Không thể xóa tệp tạm thời: {e}")
            elif log_callback:
                log_callback("⚠️ Không tìm thấy file âm thanh/video để chạy Whisper.")

        is_auto_lang = not lang or lang in ["Auto-detect (Tự động)", "Tự động", "auto", ""] or lang.startswith("Auto-detect")
        need_translation = not is_auto_lang
        need_gemini = enable_speaker_diarization or need_translation
        
        if need_gemini:
            txt_files = glob.glob(os.path.join(txt_dir, "*.txt"))
            for txt_file in txt_files:
                if txt_file.endswith("_clean.txt"):
                    continue
                basename = os.path.basename(txt_file)
                output_txt_path = os.path.join(txt_speaker_dir, basename)
                
                process_transcript(
                    input_txt_path=txt_file,
                    output_txt_path=output_txt_path,
                    log_callback=log_callback,
                    progress_callback=lambda p: diarization_progress_callback(url, p) if diarization_progress_callback else None,
                    target_lang=lang if need_translation else None,
                    diarize=enable_speaker_diarization,
                    cancel_event=cancel_event
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

def process_multiple_urls(tasks, lang='vi', output_dir='downloads', download_video=True,
                          browser='chrome', delay_min=3.0, delay_max=5.0,
                          video_quality='1080p',
                          whisper_model='medium', whisper_device='auto',
                          whisper_model_dir='models/whisper',
                          enable_speaker_diarization=False,
                          progress_callback=None, delay_callback=None, log_callback=None, 
                          diarization_progress_callback=None, whisper_progress_callback=None,
                          cancel_event=None, whisper_lang_callback=None, settings_dict=None):
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
        video_lang = task.get('lang', lang)
        
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

        success, video_bytes = download_subtitles_for_url(
            task=task,
            lang=video_lang,
            output_dir=output_dir,
            download_video=download_video,
            browser=browser,
            video_quality=video_quality,
            whisper_model=whisper_model,
            whisper_device=whisper_device,
            whisper_model_dir=whisper_model_dir,
            enable_speaker_diarization=enable_speaker_diarization,
            progress_callback=progress_callback,
            log_callback=log_callback,
            diarization_progress_callback=diarization_progress_callback,
            whisper_progress_callback=whisper_progress_callback,
            cancel_event=cancel_event,
            whisper_lang_callback=whisper_lang_callback,
            settings_dict=settings_dict
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

def _worker_process(q, tasks, session_dir, settings_dict):
    """
    Hàm Wrapper chạy ngầm trên Tiến trình riêng (Multiprocessing).
    Truyền dữ liệu tiến trình và log về GUI thông qua Queue.
    """
    def log_cb(msg): q.put(("log", msg))
    def prog_cb(url, pct, dl, tot): q.put(("prog", (url, pct, dl, tot)))
    def delay_cb(url, sec): q.put(("delay", (url, sec)))
    def d_prog_cb(url, pct): q.put(("d_prog", (url, pct)))
    def w_prog_cb(url, pct, stats): q.put(("w_prog", (url, pct, stats)))
    def w_lang_cb(url, lang): q.put(("w_lang", (url, lang)))

    # Đảm bảo imports nằm trong worker process
    from src.core.downloader import apply_ytdlp_update
    # Ưu tiên áp dụng bản cập nhật yt-dlp nếu có
    apply_ytdlp_update()

    try:
        success_count, total_bytes, duration = process_multiple_urls(
            tasks=tasks,
            lang=settings_dict['lang'],
            output_dir=session_dir,
            download_video=settings_dict['download_video'],
            browser=settings_dict['browser'],
            delay_min=settings_dict['delay_min'],
            delay_max=settings_dict['delay_max'],
            video_quality=settings_dict['video_quality'],
            whisper_model=settings_dict['whisper_model'],
            whisper_device=settings_dict['whisper_device'],
            whisper_model_dir=settings_dict['whisper_model_dir'],
            enable_speaker_diarization=settings_dict['enable_speaker_diarization'],
            progress_callback=prog_cb,
            delay_callback=delay_cb,
            log_callback=log_cb,
            diarization_progress_callback=d_prog_cb,
            whisper_progress_callback=w_prog_cb,
            whisper_lang_callback=w_lang_cb,
            settings_dict=settings_dict
        )
        q.put(("done", (success_count, total_bytes, duration)))
    except Exception as e:
        q.put(("error", str(e)))
