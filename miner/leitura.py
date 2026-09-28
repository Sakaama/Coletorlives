# -*- coding: utf-8 -*-
import os
import json
import uuid
import datetime
import requests
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types
from miner.cloud_db import get_firestore_service

def get_subtitles(url):
    # Extract video id
    parsed = urlparse(url)
    video_id = ''
    if parsed.hostname in ('youtu.be', 'www.youtu.be'):
        video_id = parsed.path[1:]
    else:
        qs = parse_qs(parsed.query)
        if 'v' in qs:
            video_id = qs['v'][0]
    
    if not video_id:
        raise Exception("Nao foi possivel identificar o video_id na URL fornecida.")
        
    title = 'Video Sem Titulo'
    try:
        r = requests.get(f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json', timeout=10)
        if r.status_code == 200:
            title = r.json().get('title', title)
    except Exception as e:
        print("Aviso: Falha ao obter titulo:", e)
        
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        
        try:
            transcript = transcript_list.find_transcript(['pt', 'en', 'es'])
        except:
            transcript = list(transcript_list)[0]
            
        data = transcript.fetch()
        
        clean_lines = []
        for item in data:
            line = item['text'].replace('\n', ' ').strip()
            if not clean_lines or clean_lines[-1] != line:
                clean_lines.append(line)
                
        return title, video_id, '\n'.join(clean_lines)
    except Exception as e:
        raise Exception(f"Falha ao baixar legendas via API do YouTube: {e}")

def analyze_transcript(transcript_text, api_key):
    client = genai.Client(api_key=api_key)
    prompt = f"""Voce eh um especialista em curadoria de clipes curtos (TikTok, Reels, Shorts).
Sua missao eh ler essa transcricao e identificar de 1 a 3 momentos brilhantes que se encaixam no DNA Editorial:
- Premissa (gancho forte inicial)
- Responsabilidade (o criador assume uma posicao ou da uma opiniao)
- Desvantagem (um conflito ou problema relatado)
- Revelacao (um plot twist, conclusao ou punchline)

Retorne EXATAMENTE um array JSON neste formato:
[
  {{
    "title": "titulo curto do clipe",
    "justification": "por que esse clipe eh bom baseado no DNA",
    "quote": "a frase exata que resume o clipe"
  }}
]

Transcricao (trecho):
{transcript_text[:20000]}"""
    
    response = client.models.generate_content(
        model='gemini-2.5-pro',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type='application/json'
        ),
    )
    return response.text

def leitura_expressa(url, campaign="GabePeixe"):
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise Exception('GEMINI_API_KEY nao configurada no servidor.')
        
    source_title, vod_id, text = get_subtitles(url)
    
    llm_output = analyze_transcript(text, api_key)
    try:
        clips_data = json.loads(llm_output)
    except:
        raise Exception("Gemini nao retornou um JSON valido.")
        
    db = get_firestore_service()
    
    items = []
    for c in clips_data:
        clip_id = str(uuid.uuid4())[:8]
        raw_clip = {
            "id": clip_id,
            "vod_id": vod_id,
            "campaign": campaign,
            "title": c.get("title", "Sem titulo"),
            "hook": c.get("quote", ""),
            "justification": c.get("justification", ""),
            "score": 90,
            "classification": "SHORTLIST",
            "status": "PENDENTE",
            "start_formatted": "00:00:00",
            "end_formatted": "00:01:00",
            "duration_formatted": "1m 00s",
            "visual_activity": "Media",
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
