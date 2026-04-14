# 错误处理和业务状态码指南

## 📋 业务状态码 (Business Code)

后端API使用双层状态码系统：
1. **HTTP状态码** - 网络层（200, 401, 500等）
2. **业务状态码** - 应用层（20000, 40000等）

### 业务状态码列表

| Code | 名称 | 含义 | 用户提示 |
|------|------|------|----------|
| 20000 | SUCCESS | 操作成功 | - |
| 40000 | BAD_REQUEST | 请求参数错误 | "请检查输入后重试" |
| 40001 | AUTH_FAILED | 认证失败 | "用户名或密码错误" |
| 40901 | FILE_ALREADY_EXISTS | 文件已存在 | "该文件已上传过" |
| 50001 | FILE_TYPE_ERROR | 不支持的文件格式 | "不支持的文件格式，请检查文件类型" |
| 50002 | TASK_NOT_FOUND | 任务不存在或已过期 | "任务不存在，可能已过期或被删除" |
| 50003 | PROCESS_FAILED | 内部处理错误 | "处理失败，发生内部错误" |

---

## 🔧 前端错误处理实现

### 1. 错误码映射

在 [app.js](app.js) 中定义：

```javascript
const ERROR_CODES = {
  20000: "SUCCESS",
  40000: "BAD_REQUEST",
  40001: "AUTH_FAILED",
  40901: "FILE_ALREADY_EXISTS",
  50001: "FILE_TYPE_ERROR",
  50002: "TASK_NOT_FOUND",
  50003: "PROCESS_FAILED",
};
```

### 2. 友好错误消息

```javascript
function getErrorMessage(code, defaultMessage) {
  const errorMessages = {
    40000: "Bad request. Please check your input and try again.",
    40001: "Authentication failed. Invalid username or password.",
    40901: "File already exists. This file has been uploaded before.",
    50001: "Unsupported file format. Please check the file type.",
    50002: "Task not found. The task may have expired or been deleted.",
    50003: "Processing failed. An internal error occurred.",
  };

  return errorMessages[code] || defaultMessage || "An unknown error occurred.";
}
```

### 3. 统一响应解析

```javascript
function parseApiResponse(data, defaultErrorMsg = "Operation failed") {
  if (!data) {
    throw new Error(defaultErrorMsg);
  }

  const code = data.code;

  if (code === 20000) {
    return data;  // Success
  }

  // Non-success code
  const errorType = ERROR_CODES[code] || "UNKNOWN_ERROR";
  const userMessage = getErrorMessage(code, data.message);
  const error = new Error(userMessage);
  error.code = code;
  error.errorType = errorType;
  error.originalMessage = data.message;

  throw error;
}
```

---

## 🎯 使用示例

### 文本搜索

```javascript
async function performTextSearch(query, maxResults, filter) {
  const response = await fetch("http://127.0.0.1:9011/api/v1/object/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const data = await response.json();
  parseApiResponse(data, "Search failed");  // 自动检查业务码

  return (data.data?.results || []).map(mapApiResultToUi);
}
```

### 文件上传

```javascript
try {
  const response = await fetch("http://127.0.0.1:9011/api/v1/object/upload-ingest", {
    method: "POST",
    body: formData,
  });

  const data = await response.json();
  parseApiResponse(data, "Upload failed");

  // 上传成功的处理...
} catch (error) {
  let errorMsg = error?.message || "Unknown error";

  // 针对特定错误码的额外提示
  if (error.code === 50001) {
    errorMsg += " Supported formats: .mp4, .jpg, .png, .pdf, .docx, .txt";
  } else if (error.code === 40901) {
    errorMsg += " Try uploading a different file.";
  }

  setStatus(uploadStatus, `Upload failed: ${errorMsg}`);
}
```

### 任务状态轮询

```javascript
async function pollTaskStatus(taskId) {
  try {
    const response = await fetch(`http://127.0.0.1:9011/api/v1/task/query/${taskId}`);
    const data = await response.json();
    parseApiResponse(data, "Query task failed");

    return data.data;
  } catch (error) {
    console.error("Poll task failed:", error);

    // 特殊处理任务不存在的情况
    if (error.code === 50002) {
      setStatus(uploadStatus, "Task not found. It may have expired.");
      // 停止轮询
      if (indexingTimer) {
        clearInterval(indexingTimer);
        indexingTimer = null;
      }
    }

    return null;
  }
}
```

---

## 📊 错误处理流程图

```
API调用
   ↓
HTTP检查 (response.ok)
   ├─ ✗ → 抛出HTTP错误
   ↓
解析JSON
   ↓
业务码检查 (parseApiResponse)
   ├─ 20000 → 成功，返回数据
   ├─ 40xxx → 客户端错误
   └─ 50xxx → 服务端错误
   ↓
生成友好错误消息
   ↓
显示给用户
```

---

## 💡 错误提示示例

### 成功场景
```
✅ Upload and indexing completed successfully! (1 chunk processed in 48s)
✅ Search completed: 12 results found.
```

### 错误场景

#### 文件格式错误 (50001)
```
❌ Upload failed: Unsupported file format. Please check the file type.
   Supported formats: .mp4, .jpg, .png, .pdf, .docx, .txt, .html, .md
