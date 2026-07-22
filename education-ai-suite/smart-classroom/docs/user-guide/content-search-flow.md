# Content Search Flow

The Content Search feature supports file upload and ingestion, multimodal search (text and image
queries), and Q&A over retrieved content. To enter the Content Search view, click the
**Content Search** button in the top navigation bar on the Smart Classroom main screen:

![Content Search Entry](./_assets/content-search-entry1.png)

The Content Search view page is split into two panels:

**Left Panel**

- **Upload** - Ingest files (videos, documents, and images) into the vector database
- **Search and Q&A** - Query uploaded content using text or image search, or through natural
language
- **Results** - Display search results with type filtering, relevance scores, and content previews

**Right Panel**

- **Configurations** - Platform and software configuration for Content Search services
- **Resource Utilization** - Live monitoring of CPU, GPU, memory, and power utilization
- **Pre-validated Models** - Models used by Content Search, including Vision-Language Model (VLM), visual embedding, document embedding,
  and reranker

![Content Search Initial View](./_assets/content-search-entry2.png)

## Step 1: Upload Files

1. Click **Upload Files** to browse, or drag and drop files into the drop zone:

![Upload Flow](./_assets/content-search-upload.png)

2. **Select files** using checkboxes to manage file tags
3. **Add tags** to selected files before the upload
4. **Video options** - Toggle the summarization of MP4 files
5. **Search and Q&A tabs** - Available after the upload completes

Supported file formats:

| Type | Formats |
| :--- | :--- |
| Video | `.mp4` |
| Document | `.pdf`, `.docx`, `.doc`, `.pptx`, `.ppt`, `.xlsx`, `.xls`, `.txt`, `.html`, `.htm`, `.xml`, `.md` |
| Image | `.jpg`, `.jpeg`, `.png` |

### Tag Files

Before uploading files, you can add tags to organize your content:

1. Select one or more files using the checkboxes in the file table
2. Type a tag in the tag input field and press **Enter** or **comma** to add it
3. Tags appear as chips that can be removed by clicking **x**

> **Note:** Tags can be added or removed only while the file is in the **Staged** state (before
> upload). Once uploaded, tags are locked.

### Toggle Video Summarization

For `.mp4` files, a **Summarize** toggle appears next to the file name. When enabled, the system
uses a VLM to generate text summaries of video chunks. This enables richer
text-based search over the video content.

### Upload Files

Click the **Upload Files** button at the bottom to start processing all staged files. Each file
goes through the ingestion pipeline:

- **Documents** - Text extraction with Optical Character Recognition (OCR) for handwritten or scanned content, semantic chunking,
  and embedding
- **Images** - Contrastive Language-Image Pretraining (CLIP) embedding for visual similarity search
- **Videos** - Time-based chunking, frame sampling, VLM summarization if enabled, and both text
  and visual embedding

The status column shows the current state: Staged -> Processing -> Completed (or Failed).

![Files Uploaded Successfully](./_assets/content-search-metrics.png)

### Manage Files

After uploading files, click **View Files** to open the File Manager:

![View Files Button](./_assets/content-search-filemanager.png)

The File Manager shows all files currently stored on the server:

![File Manager - Uploaded File List](./_assets/content-search-filemanager2.png)

## Step 2: Search for Text and Images

After at least one file upload is complete, the **Search** tab becomes available.

### Search for Text

1. Select the **Text Search** tab.
2. Type your query in the text area (maximum: 100 characters).
3. Select the content types to search across: **Documents**, **Images**, and **Videos**
   (any combination).
4. (Optional) Filter results by tag using the **Filter by tags** drop-down menu.
5. Set the number of **Top Results** to return (default: 10)
6. Click **Search**

The text query feature searches both the visual collection (CLIP embeddings) and the textual collection
BAAI General Embedding (BGE) embeddings. Textual results are reranked by a cross-encoder, and results from both
modalities are merged using Reciprocal Rank Fusion (RRF).

![Text Search with Results](./_assets/content-search_searchResult.png)

### Search for Images

1. Select the **Image Search** tab
2. Drag and drop an image or click to browse (accepts `.jpg`, `.jpeg`, `.png`)
3. Select the content types to search: **Images**, **Videos**
   (document search is not available for image queries)
4. Optionally filter by tag
5. Click **Search**

The image query feature searches the visual collection by CLIP similarity, returning visually similar images
and video frames:

![Image Search with Results](./_assets/content-search-image-search.png)

### View Search Results

Results are displayed in a card layout with tabs for filtering by type:
**All**, **Documents**, **Images**, and **Videos**.

Each result card shows:

- **File name** and type icon
- **Relevance score** (percentage)
- **Page number** (for documents)
- **Timestamp** (for video results, showing the pin time in the video)
- **Raw text / Summary** - Expandable text snippet or VLM-generated summary
- **Tags** - Associated labels

Click **Reset** to clear all search inputs and results.

## Step 3: Q&A Retrieval-Augmented Generation (RAG)

The **Q&A** tab provides a conversational interface for asking questions about uploaded content.

1. Switch to the **Q&A** tab.
2. (Optional) Select tags to narrow the context using the **Filter by tag** selector.
3. Type your question in the input area (maximum: 500 characters).
4. Press **Enter** or click the **Send** button.

The system retrieves the most relevant chunks from uploaded content, assembles them as context, and
sends them to the VLM to generate a grounded answer. Each response includes:

- **Answer** - The AI-generated response based on your content
- **Sources** - Referenced files with type indicators and location (page number or video timestamp)

The conversation history is maintained within the session, allowing multi-turn follow-up questions.
Click **Clear conversation** to reset the chat history.

![Q&A Conversation](./_assets/content-search-QaA.png)

## Step 4: Monitor Health

The Content Search panel automatically checks the health of backend services on load. If any service
is unreachable or unhealthy, an error message appears indicating:

- Backend unreachable - The Content Search API (port 9011) is not responding
- Upload/search failure - One or more downstream services (File Ingest, Video Preprocess,
  VLM Serving, or ChromaDB vector database) have issues

![Health Check Error](./_assets/content-search-healthy-check.png)

Upload and search functionality is affected until all services are healthy.

## Microservices

| Service | Port | Role |
| :--- | :---: | :--- |
| Content Search API | 9011 | Orchestrator and public API |
| File Ingest & Retrieve | 9990 | Embedding, indexing, and retrieval |
| Video Preprocess | 8001 | Video chunking and VLM summarization |
| VLM OpenVINO Serving | 9900 | VLM inference |
| ChromaDB | 9090 | Vector database |

## Learn More

- [How It Works - Content Search Pipeline](./how-it-works.md#content-search-pipeline): Technical
  architecture and design details.
- [Application Flow](./application-flow.md): End-to-end application flow.