import PyPDF2
import io

def read_pdf_content(uploaded_file):
    """
    读取 Streamlit 上传的 PDF 文件并提取文本
    """
    try:
        # 必须重置指针，防止读取空内容
        uploaded_file.seek(0)
        
        reader = PyPDF2.PdfReader(uploaded_file)
        text = []
        
        # 遍历每一页提取文本
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text.append(content)
        
        full_text = "\n".join(text)
        
        # 如果提取出的内容太少（说明可能是纯图片PDF），则报错
        if len(full_text.strip()) < 50:
            return None
            
        return full_text
    except Exception as e:
        print(f"❌ PDF Read Error: {e}")
        return None