```

#### 文件已存在 (40901)
```
❌ Upload failed: File already exists. This file has been uploaded before.
   Try uploading a different file.
```

#### 任务不存在 (50002)
```
❌ Task not found. It may have expired or been deleted.
```

#### 处理失败 (50003)
```
❌ Indexing failed: Processing failed. An internal error occurred.
```

#### HTTP网络错误
```
❌ Upload failed: HTTP 500: Internal Server Error
❌ Search failed: HTTP 422: Unprocessable Entity
```

---

## 🔍 调试技巧

### 1. 浏览器控制台查看

打开浏览器开发者工具 (F12)：

**Console标签**：查看错误日志
```javascript
Poll task failed: Error: Task not found. The task may have expired or been deleted.
    at parseApiResponse (app.js:42)
    code: 50002
    errorType: "TASK_NOT_FOUND"
    originalMessage: "Task ID does not exist or has expired"
```

**Network标签**：查看API响应
```json
{
  "code": 50002,
  "data": {},
  "message": "Task ID does not exist or has expired",
  "timestamp": 1776128017
}
```

### 2. 错误对象属性

错误对象包含以下属性：

```javascript
error = {
  message: "Task not found. The task may have expired or been deleted.",
  code: 50002,
  errorType: "TASK_NOT_FOUND",
  originalMessage: "Task ID does not exist or has expired"
}
```

- `message`: 用户友好的错误消息
- `code`: 业务状态码
- `errorType`: 错误类型名称
- `originalMessage`: 后端返回的原始消息

---

## 🛠️ 自定义错误处理

### 添加新的错误码

如果后端添加了新的错误码，在 `ERROR_CODES` 和 `getErrorMessage` 中添加：

```javascript
const ERROR_CODES = {
  // ... 现有代码
  50004: "QUOTA_EXCEEDED",  // 新增
};

function getErrorMessage(code, defaultMessage) {
  const errorMessages = {
    // ... 现有代码
    50004: "Storage quota exceeded. Please delete old files.",  // 新增
  };
  // ...
}
```

### 针对特定场景的处理

在catch块中根据错误码做特殊处理：

```javascript
catch (error) {
  if (error.code === 50001) {
    // 文件格式错误 - 显示支持的格式
    showFormatHelp();
  } else if (error.code === 40901) {
    // 文件已存在 - 提供跳过选项
    askUserToSkip();
  } else {
    // 通用错误处理
    showGenericError(error.message);
  }
}
```

---

## 📚 最佳实践

### ✅ 推荐做法

1. **始终使用 parseApiResponse**
   ```javascript
   const data = await response.json();
   parseApiResponse(data, "Operation failed");
   ```

2. **提供上下文相关的默认消息**
   ```javascript
   parseApiResponse(data, "Search failed");  // 搜索场景
   parseApiResponse(data, "Upload failed");  // 上传场景
   ```

3. **针对特定错误码提供额外帮助**
   ```javascript
   if (error.code === 50001) {
     errorMsg += " Supported formats: ...";
   }
   ```

4. **记录错误到控制台**
   ```javascript
   console.error("Operation failed:", error);
   ```

### ❌ 避免做法

1. **不要忽略业务状态码**
   ```javascript
   // ❌ 错误
   const data = await response.json();
   return data.data;  // 没有检查 code
   ```

2. **不要直接显示技术错误**
   ```javascript
   // ❌ 错误
   alert(error.stack);  // 用户看不懂
   
   // ✅ 正确
   setStatus(uploadStatus, error.message);  // 友好提示
   ```

3. **不要吞掉错误**
   ```javascript
   // ❌ 错误
   try {
     await performSearch();
   } catch (error) {
     // 静默失败，用户不知道发生了什么
   }
   ```

---

## 🎯 测试场景

### 手动测试清单

- [ ] 正常搜索（20000）
- [ ] 搜索无结果
- [ ] 上传成功（20000）
- [ ] 上传不支持的文件格式（50001）
- [ ] 上传已存在的文件（40901）
- [ ] 查询不存在的任务（50002）
- [ ] 网络断开（HTTP错误）
- [ ] 服务器错误（500）

### 模拟错误响应

在开发者工具中可以用以下方式模拟错误：

```javascript
// 临时修改 parseApiResponse 进行测试
function parseApiResponse(data) {
  // 模拟文件格式错误
  throw Object.assign(new Error("Unsupported file format"), {
    code: 50001,
    errorType: "FILE_TYPE_ERROR"
  });
}
```

---

## 📝 更新日志

### v1.1 (2026-04-13)
- ✅ 添加业务状态码支持
- ✅ 实现 `parseApiResponse` 统一解析
- ✅ 添加友好错误消息映射
- ✅ 在所有API调用中应用错误处理
- ✅ 针对特定错误码提供额外提示

### v1.0 (2026-04-13)
- ✅ 基础API集成
- ✅ 简单错误处理

---

**文档版本**: v1.1  
**最后更新**: 2026-04-13  
**维护者**: Claude Sonnet 4.5
