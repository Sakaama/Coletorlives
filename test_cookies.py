import tempfile
import os
from youtube_transcript_api import YouTubeTranscriptApi

with open('user_cookies.txt', 'r', encoding='utf-8') as f:
    cookies_txt = f.read()

with tempfile.TemporaryDirectory() as tmpdir:
    cookie_path = os.path.join(tmpdir, 'cookies.txt')
    with open(cookie_path, 'w', encoding='utf-8') as f:
        f.write(cookies_txt)
        
    try:
        transcript = YouTubeTranscriptApi.get_transcript('7xwkE1FxxJg', languages=['pt', 'en'], cookies=cookie_path)
        print("SUCCESS!")
        print(transcript[:2])
    except Exception as e:
        print("ERROR:", str(e))
