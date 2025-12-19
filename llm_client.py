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
    用于：分类、简单提取、JSON格式化
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, 
            stream=False,
            # V3 不需要思考，8192 足够写出非常长的 JSON
            max_tokens=8192 
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
        print("🤔 R1 正在深度思考 (Deep Thinking)...")
        # 注意：DeepSeek 的 reasoning 过程是计入输出 token 的
        # 我们必须把它拉到最大，防止思考太久导致 JSON 没写完
        response = client.chat.completions.create(
            model="deepseek-reasoner", 
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192  # 🔥 关键修改：拉满到 8k
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
        # 如果 R1 还是不行，自动降级用 V3 (V3 不思考直接写，反而不容易截断)
        print("🔄 尝试降级使用 DeepSeek-V3...")
        return get_completion(prompt), "（降级为 V3，无思考过程）"
