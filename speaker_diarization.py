import os
import re
import json

def parse_transcript(filepath):
    """Đọc file transcript và gom lại thành list of segments."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    segments = []
    current_time = ""
    current_text = []
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            if current_time and current_text:
                segments.append({
                    "time": current_time,
                    "text": " ".join(current_text)
                })
                current_time = ""
                current_text = []
            continue
            
        if "-->" in line:
            if current_time and current_text:
                segments.append({
                    "time": current_time,
                    "text": " ".join(current_text)
                })
                current_text = []
            current_time = line
        else:
            current_text.append(line)
            
    if current_time and current_text:
        segments.append({
            "time": current_time,
            "text": " ".join(current_text)
        })
        
    return segments

def extract_anchors(segments):
    """Dùng Regex phân tích các điểm neo ngữ cảnh (lời mời, giới thiệu)."""
    anchors = []
    for seg in segments:
        text = seg["text"]
        
        # Phát hiện tự giới thiệu
        intro = re.search(r'(tên là|mình là|tự giới thiệu là|xưng là|định danh là)\s+([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯ][a-zàáâãèéêìíòóôõùúăđĩũơư\s]{1,15})', text)
        if intro:
            anchors.append({"time": seg["time"], "type": "Tự giới thiệu", "name": intro.group(2).strip()})
        
        # Phát hiện lời mời
        invite = re.search(r'(mời\s+(thầy|cô|lý|anh|chị|chú|bác)\s+([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯ][a-zàáâãèéêìíòóôõùúăđĩũơư\s]{1,15}))', text, re.IGNORECASE)
        if invite:
            anchors.append({"time": seg["time"], "type": "Lời mời / Chuyển lượt", "name": invite.group(1).strip()})
            
    return anchors

def chunk_segments(segments, chunk_size=50):
    """Chia nhỏ segments thành các chunk để không tràn token của LLM."""
    return [segments[i:i + chunk_size] for i in range(0, len(segments), chunk_size)]

def process_transcript(input_txt_path, output_txt_path, api_key, model_name='gemini-2.5-flash', log_callback=None, progress_callback=None):
    """Luồng chính: Nhận diện người nói bằng Gemini 1.5 Flash."""
    try:
        import google.generativeai as genai
    except ImportError:
        if log_callback:
            log_callback("❌ Chưa cài thư viện google-generativeai. Vui lòng chạy pip install google-generativeai.")
        return False

    if not api_key:
        if log_callback:
            log_callback("❌ Chưa nhập Gemini API Key trong phần Cài đặt!")
        return False

    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config={
            "temperature": 0.3,
            "top_p": 0.9,
            "response_mime_type": "application/json",
        }
    )

    segments = parse_transcript(input_txt_path)
    if not segments:
        if log_callback:
            log_callback("⚠️ File transcript trống hoặc sai định dạng!")
        return False

    anchors = extract_anchors(segments)
    chunks = chunk_segments(segments, chunk_size=40)
    
    total_chunks = len(chunks)
    annotated_results = []
    
    if log_callback:
        mode = "Phân tích & Dịch thuật" if target_lang else "Phân tích Người nói"
        log_callback(f"🧠 Bắt đầu gửi qua AI để {mode} ({total_chunks} phần)...")

    if target_lang and target_lang not in ["Auto-detect (Tự động)", "Tự động", "auto", ""]:
        translation_instruction = f"BẠN CẦN PHẢI DỊCH TOÀN BỘ NỘI DUNG VĂN BẢN SANG NGÔN NGỮ: '{target_lang}'."
    else:
        translation_instruction = "QUAN TRỌNG: KHÔNG ĐƯỢC dịch nội dung, BẮT BUỘC phải giữ nguyên ngôn ngữ gốc của văn bản (text)."

    if diarize:
        system_instruction = (
            "Bạn là một chuyên gia phân tích hội thoại. Nhiệm vụ của bạn là gán tên người nói cho "
            "từng đoạn văn bản dựa trên mốc thời gian. Hãy dựa vào văn cảnh (lời chào, tự giới thiệu, lời mời) "
            "để suy luận tên người nói. Dữ liệu trả về BẮT BUỘC phải là mảng JSON chứa các object: "
            '[{"time": "00:00:00 --> 00:00:05", "speaker": "Tên Người Nói", "text": "Nội dung..."}]. '
            "Nếu không xác định được tên thật, hãy dùng các nhãn như 'Host', 'Người tham gia', 'Speaker A'. "
            f"{translation_instruction}"
        )
    else:
        system_instruction = (
            "Nhiệm vụ của bạn là định dạng và xử lý lại đoạn transcript. Dữ liệu trả về BẮT BUỘC phải là mảng JSON chứa các object: "
            '[{"time": "00:00:00 --> 00:00:05", "speaker": "Speaker", "text": "Nội dung..."}]. '
            "Hãy giữ nguyên các mốc thời gian và đặt tên speaker mặc định là 'Speaker'. "
            f"{translation_instruction}"
        )

    for i, chunk in enumerate(chunks):
        formatted_transcript = ""
        for seg in chunk:
            formatted_transcript += f"[{seg['time']}] {seg['text']}\n"
            
        user_prompt = f"""
        HƯỚNG DẪN:
        Dưới đây là một số manh mối (anchors) mà hệ thống tự động trích xuất được từ toàn bộ video để giúp bạn tham chiếu:
        {json.dumps(anchors, ensure_ascii=False, indent=2)}
        
        NHIỆM VỤ:
        Gán tên người nói cho đoạn transcript sau:
        {formatted_transcript}
        """
        
        max_retries = 3
        retry_count = 0
        success = False
        
        while retry_count < max_retries and not success:
            try:
                # Truyền system instruction vào chung nội dung
                response = model.generate_content(system_instruction + "\n\n" + user_prompt)
                clean_text = response.text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                elif clean_text.startswith("```"):
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()
                
                chunk_result = json.loads(clean_text)
                
                # Gộp kết quả
                if isinstance(chunk_result, list):
                    annotated_results.extend(chunk_result)
                    
                # Cập nhật tiến độ %
                if progress_callback:
                    percent = int(((i + 1) / total_chunks) * 100)
                    progress_callback(percent)
                    
                # Tránh Rate Limit của Gemini Free Tier (15 RPM -> nghỉ 4.5s mỗi request)
                import time
                time.sleep(4.5)
                success = True
                    
            except Exception as e:
                err_msg = str(e)
                import time
                import re
                
                if "429" in err_msg or "Quota exceeded" in err_msg:
                    # Lỗi vượt quá Rate Limit, tìm thời gian cần đợi
                    wait_time = 60 # Mặc định đợi 60s
                    match = re.search(r"retry in (\d+\.?\d*)s", err_msg)
                    if match:
                        wait_time = float(match.group(1)) + 1.0 # Cộng 1s an toàn
                        
                    if log_callback:
                        log_callback(f"⏳ Quá giới hạn API ở đoạn {i+1}. Tạm nghỉ {wait_time:.1f}s để hồi phục (thử lại lần {retry_count+1}/3)...")
                    time.sleep(wait_time)
                    retry_count += 1
                else:
                    if log_callback:
                        log_callback(f"⚠️ Cảnh báo: Lỗi phân tích ở đoạn {i+1}/{total_chunks}. Chi tiết: {err_msg}")
                    
                    with open(output_txt_path + ".error.log", "a", encoding="utf-8") as f_err:
                        f_err.write(f"Chunk {i+1} error: {err_msg}\n")
                    break # Thoát vòng lặp while, không retry nếu không phải lỗi 429
                    
        if not success:
            # Fallback nếu vượt quá số lần thử hoặc lỗi không mong muốn
            for seg in chunk:
                annotated_results.append({
                    "time": seg["time"],
                    "speaker": "Chưa xác định",
                    "text": seg["text"]
                })
                
    # Ghi ra file
    os.makedirs(os.path.dirname(output_txt_path), exist_ok=True)
    with open(output_txt_path, 'w', encoding='utf-8') as f:
        f.write("# Transcript đã gán nhãn người nói bằng Hybrid AI (Gemini Flash)\n\n")
        for item in annotated_results:
            time_val = item.get("time", "")
            speaker_val = item.get("speaker", "Unknown")
            text_val = item.get("text", "")
            
            f.write(f"{time_val}\n")
            f.write(f"[{speaker_val}]: {text_val}\n\n")
            
    if log_callback:
        log_callback(f"✅ Đã phân tích xong người nói! Lưu tại: {os.path.basename(output_txt_path)}")
        
    return True
