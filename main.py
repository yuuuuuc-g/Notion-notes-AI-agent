import json
import re
import os
from dotenv import load_dotenv
from llm_client import get_completion
from web_ops import fetch_url_content
import notion_ops  # Import the whole module

# Try to import file_ops, ignore if missing (to avoid local errors)
try:
    from file_ops import read_pdf_content
except ImportError:
    read_pdf_content = None

load_dotenv()

# --- 🧠 Brain A: Classifier (Router) ---
def classify_intent(text):
    prompt = f"""
    Please analyze the content type of the following text.
    First 800 characters: {text[:800]}
    
    Return JSON only, no extra text:
    {{ "type": "Spanish" }}  <- If it relates to Spanish learning (grammar, vocab, subtitles).
    {{ "type": "General" }}  <- Everything else (Tech, News, General Knowledge, English/Chinese videos).
    """
    response = get_completion(prompt)
    # Simple keyword fallback
    if "Spanish" in response:
        return {"type": "Spanish"}
    return {"type": "General"}

# --- 🧠 Brain B: Spanish Processor (Simplified) ---
def generate_spanish_content(text):
    """
    Extracts Spanish words and examples.
    """
    prompt = f"""
    You are a professional Spanish teacher. Please organize this material.
    
    Input content:
    {text[:15000]}
    
    Output JSON format (No Markdown code blocks):
    {{
        "title": "Note Title",
        "summary": "Chinese Summary (within 100 words)",
        "words": [
             {{ "word": "Spanish Word", "meaning": "Chinese Meaning", "example": "Spanish Example Sentence" }},
             ... (Extract 5-10 core words)
        ]
    }}
    """
    response = get_completion(prompt)
    clean_json = response.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean_json)
    except:
        return {"title": "Spanish Note", "summary": "Parsing Failed", "words": []}

# --- 🧠 Brain C: General Knowledge Processor (Fixed Structure) ---
def process_general_knowledge(text):
    """
    General articles/videos: Summary, Tags, Title, Key Points
    """
    prompt = f"""
    You are a professional knowledge management assistant. Analyze the following content:
    
    {text[:15000]} 
    
    Extract the following info and output in strict JSON format:
    1. title: Short and concise title (in Chinese).
    2. summary: Concise summary within 200 words (in Chinese).
    3. tags: 3-5 relevant tags (Array of strings).
    4. key_points: Extract 3-7 core key points or insights (Array of strings).
       - If code/tech: summarize core logic.
       - If opinion: summarize arguments.
       - Keep it concise, 50-100 words per point.
    
    Output Example:
    {{
        "title": "PyTorch Core Principles",
        "summary": "This article explains...",
        "tags": ["AI", "Python", "Deep Learning"],
        "key_points": [
            "Class acts as a container for parameters.",
            "Def defines the calculation flow.",
            "__init__ is for initialization."
        ]
    }}
    """
    
    # Call LLM
    response = get_completion(prompt)
    
    # === Clean and Parse JSON ===
    clean_json = response.replace("```json", "").replace("```", "").strip()
    
    try:
        data = json.loads(clean_json)
        return data
    except json.JSONDecodeError:
        print(f"❌ JSON Parsing Failed. Raw response: {response}")
        # Fallback return
        return {
            "title": "Unnamed Note (Parsing Failed)", 
            "summary": response[:500], 
            "tags": ["Error"],
            "key_points": ["Auto-organization failed, please check summary"] 
        }

# --- 🎩 Main Workflow ---
def main_workflow(user_input=None, uploaded_file=None):
    processed_text = ""
    original_url = None
    
    # === 1. Get Input Content ===
    if uploaded_file and read_pdf_content:
        print("📂 File input detected...")
        content = read_pdf_content(uploaded_file)
        if not content: return
        processed_text = content
    elif user_input:
        # Check if URL
        if user_input.strip().startswith("http"):
            original_url = user_input.strip()
            print(f"🌐 Fetching URL: {original_url}")
            content = fetch_url_content(original_url)
            if not content: return
            processed_text = f"[Source URL] {original_url}\n\n{content}"
        else:
            processed_text = user_input
    else:
        print("⚠️ Empty input")
        return

    # === 2. Route Classification ===
    print("🚦 Analyzing content type (Routing)...")
    intent = classify_intent(processed_text)
    content_type = intent.get('type', 'General')
    print(f"👉 Content type determined: [{content_type}]")

    # === 3. Dispatch Processing ===
    if content_type == 'Spanish':
        print("🇪🇸 Entering Spanish Learning Mode...")
        # Generate data via Brain B
        data = generate_spanish_content(processed_text)
        
        print("✍️ Writing to Notion (Spanish Template)...")
        # Write via notion_ops
        notion_ops.create_study_note(
            title=data.get('title', 'Spanish Note'), 
            summary=data.get('summary', ''), 
            word_list=data.get('words', []), 
            original_url=original_url
        )

    else:
        # === General Knowledge Mode ===
        print("🌍 Entering General Knowledge Mode...")
        
        # 1. Get Dict data directly
        note_data = process_general_knowledge(processed_text)
        
        if note_data:
            print("✍️ Writing to Notion (General Template)...")
            # 2. Pass to notion_ops
            notion_ops.create_general_note(note_data, original_url)

    print("✅ Processing Complete!")

if __name__ == "__main__":
    # For local testing
    pass