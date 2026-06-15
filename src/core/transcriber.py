import os
import sys
import re
import requests
import json
from google import genai
from google.genai import types
from src.core.interceptors import TqdmInterceptor, StdoutInterceptor, CancelException
from src.core.downloader import ensure_ffmpeg_in_path, get_ffmpeg_path

def seconds_to_timestamp(seconds):
    """Chuyển đổi số giây thành định dạng timestamp (hh:mm:ss)."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"

def check_whisper_available():
    """Kiểm tra xem openai-whisper đã được cài chưa."""
    try:
        import whisper
        return True
    except ImportError:
        return False

def get_available_whisper_models(model_dir='models/whisper'):
    """Trả về danh sách tên các model Whisper đã được tải về máy."""
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

def transcribe_with_whisper_local(video_path, model_name, model_dir, device, log_callback, whisper_progress_callback, cancel_event, whisper_lang_callback):
    """Thực hiện transcribe bằng Whisper Local."""
    import whisper
    
    actual_device = device
    if device == 'auto':
        try:
            import torch
            actual_device = 'cuda' if torch.cuda.is_available() else 'cpu'
        except ImportError:
            actual_device = 'cpu'

    if log_callback:
        log_callback(f"[Whisper] 🎙️ Bắt đầu phân tích âm thanh (Local) bằng model '{model_name}' trên {actual_device.upper()}...")
        if actual_device == 'cuda' and model_name in ['large', 'large-v2', 'large-v3']:
            log_callback("[Whisper] ⚠️ VRAM yêu cầu cao. Nếu bị OOM (Out Of Memory), hệ thống sẽ tự động chuyển sang CPU.")

    # Tạo interceptor
    interceptor = TqdmInterceptor(
        callback=whisper_progress_callback, 
        original_stderr=sys.stderr, 
        log_callback=log_callback,
        cancel_event=cancel_event,
        lang_callback=whisper_lang_callback
    )
    original_stderr = sys.stderr
    sys.stderr = interceptor
    
    original_stdout = sys.stdout
    stdout_interceptor = StdoutInterceptor(
        original_stdout=sys.stdout,
        lang_callback=whisper_lang_callback,
        log_callback=log_callback
    )
    sys.stdout = stdout_interceptor

    try:
        if cancel_event and cancel_event.is_set():
            raise CancelException("Tiến trình đã bị hủy bởi người dùng.")

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
                    if cancel_event and cancel_event.is_set():
                        raise CancelException("Tiến trình đã bị hủy bởi người dùng.")
                    model = whisper.load_model(model_name, device='cpu', download_root=model_dir)
                    actual_device = 'cpu'
                except Exception as e2:
                    if isinstance(e2, CancelException):
                        raise e2
                    if log_callback:
                        log_callback(f"[Whisper] ❌ Không thể load model ngay cả trên CPU: {e2}")
                    return None
            else:
                if log_callback:
                    log_callback(f"[Whisper] ❌ Lỗi load model: {e}")
                return None

        if cancel_event and cancel_event.is_set():
            raise CancelException("Tiến trình đã bị hủy bởi người dùng.")

        if log_callback:
            log_callback(f"[Whisper] ⏳ Đang nhận diện giọng nói... (Có thể mất vài phút tuỳ độ dài video)")

        fp16_flag = True if actual_device == 'cuda' else False
        result = model.transcribe(
            video_path,
            verbose=False,
            word_timestamps=False,
            fp16=fp16_flag,
        )
        return result
    except Exception as e:
        if isinstance(e, CancelException):
            raise e
        if log_callback:
            log_callback(f"[Whisper] ❌ Lỗi trong quá trình transcribe: {e}")
        return None
    finally:
        sys.stderr = original_stderr
        sys.stdout = original_stdout

def transcribe_with_cloud_api(video_path, settings_dict, log_callback):
    """
    Thực hiện transcribe thông qua API đám mây (OpenAI hoặc Gemini) 
    để hỗ trợ máy cấu hình yếu.
    """
    openai_key = settings_dict.get("openai_api_key", "").strip()
    gemini_key = settings_dict.get("gemini_api_key", "").strip()
    
    # 1. Trích xuất audio từ video bằng ffmpeg trước khi upload (để giảm băng thông)
    audio_path = os.path.splitext(video_path)[0] + ".mp3"
    ffmpeg_exe = get_ffmpeg_path()
    
    if log_callback:
        log_callback("[Cloud API] 🗜️ Đang trích xuất và nén âm thanh từ video...")
        
    try:
        # Tách audio nén bit-rate thấp để tối ưu dung lượng tải lên
        cmd = [ffmpeg_exe, "-y", "-i", video_path, "-vn", "-ar", "16000", "-ac", "1", "-b:a", "64k", audio_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except Exception as e:
        if log_callback:
            log_callback(f"[Cloud API] ⚠️ Không thể nén âm thanh bằng ffmpeg, sẽ gửi file gốc: {e}")
        audio_path = video_path

    # Nếu cấu hình OpenAI API Key
    if openai_key:
        if log_callback:
            log_callback("[Cloud API] ☁️ Đang gửi yêu cầu transcribe lên OpenAI Whisper API...")
        try:
            url = "https://api.openai.com/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {openai_key}"}
            with open(audio_path, 'rb') as f:
                files = {'file': (os.path.basename(audio_path), f, 'audio/mpeg')}
                data = {'model': 'whisper-1', 'response_format': 'verbose_json'}
                resp = requests.post(url, headers=headers, files=files, data=data, timeout=120)
                
            if resp.status_code == 200:
                result = resp.json()
                if audio_path != video_path and os.path.exists(audio_path):
                    os.remove(audio_path)
                return result
            else:
                raise Exception(f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            if log_callback:
                log_callback(f"[Cloud API] ❌ Lỗi gọi OpenAI API: {e}")

    # Fallback/Hoặc cấu hình Gemini API Key
    if gemini_key:
        if log_callback:
            log_callback("[Cloud API] ☁️ Đang gửi tệp âm thanh lên Google Gemini API để xử lý...")
        try:
            client = genai.Client(api_key=gemini_key)
            # Upload file lên Gemini File API
            uploaded_file = client.files.upload(file=audio_path)
            
            # Chờ xử lý file
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(2)
                uploaded_file = client.files.get(name=uploaded_file.name)
                
            if uploaded_file.state.name == "FAILED":
                raise Exception("Tải tệp lên Gemini API thất bại.")
                
            # Tạo prompt trích xuất và format
            prompt = (
                "Hãy nghe đoạn âm thanh này và xuất ra bản transcript đầy đủ, có chèn timestamp bắt đầu và kết thúc ở định dạng:\n"
                "hh:mm:ss --> hh:mm:ss\n"
                "[Văn bản thoại]\n\n"
                "Chỉ trả về định dạng timestamp và văn bản thoại, không thêm bất kỳ văn bản giải thích nào khác."
            )
            
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[uploaded_file, prompt]
            )
            
            # Xóa file sau khi xử lý xong
            client.files.delete(name=uploaded_file.name)
            if audio_path != video_path and os.path.exists(audio_path):
                os.remove(audio_path)
                
            # Parse nội dung Gemini trả về thành cấu trúc segments chuẩn
            text = response.text.strip()
            segments = []
            pattern = re.compile(r'(\d{2}:\d{2}:\d{2})\s*-->\s*(\d{2}:\d{2}:\d{2})\n(.*)', re.MULTILINE)
            
            # Parse sơ bộ
            lines = text.split('\n')
            current_time = ""
            current_text = []
            
            for line in lines:
                line = line.strip()
                if "-->" in line:
                    if current_time and current_text:
                        segments.append({"start_ts": current_time.split("-->")[0].strip(), "end_ts": current_time.split("-->")[1].strip(), "text": " ".join(current_text)})
                        current_text = []
                    current_time = line
                elif line:
                    current_text.append(line)
                    
            if current_time and current_text:
                segments.append({"start_ts": current_time.split("-->")[0].strip(), "end_ts": current_time.split("-->")[1].strip(), "text": " ".join(current_text)})
                
            return {"segments": segments, "language": "auto"}
            
        except Exception as e:
            if log_callback:
                log_callback(f"[Cloud API] ❌ Lỗi gọi Gemini API: {e}")
                
    if audio_path != video_path and os.path.exists(audio_path):
        os.remove(audio_path)
    return None

def transcribe_with_whisper(video_path, output_txt_dir, model_name='medium',
                             model_dir='models/whisper', device='auto',
                             log_callback=None,
                             whisper_progress_callback=None, cancel_event=None,
                             whisper_lang_callback=None, settings_dict=None):
    """
    Orchestrator định tuyến giữa Local Whisper và Cloud API.
    """
    if cancel_event and cancel_event.is_set():
        raise CancelException("Tiến trình đã bị hủy bởi người dùng.")

    if not ensure_ffmpeg_in_path():
        if log_callback:
            log_callback("[Whisper] ❌ Không tìm thấy ffmpeg! Cần cài ffmpeg để Whisper hoạt động.")
        return None

    if not os.path.exists(video_path):
        if log_callback:
            log_callback(f"[Whisper] ❌ Không tìm thấy file video: {video_path}")
        return None

    result = None
    use_cloud = settings_dict and settings_dict.get("use_cloud_api", False)
    
    if use_cloud:
        result = transcribe_with_cloud_api(video_path, settings_dict, log_callback)
        if not result and log_callback:
            log_callback("[Whisper] ⚠️ Gọi Cloud API thất bại. Tự động fallback chuyển sang chạy Local...")
            
    if not result:
        # Kiểm tra Whisper cài chưa cho Local
        if not check_whisper_available():
            if log_callback:
                log_callback("[Whisper] ❌ Chưa cài openai-whisper! Không thể chạy local. Vui lòng chạy setup_local.ps1.")
            return None
        result = transcribe_with_whisper_local(
            video_path, model_name, model_dir, device, 
            log_callback, whisper_progress_callback, cancel_event, whisper_lang_callback
        )

    if not result:
        return None

    # Chuẩn bị tên file output
    video_basename = os.path.splitext(os.path.basename(video_path))[0]
    txt_filename = f"{video_basename}.txt"
    txt_path = os.path.join(output_txt_dir, txt_filename)

    # Ghi kết quả ra file .txt theo định dạng chuẩn của Tool
    os.makedirs(output_txt_dir, exist_ok=True)
    try:
        if cancel_event and cancel_event.is_set():
            raise CancelException("Tiến trình đã bị hủy bởi người dùng.")

        segments = result.get('segments', [])
        detected_lang = result.get('language', 'unknown')

        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"# Transcript được tạo bởi Whisper AI ({model_name})\n")
            f.write(f"# Ngôn ngữ phát hiện: {detected_lang}\n")
            f.write(f"# Chế độ: {'Cloud API' if use_cloud else 'Local Model'}\n\n")

            for seg in segments:
                if cancel_event and cancel_event.is_set():
                    raise CancelException("Tiến trình đã bị hủy bởi người dùng.")
                
                # Parse start/end timestamp
                if 'start' in seg:
                    start_ts = seconds_to_timestamp(seg['start'])
                    end_ts = seconds_to_timestamp(seg['end'])
                else:
                    start_ts = seg.get('start_ts', '00:00:00')
                    end_ts = seg.get('end_ts', '00:00:00')
                    
                text = seg['text'].strip()
                if text:
                    f.write(f"{start_ts} --> {end_ts}\n")
                    f.write(f"{text}\n\n")

        # Ghi file sạch liền mạch không timestamp
        clean_txt_filename = f"{video_basename}_clean.txt"
        clean_txt_path = os.path.join(output_txt_dir, clean_txt_filename)
        text_list = [seg['text'].strip() for seg in segments if seg.get('text')]
        clean_text_content = " ".join(text_list)
        clean_text_content = re.sub(r'\s+', ' ', clean_text_content).strip()
        with open(clean_txt_path, 'w', encoding='utf-8') as f_clean:
            f_clean.write(clean_text_content)

        if log_callback:
            log_callback(f"[Whisper] ✅ Hoàn thành! Ngôn ngữ: {detected_lang.upper()} | {len(segments)} đoạn | Lưu tại: {txt_filename}")

        return txt_path

    except Exception as e:
        if log_callback:
            log_callback(f"[Whisper] ❌ Lỗi khi ghi file transcript: {e}")
        return None

def download_whisper_model(model_name, model_dir='models/whisper', log_callback=None):
    """Tải model Whisper về thư mục local."""
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
