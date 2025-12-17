import requests
import re
import json
import yt_dlp

def get_video_id(url):
    """从 YouTube URL 中提取视频 ID"""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
        r"(?:embed\/)([0-9A-Za-z_-]{11})"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def fetch_youtube_content(url):
    """
    专门处理 YouTube 视频：使用 yt-dlp
    """
    print(f"📺 YouTube video detected, starting yt-dlp engine...")
    
    # 配置 yt-dlp：不下载视频，只获取元数据
    ydl_opts = {
        'skip_download': True,  # 不下载视频
        'quiet': True,          # 安静模式，少输出废话
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 1. 提取视频信息
            info = ydl.extract_info(url, download=False)
            
            # 2. 寻找字幕
            # yt-dlp 把字幕分两类：subtitles (人工上传) 和 automatic_captions (自动生成)
            # 我们优先找人工的，没有再找自动的
            subtitles = info.get('subtitles', {})
            auto_captions = info.get('automatic_captions', {})
            
            # 定义我们想要的语言优先级
            langs = ['es', 'en', 'zh-Hans', 'zh-Hant']
            
            target_url = None
            found_lang = None

            # 策略：先在【人工字幕】里找
            for lang in langs:
                if lang in subtitles:
                    # 寻找 json3 格式 (最容易解析)，没有就拿第一个
                    for fmt in subtitles[lang]:
                        if fmt['ext'] == 'json3':
                            target_url = fmt['url']
                            found_lang = lang
                            break
                    if target_url: break
            
            # 策略：如果没找到，去【自动字幕】里找
            if not target_url:
                for lang in langs:
                    if lang in auto_captions:
                        for fmt in auto_captions[lang]:
                            if fmt['ext'] == 'json3':
                                target_url = fmt['url']
                                found_lang = lang + " (Auto)"
                                break
                        if target_url: break
            
            # 策略：如果还是没找到，就随便拿一个自动字幕（通常是原声的自动生成）
            if not target_url and auto_captions:
                first_lang = list(auto_captions.keys())[0]
                target_url = auto_captions[first_lang][0]['url']
                found_lang = first_lang + " (Fallback)"

            if not target_url:
                return f"⚠️ No subtitles found for this video...\n视频标题：{info.get('title')}\n简介：{info.get('description')}"

            # 3. 下载并解析字幕数据
            print(f"✅ Subtitle source locked({found_lang})，downloading...")
            # yt-dlp 的 json3 格式非常标准，直接请求 URL 即可
            subs_json = requests.get(target_url).json()
            
            # 4. 拼接字幕文本
            # json3 结构: {'events': [{'tStartMs': 1000, 'dDurationMs': 2000, 'segs': [{'utf8': '文本'}]}]}
            full_text = []
            if 'events' in subs_json:
                for event in subs_json['events']:
                    if 'segs' in event:
                        # 把这一句里的所有片段拼起来
                        line = "".join([seg['utf8'] for seg in event['segs'] if 'utf8' in seg])
                        if line.strip() and line != '\n':
                            full_text.append(line.strip())
            
            final_text = "\n".join(full_text)
            
            # 长度截断保护
            if len(final_text) > 15000:
                final_text = final_text[:15000] + "\n...(字幕过长已截断)"
                
            return f"【来源：YouTube 字幕 (由 yt-dlp 提取 - {found_lang})】\n{final_text}"

    except Exception as e:
        print(f"❌ yt-dlp extraction failed: {e}")
        # 最后的保底：还是去抓网页文字
        return fetch_url_content_fallback(url)

def fetch_url_content_fallback(url):
    """Jina 备用抓取"""
    jina_url = f"https://r.jina.ai/{url}"
    try:
        response = requests.get(jina_url, timeout=30)
        return f"【来源：网页抓取（无字幕）】\n{response.text[:10000]}"
    except Exception as e:
        return f"❌ 抓取彻底失败: {e}"

def fetch_url_content(url):
    print(f"🌐 Web Analyst is analyzing link: {url} ...")
    if "youtube.com" in url or "youtu.be" in url:
        return fetch_youtube_content(url)
    return fetch_url_content_fallback(url)