import re
import time
from pathlib import Path
from pypdf import PdfReader
from tqdm import tqdm

KNOWHOW_DIR = Path(".")

def format_text_to_markdown(text: str) -> str:
    """
    Chuyển đổi text thô thành cấu trúc Markdown hợp lệ để VS Code Extension render đẹp.
    """
    lines = text.split("\n")
    md_lines = []
    
    in_code_block = False
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            md_lines.append("")
            continue

        # Nhận diện Heading dựa trên độ dài và viết hoa (thường gặp trong doc SQL/Manual)
        if len(stripped) < 80 and (stripped.isupper() or re.match(r"^\d+(\.\d+)*\s+[A-Z]", stripped)):
            md_lines.append(f"\n### {stripped}\n")
        # Nhận diện dòng code SQL hoặc lệnh CLI
        elif stripped.startswith(("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "CREATE ", "ALTER ", "DROP ", "GRANT ", "mysql>", "postgres=#")):
            if not in_code_block:
                md_lines.append("```sql")
                in_code_block = True
            md_lines.append(line)
        else:
            if in_code_block:
                md_lines.append("```\n")
                in_code_block = False
            md_lines.append(line)
            
    if in_code_block:
        md_lines.append("```\n")

    return "\n".join(md_lines)

def convert_pdf_to_markdown_pypdf(pdf_path: Path, output_md_path: Path):
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    
    with open(output_md_path, "w", encoding="utf-8") as f, \
         tqdm(total=total_pages, desc="    ⏳ Tiến độ", unit="trang", leave=True) as pbar:
        
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                formatted_md = format_text_to_markdown(text)
                f.write(f"\n\n<!-- PAGE {index} -->\n\n")
                f.write(formatted_md)
            pbar.update(1)

def main():
    if not KNOWHOW_DIR.exists():
        print(f"❌ Thư mục '{KNOWHOW_DIR}' không tồn tại!")
        return

    pdf_files = list(KNOWHOW_DIR.glob("*.pdf"))
    if not pdf_files:
        print("⚠️ Không tìm thấy file PDF nào.")
        return

    total_files = len(pdf_files)
    script_start_time = time.time()

    print("==================================================")
    print(f"🚀 BẮT ĐẦU CHUYỂN ĐỔI {total_files} FILE PDF SANG MARKDOWN (PYPDF ENGINE)")
    print("==================================================\n")

    for index, pdf_path in enumerate(pdf_files, start=1):
        output_md_filename = f"converted_{pdf_path.stem}.md"
        output_md_path = pdf_path.parent / output_md_filename
        file_start_time = time.time()
        file_size_mb = pdf_path.stat().st_size / (1024 * 1024)

        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
        except Exception:
            total_pages = 0

        print(f"[{index}/{total_files}] 📄 File: {pdf_path.name} ({file_size_mb:.2f} MB - {total_pages} trang)")

        try:
            convert_pdf_to_markdown_pypdf(pdf_path, output_md_path)
            elapsed_file_time = time.time() - file_start_time
            print(f"    ✅ Hoàn thành ➔ Saved: {output_md_filename} ({elapsed_file_time:.2f}s)\n")
        except Exception as e:
            elapsed_file_time = time.time() - file_start_time
            print(f"    ❌ Lỗi sau {elapsed_file_time:.2f} giây: {e}\n")

    total_execution_time = time.time() - script_start_time
    print("==================================================")
    print(f"🎉 TỔNG KẾT QUÁ TRÌNH CHUYỂN ĐỔI: {total_execution_time:.2f} giây")
    print("==================================================")

if __name__ == "__main__":
    main()