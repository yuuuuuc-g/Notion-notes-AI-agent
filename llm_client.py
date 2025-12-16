import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

def get_completion(prompt):
    """
    发送 Prompt 给 DeepSeek，返回纯文本回复
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # 低温，让它处理数据更严谨
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ LLM 调用失败: {e}")
        return ""