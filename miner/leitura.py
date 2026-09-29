# -*- coding: utf-8 -*-
import os
import re
import json
import uuid
import datetime
import urllib.request
import requests
import http.cookiejar
from google import genai
from google.genai import types
from miner.cloud_db import get_firestore_service
from youtube_transcript_api import YouTubeTranscriptApi

def get_subtitles(url, cookies_txt="", subtitle_text=""): 
    # Extract video ID
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    video_id = match.group(1) if match else url

    # Fetch Title
    title = "Sem Título"
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        with urllib.request.urlopen(oembed_url) as response:
            metadata = json.loads(response.read())
            title = metadata.get('title', 'Sem Título')
    except Exception as e:
        print(f"Warning: Could not fetch title via oembed: {e}")

    if subtitle_text:
        return title, video_id, subtitle_text

    # Fetch Transcript
    session = requests.Session()
    if cookies_txt:
        cj = http.cookiejar.MozillaCookieJar()
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(cookies_txt)
            tmpname = f.name
        try:
            cj.load(tmpname, ignore_discard=True, ignore_expires=True)
            session.cookies.update(cj)
        except Exception as e:
            print(f"Warning: Failed to load cookies: {e}")
        finally:
            try:
                os.remove(tmpname)
            except:
                pass

    api = YouTubeTranscriptApi(http_client=session)
    try:
        transcript_list = api.list(video_id)
        try:
            transcript = transcript_list.find_transcript(['pt', 'en'])
        except:
            transcript = transcript_list.find_generated_transcript(['pt', 'en'])
            
        fetched = transcript.fetch()
        
        lines = []
        for snippet in fetched:
            text = snippet.get('text', '')
            if text:
                lines.append(text)
                
        full_text = '\n'.join(lines)
    except Exception as e:
        raise Exception(f"Falha ao extrair legendas via API direta: {str(e)}")
        
    return title, video_id, full_text

def analyze_transcript(transcript_text, api_key):
    client = genai.Client(api_key=api_key)
    prompt = f"""Você é um especialista em curadoria de clipes curtos (TikTok, Reels, Shorts).
Sua missão é ler essa transcrição e identificar de 1 a 3 momentos brilhantes que se encaixam no DNA Editorial:
- Premissa (gancho forte inicial)
- Responsabilidade (o criador assume uma posição/dá uma opinião)
- Desvantagem (um conflito ou problema relatado)
- Revelação (um plot twist, conclusão ou punchline)

Retorne EXATAMENTE um array JSON neste formato:
[
  {{
    "title": "titulo curto do clipe",
    "justification": "por que esse clipe e bom baseado no DNA",
    "quote": "a frase exata que resume o clipe"
  }}
]

Transcrição (trecho):
{transcript_text[:20000]}"""
    
    response = client.models.generate_content(
        model='gemini-3.1-pro-preview',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type='application/json'
        ),
    )
    return response.text

def leitura_expressa(url, campaign="GabePeixe", cookies_txt="", subtitle_text="", service=None):
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise Exception('GEMINI_API_KEY não configurada no servidor.')
        
    source_title, vod_id, text = get_subtitles(url, cookies_txt, subtitle_text)
    
    llm_output = analyze_transcript(text, api_key)
    try:
        clips_data = json.loads(llm_output)
    except:
        raise Exception("Gemini não retornou um JSON válido.")
        
    db = get_firestore_service()
    if service:
        import datetime
        vod, known = service.create_vod(
            campaign,
            url,
            {
                "url": url,
                "platform": "YouTube",
                "title": source_title,
                "eligibility": {"status": "PERMITIDA", "reasons": []},
                "date": datetime.datetime.utcnow().date().isoformat(),
                "duration": 0,
                "channel": "Desconhecido",
                "was_live": True,
            },
        )
        vod_id = vod["id"]
        
        found = []
        for i, c in enumerate(cortes):
            clip_id = str(i+1)
            found.append({
                "start": 0.0,
                "end": 60.0,
                "score": 90,
                "title": c.get("title", "Sem titulo"),
                "quote": c.get("quote", ""),
                "justification": c.get("justification", ""),
            })
            
        service.save_analysis(vod_id, found, warnings=[], metrics={}, model="gemini-3.1-pro-preview", mode="express", has_segments=False)
        return {"vod_id": vod_id}

    items = []

    for c in clips_data:
        clip_id = str(uuid.uuid4())[:8]
        raw_clip = {
            "id": clip_id,
            "vod_id": vod_id,
            "url": url,
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
