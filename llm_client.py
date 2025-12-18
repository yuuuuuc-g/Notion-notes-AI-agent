import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

def get_completion(prompt, model="deepseek-chat"):
    """
    通用快速模式 (DeepSeek-V3)
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, 
            stream=False,
            max_tokens=8000  # 🔼 增加输出上限，防止长文截断
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ V3 调用失败: {e}")
        return ""

def get_reasoning_completion(prompt):
    """
    深度思考模式 (DeepSeek-R1)
    """
    try:
        print("🤔 R1 正在深度思考 (这可能需要一点时间)...")
        response = client.chat.completions.create(
            model="deepseek-reasoner", 
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8000  # 🔼 关键！给思考过程和 JSON 留足空间
        )
        
        # 获取最终回答
        content = response.choices[0].message.content
        
        # 获取思考过程
        reasoning = getattr(response.choices[0].message, 'reasoning_content', None)
        
        if not reasoning:
            reasoning = "（模型未返回显式思考过程）"
            
        return content, reasoning
        
    except Exception as e:
        print(f"❌ R1 调用失败: {e}")
        # 如果 R1 挂了，降级用 V3
        return get_completion(prompt), "（降级为 V3，无思考过程）"
