# File Ingest & Retrieve

## Document Parsing Configuration

`DocumentParser` processes a file in two independent steps:

```
File  →  [Step 1: Text Extraction]  →  raw text  →  [Step 2: Chunking]  →  nodes
```

---

## Step 1 — Text Extraction

Controlled by `use_hi_res_strategy` and `ocr_languages`. These parameters affect **only how text is read from the file**.

| Parameter | Default | Description |
|---|---|---|
| `use_hi_res_strategy` | `True` | `True`: renders each PDF page as an image and runs Tesseract OCR (slower, higher accuracy, required for scanned PDFs). `False`: fast strategy — uses selectable text directly; OCR only as fallback for image-only pages |
| `ocr_languages` | `["eng", "chi_sim", "chi"]` | Tesseract language codes used when OCR is invoked |
| `extract_images` | `True` | Extract embedded images from PDFs/DOCX and save them to `image_output_dir` (no OCR is applied to the extracted images) |

---

## Step 2 — Chunking

Controlled by `embed_model`. These parameters affect **how the extracted text is split into chunks**.

### Basic (fixed-size) chunking — default (`embed_model=None`)

The `unstructured` library splits text into fixed-size character chunks.

| Parameter | Default | Description |
|---|---|---|
| `chunk_size` | `250` | Maximum characters per chunk |
| `chunk_overlap` | `50` | Overlapping characters between adjacent chunks |

### Semantic chunking (`embed_model` provided)

Pass a LlamaIndex-compatible embedding model to enable `SemanticSplitterNodeParser`. The full file is first extracted as a single document, then split by detecting natural topic boundaries using embedding similarity — producing semantically coherent chunks rather than fixed-size ones.

A bilingual sentence splitter is used internally, supporting both **Chinese** (。！？；……) and **English** (`. ! ?`) punctuation boundaries.

> **Note:** When `embed_model` is provided, `chunk_size` and `chunk_overlap` are ignored.

| Parameter | Default | Description |
|---|---|---|
| `embed_model` | `None` | LlamaIndex embedding model instance. When set, semantic chunking is used instead of basic chunking |
| `semantic_buffer_size` | `2` | Number of surrounding sentences compared when detecting a semantic boundary |
| `semantic_breakpoint_percentile` | `85` | Percentile threshold for breakpoint detection; higher value → fewer, larger chunks |
| `semantic_min_chunk_size` | `200` | Minimum characters per chunk; chunks below this threshold are merged into the next chunk |

---

## Combination Matrix

| `use_hi_res_strategy` | `embed_model` | Text extraction | Chunking |
|---|---|---|---|
| `False` | `None` | fast (selectable text, OCR fallback) | fixed-size (unstructured basic) |
| `True` | `None` | hi_res full OCR | fixed-size (unstructured basic) |
| `False` | provided | fast (selectable text, OCR fallback) | semantic (SemanticSplitterNodeParser) |
| `True` | provided | hi_res full OCR | semantic (SemanticSplitterNodeParser) |

---

## Example — Enabling Semantic Chunking

```python
# In indexer.py, pass the embedding model instance to DocumentParser:
self.document_parser = DocumentParser(
    embed_model=self.document_embedding_model,  # LlamaIndex-compatible OpenVINOEmbedding instance
    semantic_breakpoint_percentile=95,
    semantic_min_chunk_size=150,
    use_hi_res_strategy=False,  # Step 1: fast extraction (Step 2 semantic chunking is independent)
)
```

---
