import fitz  # PyMuPDF

def read_pdf_content(uploaded_file):
    """
    读取 Streamlit 上传的 PDF 文件并转换为文本
    """
    print(f"📂 正在解析 PDF 文件: {uploaded_file.name}...")
    try:
        # 1. 读取二进制流
        bytes_data = uploaded_file.read()
        
        # 2. 使用 fitz 打开
        # stream 参数允许直接从内存读取，不需要存到硬盘
        doc = fitz.open(stream=bytes_data, filetype="pdf")
        
        text_content = []
        # 3. 遍历每一页提取文本
        for page in doc:
            text_content.append(page.get_text())
            
        full_text = "\n".join(text_content)
        
        print(f"✅ PDF parsed successfully. Total pages: {len(doc)}. Characters extracted: {len(full_text)}")
        return f"【来源：PDF 文件 ({uploaded_file.name})】\n{full_text}"
        
    except Exception as e:
        print(f"❌ PDF 解析失败: {e}")
        return None