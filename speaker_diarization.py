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

def process_transcript(input_txt_path, output_txt_path, log_callback=None, progress_callback=None, target_lang=None, diarize=False, cancel_event=None):
    """Luồng chính: Nhận diện người nói bằng AI Fallback Matrix."""
    try:
        import google.generativeai as genai
    except ImportError:
        if log_callback:
            log_callback("❌ Chưa cài thư viện google-generativeai. Vui lòng chạy pip install google-generativeai.")
        return False

    import ai_manager
    aim = ai_manager.AIManager()

    segments = parse_transcript(input_txt_path)
    if not segments:
        if log_callback:
            log_callback("⚠️ File transcript trống hoặc sai định dạng!")
        return False

    anchors = extract_anchors(segments)
    chunk_size = 60 if target_lang and target_lang not in ["Auto-detect (Tự động)", "Tự động", "auto", ""] else 150
    chunks = chunk_segments(segments, chunk_size=chunk_size)
    
    total_chunks = len(chunks)
    annotated_results = []
    
    if log_callback:
        mode = "Phân tích & Dịch thuật" if target_lang else "Phân tích Người nói"
        log_callback(f"🧠 Bắt đầu gửi qua AI để {mode} ({total_chunks} phần)...")

    is_translation = target_lang and target_lang not in ["Auto-detect (Tự động)", "Tự động", "auto", ""]
    if is_translation:
        translation_instruction = f"BẠN CẦN PHẢI DỊCH TOÀN BỘ NỘI DUNG VĂN BẢN SANG NGÔN NGỮ: '{target_lang}'."
    else:
        translation_instruction = "QUAN TRỌNG: KHÔNG ĐƯỢC dịch nội dung, BẮT BUỘC phải giữ nguyên ngôn ngữ gốc của văn bản (text)."

    if diarize:
        if is_translation:
            system_instruction = (
                "Bạn là một chuyên gia phân tích hội thoại. Nhiệm vụ của bạn là gán tên người nói cho "
                "từng đoạn văn bản dựa trên mốc thời gian và DỊCH nội dung. Hãy dựa vào văn cảnh "
                "để suy luận tên người nói. Dữ liệu trả về BẮT BUỘC phải là mảng JSON chứa các object: "
                '[{"id": 1, "speaker": "Tên Người Nói", "text": "Nội dung dịch..."}]. '
                "Nếu không xác định được tên thật, hãy dùng 'Host', 'Khách mời'. "
                f"{translation_instruction}"
            )
        else:
            system_instruction = (
                "Bạn là một chuyên gia phân tích hội thoại. Nhiệm vụ của bạn là gán tên người nói cho "
                "từng đoạn văn bản được đánh số [ID]. Hãy dựa vào văn cảnh để suy luận tên người nói. "
                "ĐỂ TIẾT KIỆM TOKEN, BẠN CHỈ TRẢ VỀ ID VÀ SPEAKER. Dữ liệu trả về BẮT BUỘC phải là mảng JSON: "
                '[{"id": 1, "speaker": "Tên Người Nói"}, {"id": 2, "speaker": "Host"}]. '
                "Tuyệt đối KHÔNG trả về nội dung (text) hay thời gian. "
                "Nếu không xác định được tên thật, hãy dùng 'Host', 'Khách mời'. "
                f"{translation_instruction}"
            )
    else:
        if is_translation:
            system_instruction = (
                "Nhiệm vụ của bạn là dịch đoạn transcript. Dữ liệu trả về BẮT BUỘC phải là mảng JSON chứa các object: "
                '[{"id": 1, "speaker": "Speaker", "text": "Nội dung dịch..."}]. '
                "Đặt tên speaker mặc định là 'Speaker'. "
                f"{translation_instruction}"
            )
        else:
            system_instruction = (
                "Nhiệm vụ của bạn là định dạng đoạn transcript. CHỈ TRẢ VỀ ID VÀ SPEAKER. Dữ liệu trả về BẮT BUỘC phải là mảng JSON: "
                '[{"id": 1, "speaker": "Speaker"}]. '
                "Đặt tên speaker mặc định là 'Speaker'. Tuyệt đối KHÔNG trả về text hay time. "
                f"{translation_instruction}"
            )

    for i, chunk in enumerate(chunks):
        if cancel_event and cancel_event.is_set():
            if log_callback:
                log_callback("🛑 Đã hủy tiến trình phân tích AI.")
            break
            
        formatted_transcript = ""
        for idx, seg in enumerate(chunk):
            formatted_transcript += f"[ID: {idx+1}] [{seg['time']}] {seg['text']}\n"
            
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
                # Gọi qua AIManager để xử lý cơ chế multi-model fallback
                clean_text = aim.generate_diarization(system_instruction, user_prompt, log_callback, cancel_event)
                if not clean_text:
                    raise Exception("Không thể nhận kết quả từ AI Manager.")
                    
                chunk_result = json.loads(clean_text)
                
                # Gộp kết quả và map lại thời gian/văn bản
                if isinstance(chunk_result, list):
                    for item in chunk_result:
                        idx = item.get("id")
                        if isinstance(idx, int) and 1 <= idx <= len(chunk):
                            seg = chunk[idx - 1]
                            annotated_results.append({
                                "time": seg["time"],
                                "speaker": item.get("speaker", "Speaker"),
                                "text": item.get("text") if is_translation else seg["text"]
                            })
                    
                # Cập nhật tiến độ %
                if progress_callback:
                    percent = int(((i + 1) / total_chunks) * 100)
                    progress_callback(percent)
                    
                success = True
                    
            except Exception as e:
                err_msg = str(e)
                if log_callback:
                    log_callback(f"⚠️ Lỗi phân tích: {err_msg}")
                    
                # Nếu lỗi không phải rate limit (vì AIManager đã xử lý chuyển model cho rate limit)
                if "tất cả các model đều quá tải" in err_msg.lower() or "không có api key" in err_msg.lower():
                    # Đợi 10s rồi thử lại vòng lặp ngoài cùng của file này (để AIManager có thời gian ping)
                    import time
                    if cancel_event:
                        if cancel_event.wait(10.0):
                            break
                    else:
                        time.sleep(10.0)
                    retry_count += 1
                else:
                    break # Lỗi parse json, v.v. thì fallback luôn
                    
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
