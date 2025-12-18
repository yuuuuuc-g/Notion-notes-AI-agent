import json
import asyncio
import edge_tts
import os
from pydub import AudioSegment
from llm_client import get_reasoning_completion # 用 R1 写剧本！

# --- 🎭 声音卡司 (Cast) ---
# 主持人: 墨西哥女声 (热情)
VOICE_HOST = "es-MX-DaliaNeural" 
# 嘉宾: 哥伦比亚男声 (清晰)
VOICE_GUEST = "es-CO-GonzaloNeural"

RATE = "+0%"

def generate_podcast_script(content):
    """
    让 R1 编写双人对话剧本
    """
    print("🎙️ R1 正在构思播客剧本 (Mexican & Colombian)...")
    
    prompt = f"""
    You are a scriptwriter for a Spanish learning podcast.
    
    【Content Source】
    {content[:10000]}
    
    【Roles】
    - **Host (Sofía)**: From Mexico. Energetic, curious. Uses Mexican phrases like "Órale", "¿Mande?".
    - **Expert (Mateo)**: From Colombia. Calm, knowledgeable. Uses Colombian phrasing occasionally (like "Parce" in informal contexts, but keeps it professional).
    
    【Task】
    Create a 2-minute dialogue script discussing the content.
    - If the content is Spanish grammar: Explain it clearly with examples.
    - If the content is General Knowledge (e.g., DeepSeek): Discuss its impact in Spanish.
    
    【Format】
    Strictly JSON list:
    [
        {{"speaker": "Host", "text": "¡Hola a todos! Bienvenidos a nuestro podcast. ¡Órale! Hoy tenemos un tema fascinante."}},
        {{"speaker": "Guest", "text": "Hola Sofía. Sí, es un placer estar aquí para hablar de esto."}}
    ]
    """
    
    # 使用 R1 生成
    content, _ = get_reasoning_completion(prompt)
    
    # 清洗 JSON
    try:
        clean_json = content.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"❌ 剧本解析失败: {e}")
        return []

async def _gen_segment(text, voice, filename):
    communicate = edge_tts.Communicate(text, voice, rate=RATE)
    await communicate.save(filename)

async def create_audio_from_script(script, output_file="podcast.mp3"):
    """
    异步生成音频
    """
    if not script: return None
    
    combined = AudioSegment.empty()
    # 稍微重叠一点点或者紧凑一点，更有对话感
    pause = AudioSegment.silent(duration=300) 
    
    temp_files = []
    
    print(f"🎧 正在录制 {len(script)} 个对话片段...")
    
    for i, line in enumerate(script):
        speaker = line.get('speaker')
        text = line.get('text')
        
        # 分配声音
        voice = VOICE_HOST if speaker == "Host" else VOICE_GUEST
        
        temp_file = f"temp_{i}.mp3"
        await _gen_segment(text, voice, temp_file)
        temp_files.append(temp_file)
        
        seg = AudioSegment.from_mp3(temp_file)
        combined += seg + pause
        
    # 导出
    combined.export(output_file, format="mp3")
    
    # 清理垃圾
    for f in temp_files:
        if os.path.exists(f): os.remove(f)
        
    return output_file

def run_podcast_workflow(text_content):
    """
    主入口：生成剧本 -> 生成音频 -> 返回剧本和音频路径
    """
    # 1. 写剧本
    script = generate_podcast_script(text_content)
    
    if not script:
        return None, None
    
    # 2. 生成音频 (Wrapper for async)
    output_path = "podcast.mp3"
    try:
        asyncio.run(create_audio_from_script(script, output_path))
        return script, output_path
    except Exception as e:
        print(f"❌ 音频生成失败 (可能是缺少 ffmpeg): {e}")
        # 即使音频失败，剧本也是有价值的，返回剧本
        return script, None