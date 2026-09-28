# -*- coding: utf-8 -*-
import os
import re
import json
import subprocess
import tempfile
import uuid
import datetime
from google import genai
from google.genai import types
from miner.cloud_db import get_firestore_service

def get_subtitles(url, cookies_txt=""): 
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            'yt-dlp',
            '--js-runtime', 'node',
            '--write-auto-subs',
            '--write-subs',
            '--sub-lang', 'pt,en',
            '--skip-download',
            '--dump-json',
            '-o', os.path.join(tmpdir, '%(id)s.%(ext)s'),
            url
        ]
        if cookies_txt:
            cookie_path = os.path.join(tmpdir, 'cookies.txt')
            with open(cookie_path, 'w', encoding='utf-8') as cf:
                cf.write(cookies_txt)
            cmd.insert(1, '--cookies')
            cmd.insert(2, cookie_path)
            
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise Exception('yt-dlp failed: ' + res.stderr)
        
        info = json.loads(res.stdout.splitlines()[0])
        video_id = info.get('id')
        title = info.get('title', '')
        
        vtt_file = None
        for root, dirs, files in os.walk(tmpdir):
            for f in files:
                if f.endswith('.vtt'):
                    vtt_file = os.path.join(root, f)
                    break
        
        if not vtt_file:
            raise Exception('Legendas automǭticas nǜo encontradas para este vdeo.')
            
        with open(vtt_file, 'r', encoding='utf-8') as f:
            vtt_content = f.read()
            
        text = re.sub(r'<[^>]+>', '', vtt_content)
        lines = [line.strip() for line in text.split('\n') if line.strip() and not '-->' in line and not line.strip().isdigit() and line.strip() != 'WEBVTT' and line.strip() != 'Kind: captions' and line.strip() != 'Language: pt' and line.strip() != 'Language: en']
        
        clean_lines = []
        for line in lines:
            if not clean_lines or clean_lines[-1] != line:
                clean_lines.append(line)
                
        return title, video_id, '\n'.join(clean_lines)

def analyze_transcript(transcript_text, api_key):
    client = genai.Client(api_key=api_key)
    prompt = f"""VocǦ Ǹ um especialista em curadoria de clipes curtos (TikTok, Reels, Shorts).
Sua missǜo Ǹ ler essa transcriǜo e identificar de 1 a 3 momentos brilhantes que se encaixam no DNA Editorial:
- Premissa (gancho forte inicial)
- Responsabilidade (o criador assume uma posiǜo/dǭ uma opiniǜo)
- Desvantagem (um conflito ou problema relatado)
- Revelaǜo (um plot twist, conclusǜo ou punchline)

Retorne EXATAMENTE um array JSON neste formato:
[
  {{
    "title": "ttulo curto do clipe",
    "justification": "por que esse clipe Ǹ bom baseado no DNA",
    "quote": "a frase exata que resume o clipe"
  }}
]

Transcriǜo (trecho):
{transcript_text[:20000]}"""
    
    response = client.models.generate_content(
        model='gemini-2.5-pro',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type='application/json'
        ),
    )
    return response.text

def leitura_expressa(url, campaign="GabePeixe", cookies_txt=""):
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise Exception('GEMINI_API_KEY nǜo configurada no servidor.')
        
    source_title, vod_id, text = get_subtitles(url, cookies_txt)
    
    llm_output = analyze_transcript(text, api_key)
    try:
        clips_data = json.loads(llm_output)
    except:
        raise Exception("Gemini nǜo retornou um JSON vǭlido.")
        
    db = get_firestore_service()
    
    items = []
    for c in clips_data:
        clip_id = str(uuid.uuid4())[:8]
        raw_clip = {
            "id": clip_id,
            "vod_id": vod_id,
            "campaign": campaign,
            "title": c.get("title", "Sem ttulo"),
            "hook": c.get("quote", ""),
            "justification": c.get("justification", ""),
            "score": 90,
            "classification": "SHORTLIST",
            "status": "PENDENTE",
            "start_formatted": "00:00:00",
            "end_formatted": "00:01:00",
            "duration_formatted": "1m 00s",
            "visual_activity": "MǸdia",
            "discovered_at": datetime.datetime.utcnow().isoformat(),
            "source_title": source_title
        }
        db.save_raw_clip(raw_clip)
        items.append(raw_clip)
        
    return {
        "count": len(items),
        "summary": {"new": len(items)},
        "items": items,
        "source_url": url
    }
