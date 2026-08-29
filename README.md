# 📚 SQL Documentation Pipeline: PDF ➔ Markdown ➔ JSON Chunks ➔ pgvector SQL

An automated pipeline to scan, extract, and convert large-scale technical PDF documents into standardized Markdown (`.md`) files, intelligently chunk them, compute vector embeddings, and generate optimized batch SQL INSERT scripts (supporting `pgvector` and `jsonb`) for direct ingestion into PostgreSQL.

---

## 🛠️ Technology Stack & Library Details

### 1. Core Libraries for PDF-to-Markdown Conversion
- **`pypdf` (`PdfReader`)**: Used as the primary engine for document text extraction.
  - **Mechanism:** Directly streams and reads pages from PDF file structures without loading the entire large document into RAM.
  - **Optimization:** Extracts robust raw text with no reliance on external C-Extensions, ensuring absolute compatibility with newer Python environments.
- **`tqdm`**: Real-time progress bar and metrics manager.
  - **Mechanism:** Initializes a visual progress bar based on the total page count (`len(reader.pages)`).
  - **Optimization:** Updates dynamically on a per-page basis, providing processing speed metrics (pages/sec) and accurate Estimated Time of Arrival (ETA).
- **`pathlib` (`Path`)**: Object-oriented filesystem path management.
  - **Mechanism:** Scans targeted workspaces and filters documents based on file extensions (e.g., `.glob("*.pdf")`).
  - **Optimization:** Seamlessly extracts base filenames (`pdf_path.stem`) to ensure consistent output naming conventions, and queries disk properties like file size (`st_size`).
- **`re`**: Regular expressions module.
  - **Mechanism:** Scans and processes raw lines of text from PDF documents.
  - **Optimization:** Employs precise regular expressions to automatically identify headers based on uppercase numbering schemes (`^\d+(\.\d+)*\s+[A-Z]`), and detects standard SQL query keywords (`SELECT`, `INSERT`, `CREATE`...) to automatically wrap code segments inside markdown blocks.

### 2. Libraries for Chunking & Embedding
- **`sentence-transformers` (`SentenceTransformer`)**:
  - **Mechanism:** Utilizes the pre-trained **`BAAI/bge-small-en-v1.5`** model to generate 384-dimensional dense vector embeddings that capture the semantic meaning of each text chunk.
  - **Optimization:** Automatically leverages GPU computing (via CUDA) if available or multi-threaded CPU processing, incorporating batching techniques to achieve ultra-fast performance without risking memory overflow.
- **`json` (Standard Library)**:
  - **Mechanism:** Handles the serialization and deserialization of intermediate data.
  - **Optimization:** Saves structured chunk data with clear nesting (`indent=2`) and disables ASCII encoding escapes (`ensure_ascii=False`) to keep native multi-byte/Unicode characters human-readable for easy debugging.
- **`uuid`**: Generates unique identifiers (UUIDs) for each chunk, ensuring item uniqueness within the database and enabling upsert operations (`ON CONFLICT`).

---

## 🔄 End-to-End Pipeline Workflow

The complete data pipeline consists of **3 sequential stages** executed via 3 separate scripts:

```
[PDF Files] ➔ (convert_pdf_to_md.py) ➔ [Markdown Files] ➔ (1_chunking.py) ➔ [processed_chunks.json] ➔ (2_generate_sql.py) ➔ [SQL Inserts] ➔ (PostgreSQL + pgvector)
```

### Step 1: Extract & Convert PDFs to Markdown (`convert_pdf_to_md.py`)
This script scans for all `.pdf` files in the root workspace, streaming each page and formatting them into clean Markdown:
1. **Initialize & Scan:** Scans the root directory to build a processing queue of all PDF documents.
2. **Page-by-Page Streaming:** Processes pages sequentially, extracting raw text with `page.extract_text()`.
3. **Format to Markdown:** Regex logic applies heading markers (`### Header`), appends original page anchors (`<!-- PAGE X -->`), and places detected SQL queries within structured code blocks.
4. **Direct I/O Writes:** Immediately appends formatted content onto the disk and releases memory buffers of processed pages to maintain a minimal RAM footprint.

### Step 2: Logical Document Chunking (`scripts/1_chunking.py`)
This script loads the Markdown files generated inside the `markdown/` folder and structures them into logical chunks:
1. **Stream-based Processing:** Reads Markdown files line-by-line to prevent high memory usage.
2. **Heading Detection:** Slices a new document chunk whenever it encounters Markdown headers (`#` to `######`).
3. **Metadata Assembly:** Every chunk is packed with a structured metadata object containing:
   - `id`: A unique 12-character hex string derived from a UUID.
   - `source_file`: The filename of the source document.
   - `chunk_index`: The sequence number of the chunk within the document.
   - `content`: The raw text content of the chunk.
   - `metadata`: Contains the current section header (`section`), original page reference (`page_anchor`), and content character count (`char_length`).
4. **Export Intermediate Data:** Saves all parsed blocks as a structured JSON file: `processed_chunks.json`.

### Step 3: Compute Vector Embeddings & Export SQL (`scripts/2_generate_sql.py`)
This script reads the intermediate JSON chunks, handles semantic embedding, and exports DB-ready SQL:
1. **Load AI Model:** Downloads and spins up the `BAAI/bge-small-en-v1.5` model from Hugging Face.
2. **Compute Embeddings:** Encodes the text of all chunks into multi-dimensional vectors using optimized batching.
3. **Batch SQL Generation:** Groups SQL insert queries into chunks of 5000 queries per file (`insert_chunks_part<X>.sql`) to keep file sizes manageable and avoid query execution timeouts.
4. **Advanced DB Ingestion Support:** Formulates queries using `INSERT INTO document_chunks ... ON CONFLICT (id) DO UPDATE...` with explicit casting for Postgres `jsonb` (`::jsonb`) and pgvector (`::vector`).

---

## 🗄️ Recommended Database Schema

To successfully import the generated SQL script files, ensure your target PostgreSQL database has the `pgvector` extension enabled and contains a table structured as follows:

```sql
-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the table for storing vectorized document chunks
CREATE TABLE document_chunks (
    id VARCHAR(50) PRIMARY KEY,
    source_file TEXT,
    chunk_index INT,
    content TEXT,
    metadata JSONB,
    embedding VECTOR(384) -- BAAI/bge-small-en-v1.5 produces 384-dimensional vectors
);
```

---

## 💻 Execution Guide

### 1. Install Dependencies
Open your Terminal or PowerShell in the root directory and install the necessary dependencies:

```powershell
py -m pip install pypdf tqdm sentence-transformers
```

> **Performance Tip:** If your machine has an NVIDIA GPU, installing a CUDA-enabled version of PyTorch is highly recommended to accelerate vector embedding computations.

### 2. Run the Scripts Sequentially

#### Step A: Convert PDFs to Markdown
```powershell
py convert_pdf_to_md.py
```
*Output:* `.md` files will be saved in the `markdown/` directory as `converted_<filename>.md`.

#### Step B: Logical Chunking
```powershell
py scripts/1_chunking.py
```
*Output:* A unified file named `processed_chunks.json` will be generated in the root directory.

#### Step C: Generate Vector Embeddings and SQL Scripts
```powershell
py scripts/2_generate_sql.py
```
*Output:* Batch files named `insert_chunks_part1.sql`, `insert_chunks_part2.sql`, etc. will be written to the root directory. These files can be run directly in PostgreSQL via your preferred client (DBeaver, pgAdmin, or the `psql` CLI command).
