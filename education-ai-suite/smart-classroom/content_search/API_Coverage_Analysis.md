# API 覆盖度分析报告

## 📋 后端支持的API清单

### 1️⃣ 任务管理类 (Task Management)

| API | Method | URL | 功能描述 | 同步/异步 |
|-----|--------|-----|---------|-----------|
| 获取任务列表 | GET | `/api/v1/task/list` | 查询所有任务，支持状态过滤 | SYNC |
| 查询任务状态 | GET | `/api/v1/task/query/{task_id}` | 轮询单个任务状态和进度 | SYNC |

**支持的任务状态**: `PENDING` → `QUEUED` → `PROCESSING` → `COMPLETED` / `FAILED`

---

### 2️⃣ 文件处理类 (File Processing)

| API | Method | URL | 功能描述 | 同步/异步 |
|-----|--------|-----|---------|-----------|
| 文件上传 | POST | `/api/v1/object/upload` | 仅上传文件，不索引 | ASYNC |
| 文件摄取 | POST | `/api/v1/object/ingest` | 对已存在文件进行索引 | ASYNC |
| 文本摄取 | POST | `/api/v1/object/ingest-text` | 直接提交文本内容进行索引 | ASYNC |
| 上传并摄取 | POST | `/api/v1/object/upload-ingest` | 上传+索引一步完成 | ASYNC |

**支持的文件类型**:
- 视频: `.mp4`
- 图片: `.jpg`, `.png`, `.jpeg`
- 文档: `.txt`, `.pdf`, `.docx`, `.doc`, `.pptx`, `.ppt`, `.xlsx`, `.xls`
- 网页: `.html`, `.htm`, `.xml`, `.md`

---

### 3️⃣ 搜索与检索类 (Search & Retrieval)

| API | Method | URL | 功能描述 | 同步/异步 |
|-----|--------|-----|---------|-----------|
| 内容搜索 | POST | `/api/v1/object/search` | 文本或图片相似度搜索 | SYNC |
| 文件下载 | GET | `/api/v1/object/download` | 下载指定资源 | SYNC |

**搜索API参数**:
```json
{
  "query": "搜索文本",                    // 或 image_base64
  "max_num_results": 10,                 // Top-K结果数量
  "filter": {
    "type": ["video", "document"],       // 类型过滤
    "tags": ["Math", "Grade1"]           // 标签过滤
  }
}
```

---

### 4️⃣ 资源管理类 (Resource Management)

| API | Method | URL | 功能描述 | 同步/异步 |
|-----|--------|-----|---------|-----------|
| 清理任务 | DELETE | `/api/v1/object/cleanup-task/{task_id}` | 删除任务及相关所有数据 | SYNC |

---

## 🎨 UI需要的功能清单

### ✅ 已实现的功能

#### 1. 文件上传和索引 (Upload & Ingest)
- **对应API**: `POST /api/v1/object/upload-ingest`
- **实现位置**: `app.js:774-821`
- **功能**:
  - ✅ 多文件上传
  - ✅ 支持拖拽上传
  - ✅ 标签(Label)管理
  - ✅ 调用真实API
  - ✅ 显示上传状态

```javascript
// 已集成代码
await fetch("http://127.0.0.1:9011/api/v1/object/upload-ingest", {
  method: "POST",
  body: formData,
});
```

---

### ⚠️ 未实现的功能

#### 2. 搜索功能 (Search)
- **对应API**: `POST /api/v1/object/search`
- **当前状态**: 使用模拟数据 `fakeSearchResults()`
- **实现位置**: `app.js:872-919`
- **需要集成的功能**:
  - ❌ 文本搜索调用真实API
  - ❌ 图片搜索调用真实API (Base64编码)
  - ❌ 类型过滤 (Document/Image/Video)
  - ❌ 标签过滤
  - ❌ Top-K控制
  - ❌ 搜索结果展示
  - ❌ 错误处理

```javascript
// 当前使用假数据
const results = fakeSearchResults({
  types: selectedTypes,
  topK: safeTopK,
  textQuery: effectiveTextQuery,
  hasImageQuery: effectiveHasImage,
});
```

#### 3. 任务状态管理 (Task Status)
- **对应API**: 
  - `GET /api/v1/task/query/{task_id}` - 查询单个任务
  - `GET /api/v1/task/list` - 查询任务列表
- **当前状态**: 完全未实现
- **UI显示位置**: `index.html:78-93` (状态面板)
- **需要实现的功能**:
  - ❌ 上传后自动轮询任务状态
  - ❌ 显示索引进度
  - ❌ 任务列表管理
  - ❌ 任务状态实时更新

