import json
import math
import re
import unicodedata
from pathlib import Path
from sentence_transformers import SentenceTransformer
import torch

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_JSON = BASE_DIR / "processed_chunks.json"
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def clean_text(value):
    text = unicodedata.normalize("NFC", str(value or ""))
    text = HTML_COMMENT_PATTERN.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = CONTROL_CHARACTER_PATTERN.sub("", text)
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()


def escape_sql_string(value):
    return clean_text(value).replace("'", "''")


def prepare_chunk(item, position):
    required_fields = ("id", "source_file", "chunk_index", "content", "metadata")
    missing_fields = [field for field in required_fields if field not in item]
    if missing_fields:
        raise ValueError(f"Chunk {position} is missing: {', '.join(missing_fields)}")

    content = clean_text(item["content"])
    if not content:
        raise ValueError(f"Chunk {position} has no content after cleaning")
    if not isinstance(item["metadata"], dict):
        raise ValueError(f"Chunk {position} metadata must be an object")

    metadata = item["metadata"].copy()
    metadata["section"] = clean_text(metadata.get("section", "General Info"))
    metadata["char_length"] = len(content)

    return {
        "id": clean_text(item["id"]),
        "source_file": clean_text(item["source_file"]),
        "chunk_index": int(item["chunk_index"]),
        "content": content,
        "metadata": metadata,
    }


def format_vector(values, position):
    vector = [float(value) for value in values]
    if not vector or not all(math.isfinite(value) for value in vector):
        raise ValueError(f"Chunk {position} has an invalid embedding")
    return "[" + ",".join(format(value, ".8g") for value in vector) + "]"

def encode_batch(model, contents, embedding_batch_size):
    current_batch_size = embedding_batch_size
    while current_batch_size >= 1:
        try:
            return model.encode(
                contents,
                show_progress_bar=True,
                batch_size=current_batch_size,
                convert_to_numpy=True,
            )
        except torch.OutOfMemoryError:
            if current_batch_size == 1:
                raise
            current_batch_size //= 2
            print(
                f"    ! Không đủ RAM, thử lại với embedding batch size: {current_batch_size}",
                flush=True,
            )


def generate_sql_insert(batch_size=5000, embedding_batch_size=16):
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    if embedding_batch_size <= 0:
        raise ValueError("embedding_batch_size must be greater than zero")

    if not INPUT_JSON.exists():
        print(f"❌ Không tìm thấy file '{INPUT_JSON}'. Hãy chạy 1_chunking.py trước!")
        return

    print(f"📖 Đang nạp dữ liệu từ '{INPUT_JSON.name}'...")
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    chunks = [prepare_chunk(item, index + 1) for index, item in enumerate(chunks)]
    total_chunks = len(chunks)
    print(f"📊 Tổng số chunks cần embedding: {total_chunks}")

    print("⏳ Đang nạp model BAAI/bge-small-en-v1.5...")
    model = SentenceTransformer('BAAI/bge-small-en-v1.5')

    print("\n📝 Đang tạo embeddings và xuất SQL (5,000 chunks/file)...")

    file_part = 1
    progress_interval = 100
    for i in range(0, total_chunks, batch_size):
        batch_chunks = chunks[i:i + batch_size]
        sql_filepath = BASE_DIR / f"insert_chunks_part{file_part}.sql"
        batch_end = i + len(batch_chunks)
        print(
            f"  ⏳ Đang tạo {sql_filepath.name} "
            f"(chunks {i + 1:,}-{batch_end:,} / {total_chunks:,})...",
            flush=True,
        )

        print(
            f"    ├─ Đang tạo embeddings (batch size: {embedding_batch_size})...",
            flush=True,
        )
        embeddings = encode_batch(
            model,
            [chunk["content"] for chunk in batch_chunks],
            embedding_batch_size,
        )
        if len(embeddings) != len(batch_chunks):
            raise RuntimeError(f"Embedding result is incomplete for {sql_filepath.name}")

        with open(sql_filepath, "w", encoding="utf-8") as f:
            f.write(f"-- PART {file_part}: INSERT {len(batch_chunks)} CHUNKS\n")
            f.write("BEGIN;\n\n")

            for idx_in_batch, item in enumerate(batch_chunks):
                chunk_id = escape_sql_string(item["id"])
                source_file = escape_sql_string(item["source_file"])
                chunk_index = item["chunk_index"]
                content = escape_sql_string(item["content"])

                metadata_str = escape_sql_string(json.dumps(item["metadata"], ensure_ascii=False, separators=(",", ":")))
                vector_str = format_vector(embeddings[idx_in_batch], i + idx_in_batch + 1)

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
    source_file = EXCLUDED.source_file,
    chunk_index = EXCLUDED.chunk_index,
    content = EXCLUDED.content,
    metadata = EXCLUDED.metadata,
    embedding = EXCLUDED.embedding;\n\n"""
                f.write(sql_statement)

                records_written = idx_in_batch + 1
                if records_written % progress_interval == 0 or records_written == len(batch_chunks):
                    total_written = i + records_written
                    percentage = total_written / total_chunks * 100
                    print(
                        f"    ├─ {total_written:,} / {total_chunks:,} chunks "
                        f"({percentage:.1f}%) written",
                        flush=True,
                    )

            f.write("COMMIT;\n")

        print(f"  ✅ Đã tạo thành công: {sql_filepath.name}", flush=True)
        file_part += 1

    print(f"\n🎉 THÀNH CÔNG! Đã xuất xong toàn bộ file SQL ra thư mục gốc.")

if __name__ == "__main__":
    generate_sql_insert()