import re

def clean_video_title(title):
    """
    Loại bỏ các thông số kỹ thuật, hậu tố phụ (Official Video, [ID], HD, 1080p...)
    và các thông số tương tác (views, reactions...) để chỉ giữ lại tiêu đề nội dung chính.
    """
    original_title = title
    
    # 1. Loại bỏ ID YouTube trong ngoặc vuông (thường gặp khi download hoặc crawl)
    title = re.sub(r'\[[a-zA-Z0-9_-]{11}\]', '', title)
    
    # 2. Loại bỏ các cụm ngoặc vuông hoặc ngoặc đơn chứa từ khóa kỹ thuật/phụ trợ
    keywords = [
        r'official\s+video', r'official\s+music\s+video', r'official\s+audio', r'official\s+mv', r'mv',
        r'lyrics', r'lyric\s+video',
        r'full\s+hd', r'1080p', r'720p', r'4k', r'hd',
        r'karaoke', r'beat', r'instrumental',
        r'live\s+performance', r'live',
        r'cover', r'teaser', r'trailer', r'audio', r'video'
    ]
    
    def replace_brackets(match):
        content = match.group(1).lower()
        for kw in keywords:
            if re.search(kw, content):
                return ""
        return match.group(0)
        
    title = re.sub(r'\(([^)]+)\)', replace_brackets, title)
    title = re.sub(r'\[([^\]]+)\]', replace_brackets, title)
    
    # 3. Loại bỏ các thông số tương tác (views, reactions, comments, thích, bình luận, v.v.)
    metrics_pattern = r'\d+(?:\.\d+)?[KMB]?(?:\s*lượt\s*xem|\s*views?|\s*reactions?|\s*comments?|\s*shares?|\s*thích|\s*bình\s*luận|\s*chia\s*sẻ)\b'
    title = re.sub(metrics_pattern, '', title, flags=re.IGNORECASE)
    
    # 4. Hậu tố sau gạch đứng, gạch ngang
    suffix_pattern = r'\s+[-|_+:·•]\s*(?:official\s+(?:music\s+)?video|official\s+audio|lyrics?|full\s+hd|1080p|720p|4k|mv|karaoke|beat|audio|video)\s*$'
    title = re.sub(suffix_pattern, '', title, flags=re.IGNORECASE)
    
    # 5. Loại bỏ các ký tự dấu phân cách dư thừa
    title = re.sub(r'\s*[·•\-|_]\s*', ' ', title)
    title = re.sub(r'\s+', ' ', title)
    
    cleaned = title.strip()
    if not cleaned:
        return original_title
    return cleaned

def sanitize_filename(name):
    """Làm sạch tên file để tránh các ký tự không hợp lệ trên hệ điều hành."""
    cleaned = clean_video_title(name)
    cleaned = re.sub(r'[\\/*?:"<>|]', '', cleaned)
    return cleaned.strip()[:80]

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
