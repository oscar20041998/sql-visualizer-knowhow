import re
import json
import uuid
from pathlib import Path

# Đường dẫn tương đối từ thư mục scripts/ ra thư mục gốc knowhow/
BASE_DIR = Path(__file__).resolve().parent.parent  
MARKDOWN_DIR = BASE_DIR / "markdown"               
OUTPUT_JSON = BASE_DIR / "processed_chunks.json"  

def parse_md_file_stream(md_file_path):
    """Đọc và parse file MD theo dạng stream để tiết kiệm RAM tối đa."""
    file_name = md_file_path.name
    
    parsed_chunks = []
    current_chunk_lines = []
    current_page = "PAGE 1"
    chunk_idx = 1

    print(f"  ⏳ Đang đọc stream file {file_name}...")
    
    with open(md_file_path, "r", encoding="utf-8") as f:
        for line in f:
            if re.match(r'^#{1,6}\s+', line) and current_chunk_lines:
                text = "".join(current_chunk_lines).strip()
                if text:
                    page_match = re.search(r'<!--\s*PAGE\s*(\d+)\s*-->', text)
                    if page_match:
                        current_page = f"PAGE {page_match.group(1)}"

                    heading_match = re.search(r'^#{1,6}\s+(.+)$', text, re.MULTILINE)
                    section_title = heading_match.group(1).strip() if heading_match else "General Info"

                    parsed_chunks.append({
                        "id": f"chunk_{uuid.uuid4().hex[:12]}",
                        "source_file": file_name,
                        "chunk_index": chunk_idx,
                        "content": text,
                        "metadata": {
                            "section": section_title,
                            "page_anchor": current_page,
                            "char_length": len(text)
                        }
                    })
                    chunk_idx += 1
                current_chunk_lines = []

            current_chunk_lines.append(line)

    if current_chunk_lines:
        text = "".join(current_chunk_lines).strip()
        if text:
            heading_match = re.search(r'^#{1,6}\s+(.+)$', text, re.MULTILINE)
            section_title = heading_match.group(1).strip() if heading_match else "General Info"
            parsed_chunks.append({
                "id": f"chunk_{uuid.uuid4().hex[:12]}",
                "source_file": file_name,
                "chunk_index": chunk_idx,
                "content": text,
                "metadata": {
                    "section": section_title,
                    "page_anchor": current_page,
                    "char_length": len(text)
                }
            })

    return parsed_chunks


def run_chunking():
    if not MARKDOWN_DIR.exists():
        print(f"❌ Không tìm thấy thư mục: {MARKDOWN_DIR}")
        return

    md_files = sorted(list(MARKDOWN_DIR.glob("converted_*.md")))
    
    if not md_files:
        print(f"❌ Không tìm thấy file 'converted_*.md' nào trong {MARKDOWN_DIR}")
        return

    print(f"🔍 Tìm thấy {len(md_files)} file Markdown trong '{MARKDOWN_DIR.name}'. Bắt đầu chunking...\n")
    all_chunks = []
    
    for md_file in md_files:
        file_chunks = parse_md_file_stream(md_file)
        all_chunks.extend(file_chunks)
        print(f"  ✅ {md_file.name}: Tạo thành công {len(file_chunks)} chunks.")

    print(f"\n💾 Đang ghi {len(all_chunks)} chunks ra file '{OUTPUT_JSON.name}' (Format Pretty Print)...")
    
    # Thêm indent=2 và ensure_ascii=False để JSON đẹp, rõ ràng, đọc được tiếng Việt
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"🎉 HOÀN THÀNH CHUNKING! File JSON chuẩn định dạng đã được lưu.")


if __name__ == "__main__":
    run_chunking()