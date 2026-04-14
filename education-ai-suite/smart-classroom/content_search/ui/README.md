# Content Search UI

AI-powered content search interface for semantic search across videos, images, and documents.

## 🚀 Quick Start

### 1. Start the Backend API

Make sure the backend API server is running:

```bash
# From the project root
cd edge-ai-my-fork/education-ai-suite/smart-classroom/content_search
python -m uvicorn main:app --reload --port 9011
```

Backend should be accessible at: `http://127.0.0.1:9011`

### 2. Start the UI

The UI must be served via HTTP (not opened directly as a file) due to CORS policies.

**Option A: Using Python 3**
```bash
cd ui
python -m http.server 8000
```

**Option B: Using Node.js**
```bash
cd ui
npx http-server -p 8000
```

**Option C: Using Live Server (VS Code Extension)**
- Install "Live Server" extension in VS Code
- Right-click `index.html` → "Open with Live Server"

### 3. Open in Browser

Navigate to: `http://localhost:8000`

---

## ✨ Features

### 📤 File Upload & Ingestion
- **Drag & drop** or click to upload files
- **Supported formats:**
  - Video: `.mp4`
  - Images: `.jpg`, `.png`, `.jpeg`
  - Documents: `.pdf`, `.ppt`, `.pptx`, `.docx`, `.txt`, `.html`, `.md`
- **Label management:** Add tags to organize your content
- **Real-time status:** Track upload and processing progress
- **Elapsed time tracking:** Monitor how long each file takes to process

### 🔍 Search
- **Text search:** Semantic search using natural language
- **Image search:** Find similar content using a reference image (.jpg)
- **Filters:**
  - Content type (Documents, Images, Videos)
  - Labels/tags
  - Top-K results (1-10)
- **Preview:** View results with thumbnails and metadata

### 📊 Results Display
- **Score ranking:** Results sorted by similarity (highest first)
- **Metadata:** Filename, page/timestamp, labels
- **Preview modal:** Quick preview for images, videos, and documents
- **Video timestamps:** Jump to relevant time segments in videos

---

## 📁 File Structure

```
ui/
├── README.md                  # This file
├── index.html                 # Main HTML entry
├── styles.css                 # All styles (Intel-branded design)
├── app.js                     # Main app logic (search, backend health)
├── app_file_manager.js        # File state management
└── app_ui_renderer.js         # UI rendering & upload logic
```

---

## 🔧 Configuration

### API Base URL

By default, the UI connects to `http://127.0.0.1:9011`.

To change this, modify `app.js`:

```javascript
const API_BASE_URL = "http://127.0.0.1:9011";  // Change this
```

Or set it dynamically:
```javascript
window.API_BASE_URL = "https://your-api-domain.com";
```

---

## 🎨 Design

- **Intel-branded color scheme:** Professional blue (`#0068b5`)
- **Clean, modern layout:** Minimalist design with subtle shadows
- **Responsive:** Mobile-friendly design (768px breakpoint)
- **Accessibility:** ARIA labels, keyboard navigation support

---

## 🐛 Troubleshooting

### Issue: "Backend Offline" status

**Cause:** UI cannot connect to the backend API.

**Solution:**
1. Verify backend is running: `curl http://127.0.0.1:9011/api/v1/system/health`
2. Check the backend logs for errors
3. Ensure no firewall is blocking port 9011

### Issue: CORS errors in browser console

**Cause:** Opening `index.html` directly as a file (`file://`).

**Solution:** Must serve via HTTP server (see Quick Start above).

### Issue: Files stuck in "Processing..." state

**Cause:** Backend processing task is still running or failed silently.

**Solution:**
1. Check backend logs for errors
2. Verify the task is still active: `GET /api/v1/task/query/{task_id}`
3. UI polls every 2 seconds - wait for completion or check for errors

### Issue: Upload fails with 413 error

**Cause:** File size exceeds server limit.

**Solution:**
- Backend may have a file size limit (default ~500MB)
- Check `max_upload_size` configuration in backend
- Consider splitting large videos into chunks

---

## 📝 API Endpoints Used

The UI interacts with these backend endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/system/health` | GET | Check backend status |
| `/api/v1/object/upload-ingest` | POST | Upload and ingest files |
| `/api/v1/task/query/{task_id}` | GET | Poll processing status |
| `/api/v1/search` | POST | Perform semantic search |
| `/api/v1/object/download/{file_path}` | GET | Download/preview files |

---

## 🔐 Security Notes

- **No authentication:** This UI has no built-in auth. Add authentication at the backend level.
- **File uploads:** Validate file types and sizes on the backend to prevent abuse.
- **XSS protection:** User-generated labels are sanitized, but be cautious with user inputs.

---

## 📦 Dependencies

**None!** This is a pure vanilla JavaScript application with no build step or npm dependencies.

- No React, Vue, or Angular
- No webpack or bundler needed
- Just modern ES6+ JavaScript

---

## 📄 License

Part of the Education AI Suite project.

---

## 🤝 Contributing

To modify the UI:

1. Edit HTML/CSS/JS files directly
2. Refresh browser (Ctrl+F5 to clear cache)
3. No build step required!

**Key files to edit:**
- `styles.css` - All visual styling
- `app_ui_renderer.js` - Upload UI and file list
- `app.js` - Search functionality
- `index.html` - Page structure

---

## 📞 Support

For issues or questions, check the main project documentation or open an issue on GitHub.
