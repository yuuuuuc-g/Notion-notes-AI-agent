import PyPDF2
import io

def read_pdf_content(uploaded_file):
    """
    读取 Streamlit 上传的 PDF 文件并提取文本
    """
    print(f"📂 Processing PDF: {uploaded_file.name}...")
    try:
        # 1. 重置文件指针 (关键)
        uploaded_file.seek(0)
        
        # 2. 读取 PDF
        reader = PyPDF2.PdfReader(uploaded_file)
        text = []
        
        # 3. 遍历提取
        for i, page in enumerate(reader.pages):
            content = page.extract_text()
            if content:
                text.append(content)
        
        full_text = "\n".join(text)
        
        # 4. 检查是否为空 (可能是扫描版图片PDF)
        if len(full_text.strip()) < 20:
            print("⚠️ PDF parsed but text is empty (Might be an image scan).")
            return None
            
        print(f"✅ PDF loaded. Length: {len(full_text)} chars.")
        return full_text

    except Exception as e:
        print(f"❌ PDF Read Error: {e}")
        return None