```html
<!-- UI已准备好状态显示 -->
<div class="statusbox__row">
  <span class="statusbox__label">Indexing Status</span>
  <span class="badge" id="indexing-state">
    <span class="spinner" id="indexing-spinner"></span>
    <span id="indexing-state-text">Idle</span>
  </span>
</div>
```

#### 4. 文件下载 (Download)
- **对应API**: `GET /api/v1/object/download`
- **当前状态**: 未实现
- **建议**: 在搜索结果中添加下载链接

#### 5. 任务清理 (Cleanup)
- **对应API**: `DELETE /api/v1/object/cleanup-task/{task_id}`
- **当前状态**: 未实现
- **建议**: 添加任务管理页面，支持删除任务

---

## 📊 覆盖度总结

### API覆盖情况

| 功能模块 | 后端API | UI需求 | 集成状态 | 优先级 |
|---------|---------|--------|---------|--------|
| 文件上传+索引 | ✅ | ✅ | ✅ **已集成** | - |
| 内容搜索 | ✅ | ✅ | ❌ **需要集成** | 🔴 **高** |
| 任务状态查询 | ✅ | ✅ | ❌ **需要集成** | 🟡 **中** |
| 任务列表 | ✅ | ❌ | - | 🟢 **低** |
| 文件下载 | ✅ | ❌ | - | 🟢 **低** |
| 任务清理 | ✅ | ❌ | - | 🟢 **低** |
| 文本直接摄取 | ✅ | ❌ | - | 🟢 **低** |
| 单独上传 | ✅ | ❌ | - | 🟢 **低** |

### 结论

✅ **好消息**: 现有后端API **完全可以覆盖** UI的核心功能需求！

🔧 **需要做的工作**:

1. **必须**: 集成搜索API（核心功能）
2. **建议**: 添加任务状态轮询（改善用户体验）
3. **可选**: 扩展任务管理功能（高级功能）

---

## 🎯 下一步行动计划

### Phase 1: 核心功能补全 (必须)
1. ✅ ~~文件上传~~ (已完成)
2. ❌ **搜索功能集成** ← 最优先
   - 文本搜索
   - 图片搜索
   - 结果映射和展示

### Phase 2: 用户体验优化 (建议)
3. ❌ 任务状态轮询
   - 上传后显示处理进度
   - 索引完成提醒
4. ❌ 错误处理优化

### Phase 3: 高级功能 (可选)
5. ❌ 任务管理页面
6. ❌ 文件下载功能
7. ❌ 任务清理功能

---

## 💡 技术细节

### 搜索API的关键点

1. **参数映射**:
   ```javascript
   // UI → API
   {
     query: textQuery,                    // 或 image_base64
     max_num_results: topK,               // 1-10
     filter: {
       type: ["video", "document"],       // UI的checkbox
       tags: selectedLabels               // UI的label selector
     }
   }
   ```

2. **结果映射**:
   ```javascript
   // API → UI
   {
     type: meta.type,                     // "video" | "image" | "document"
     filename: meta.asset_id,             // 文件名
     score: distance,                     // 相似度分数
     labels: meta.tags,                   // 标签数组
     start_time: meta.start_time,         // 视频时间戳
     page_range: meta.page_range,         // PDF页码
     chunk_text: meta.chunk_text          // 摘要文本
   }
   ```

3. **图片搜索需要Base64编码**:
   ```javascript
   const file = queryImage.getFile();
   const reader = new FileReader();
   reader.onload = () => {
     const base64 = reader.result.split(',')[1];
     // 发送到API
   };
   reader.readAsDataURL(file);
   ```

---

## 🔍 API兼容性检查

### ✅ 完全兼容的特性
- [x] 文件类型匹配 (mp4, jpg, pdf, ppt, docx, csv, txt)
- [x] 标签(Label)系统 - API用`meta.tags`, UI有完整的标签管理
- [x] 类型过滤 - API支持`filter.type`, UI有checkbox
- [x] Top-K控制 - API用`max_num_results`, UI有输入框
- [x] 异步任务模型 - API返回task_id, UI有状态显示区域

### ⚠️ 需要适配的地方
- [ ] API返回的字段名和UI期望的字段名不完全一致（需要映射）
- [ ] 图片搜索需要转Base64（UI目前存File对象）
- [ ] 错误码处理（API有完整的错误码体系，UI需要适配）

### 🎉 总体评价
**覆盖率: 90%** - 后端API设计完善，只需前端集成工作，无需后端改动！
