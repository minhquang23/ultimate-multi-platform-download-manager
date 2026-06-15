import yt_dlp
import json

url = "https://www.youtube.com/watch?v=MhkLJo6piNo" # the video from user's screenshot
ydl_opts = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(url, download=False)
    
    subs = list(info.get('subtitles', {}).keys())
    auto_subs = list(info.get('automatic_captions', {}).keys())
    
    data = {
        'language': info.get('language'),
        'subtitles': subs,
        'automatic_captions': auto_subs[:10], # limit to 10 for brevity
    }
    
    print(json.dumps(data, indent=2))
