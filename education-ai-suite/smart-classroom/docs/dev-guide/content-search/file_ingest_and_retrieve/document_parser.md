# File Ingest & Retrieve

## Document Parsing Configuration

`DocumentParser` processes a file in two independent steps:

```
File  →  [Step 1: Text Extraction]  →  raw text  →  [Step 2: Chunking]  →  nodes
```

---

## Step 1 — Text Extraction

Always uses the "fast" strategy for PDF text extraction (selectable text extracted natively). Embedded images in PDFs are extracted and sent to the PaddleOCR service for OCR, with each image's text becoming an independent searchable node.

| Parameter | Default | Description |
|---|---|---|
| `extract_images` | `True` | Extract embedded images from PDFs and OCR them via PaddleOCR service. Each image produces an independent node with `source_type: "image_ocr"` metadata |
| `ocr_service_url` | `env OCR_SERVICE_URL` or `http://127.0.0.1:8000` | URL of the PaddleOCR service used for image OCR |

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

| `embed_model` | Text extraction | Image OCR | Chunking |
|---|---|---|---|
| `None` | fast (selectable text) | PaddleOCR service | fixed-size (unstructured basic) |
| provided | fast (selectable text) | PaddleOCR service | semantic (SemanticSplitterNodeParser) |

---

## Example — Enabling Semantic Chunking

```python
# In indexer.py, pass the embedding model instance to DocumentParser:
self.document_parser = DocumentParser(
    embed_model=self.document_embedding_model,  # LlamaIndex-compatible OpenVINOEmbedding instance
    semantic_breakpoint_percentile=95,
    semantic_min_chunk_size=150,
)
```

---
