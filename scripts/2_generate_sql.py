import json
from pathlib import Path
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent.parent  
INPUT_JSON = BASE_DIR / "processed_chunks.json"   

def escape_sql_string(text):
    if text is None:
        return ""
    return str(text).replace("'", "''")

def generate_sql_insert(batch_size=5000):
    if not INPUT_JSON.exists():
        print(f"❌ Không tìm thấy file '{INPUT_JSON}'. Hãy chạy 1_chunking.py trước!")
        return

    print(f"📖 Đang nạp dữ liệu từ '{INPUT_JSON.name}'...")
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    total_chunks = len(chunks)
    print(f"📊 Tổng số chunks cần embedding: {total_chunks}")

    print("⏳ Đang nạp model BAAI/bge-small-en-v1.5 & tính toán Vector Embeddings...")
    model = SentenceTransformer('BAAI/bge-small-en-v1.5')
    
    contents = [item["content"] for item in chunks]
    embeddings = model.encode(contents, show_progress_bar=True, batch_size=32)

    print("\n📝 Đang tiến hành xuất các file SQL (Batching 5000 câu lệnh/file)...")
    
    file_part = 1
    for i in range(0, total_chunks, batch_size):
        batch_chunks = chunks[i:i + batch_size]
        sql_filepath = BASE_DIR / f"insert_chunks_part{file_part}.sql"
        
        with open(sql_filepath, "w", encoding="utf-8") as f:
            f.write(f"-- PART {file_part}: INSERT {len(batch_chunks)} CHUNKS\n")
            f.write("BEGIN;\n\n")

            for idx_in_batch, item in enumerate(batch_chunks):
                global_idx = i + idx_in_batch
                chunk_id = escape_sql_string(item["id"])
                source_file = escape_sql_string(item["source_file"])
                chunk_index = item["chunk_index"]
                content = escape_sql_string(item["content"])
                
                # Chuyển metadata dict sang chuỗi JSON không bị escaping lỗi Unicode
                metadata_str = escape_sql_string(json.dumps(item["metadata"], ensure_ascii=False))
                vector_str = str(embeddings[global_idx].tolist())

                sql_statement = f"""INSERT INTO document_chunks (id, source_file, chunk_index, content, metadata, embedding)
VALUES (
    '{chunk_id}',
    '{source_file}',
    {chunk_index},
    '{content}',
    '{metadata_str}'::jsonb,
    '{vector_str}'::vector
)
ON CONFLICT (id) DO UPDATE SET
    content = EXCLUDED.content,
    metadata = EXCLUDED.metadata,
    embedding = EXCLUDED.embedding;\n\n"""
                f.write(sql_statement)

            f.write("COMMIT;\n")
        
        print(f"  ├─ Đã tạo thành công: {sql_filepath.name}")
        file_part += 1

    print(f"\n🎉 THÀNH CÔNG! Đã xuất xong toàn bộ file SQL ra thư mục gốc.")

if __name__ == "__main__":
    generate_sql_insert()