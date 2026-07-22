# Grading UI 集成设计

grading 功能作为一块**相对独立的子界面**接入 Smart Classroom 前端（`smart-classroom/ui`）：
从主 UI 点按钮 `window.open` 弹出一个新浏览器窗口，窗口内是一个带路由的两页 grading 应用
（main 页 + results 页）。复用现有前端工程的 api 层 / i18n / 样式约定，同时给 grading 后端
补一个读取 summary.json 的接口。

配套：REST 契约见 [api_reference.md](api_reference.md)。

---

## 0. 已确认决策

| 议题 | 决策 |
|---|---|
| 独立形态 | **同一 SPA 内 `window.open` 新浏览器窗口**（同一份 Vite 构建、同一端口、同一 `api.ts`，靠路由区分）|
| 页面路由 | **引入 `react-router-dom`**，两页真正 URL 路由：`/grading`（main）、`/grading/results`（results）|
| results 数据源 | **新增后端接口读 `summary.json`**：按 `task_id` 直接返回 `outputs/<task_id>/summary.json`，运行中也可读（不要求 COMPLETED）|
| 输出目录键 | **彻底去掉 `exam_id`**，一律以 `task_id` 作为区分任务、归集输出的唯一键（`outputs/<task_id>/`）|

---

## 1. 现状约束（集成前提）

| 事项 | 现状 | 对集成的影响 |
|---|---|---|
| 前端形态 | Vite + React 19 SPA，`npm run dev`(5173)，也可 Electron 打包 | grading 是同一 SPA 内的新路由，新窗口指向同源 `/grading` |
| 路由 | **未装 react-router**，靠 `activeScreen` 单 state 切屏 | 本次引入 react-router-dom |
| 主后端 | `8000`，`VITE_API_BASE_URL`，CORS 直连；`App.tsx` 进入前先 ping `8000/health`，不通整页停在 "Backend Not Available" | 见 §7 风险：新窗口应绕开这个全局门禁 |
| 内容搜索后端 | `9011`，Vite 代理 `/api/v1` → 127.0.0.1:9011（避 CORS）| grading 后端 `9012` 照抄这条代理路子，用**独立前缀** |
| 状态管理 | Redux Toolkit（7 slice）；REST 集中在 `services/api.ts`（fetch + `safeApiCall`）| grading 先用局部 state |
| 数据刷新 | 轮询为主（`setInterval`/`setTimeout` hook）| grading 是轮询模型，无需 WebSocket |
| 国际化 | i18next，中英 `i18n/en.json` / `zh.json` | 新增 `grading.*` 文案键 |

---

## 2. 目标与非目标

**目标**
- 主 UI 提供入口，`window.open` 弹出独立窗口运行 grading 子应用。
- grading 子应用两页：
  - **main 页** `/grading`：用户操作主程序（选/传 rubric → 以「目标目录 + rubric」启动评分 → 看任务进度与控制）。
  - **results 页** `/grading/results`：以**表格**形式展示最终结果，随时查看最新 `summary.json`。
- 不破坏 main / content-search 现有行为。
- grading 后端补一个 summary 读取接口。

**非目标（本期不做）**
- 不做 rubric 在线编辑器（仅列出 + 选择 + 上传）。
- results 页先做表格 + 原始 JSON 查看，不做富可视化。
- 不引入 WebSocket。
- 不改 §7 提到的主后端 8000 全局门禁的整体逻辑（仅让新窗口绕开）。

---

## 3. 用户操作流程（对应两页）

```
main 页 /grading
 a. 选择已有 rubric（GET /rubrics）  或  上传新 rubric（POST /rubrics/upload）
 b. 填「目标目录」paper_path + 选定的 rubric_path
    → 启动评分（POST /grading/tasks）→ 得 task_id
 c. 轮询任务状态（GET /grading/tasks/{id}）看 progress / current_step，
    可 pause / resume / cancel
    ↓ 提供入口跳到 results 页（带上 task_id）
results 页 /grading/results?task_id=<...>
 d. 轮询 summary（GET /grading/tasks/{task_id}/summary）
    → 表格展示已判完的学生，运行中也实时增行
```

要点：`task_id` 是把 main 页任务与 results 页数据关联起来的唯一键。创建任务时返回 `task_id`，
main 页启动后把它传给 results 页（URL 参数）——不再有 `exam_id` 之类的用户自定义 id。

---

## 4. 新窗口方案（window.open）

主 UI 入口按钮：
```ts
window.open('/grading', 'grading', 'width=1280,height=860');
```
- 目标 `/grading` 与主应用**同源、同一份构建**，浏览器新开一个窗口加载同一 SPA，由 react-router
  渲染 grading 子树。因此天然共享 `api.ts` / i18n / 样式，无需第二套工程。
- 新窗口是独立 `window`，有自己的 React 树与 Redux store 实例（各窗口互不共享内存状态，靠后端与 URL 参数通信——本场景正好合适）。

**关键：新窗口要绕开主后端 8000 的全局健康门禁**（见 §7.1）。做法是让 grading 路由**不经过**
`App.tsx` 那段 8000 ping 逻辑——在路由层把 `/grading/*` 挂在健康门禁**之外**（见 §5.1）。

---

## 5. 前端改动

### 5.1 路由结构（引入 react-router）
在 `main.tsx` 用 `BrowserRouter` 包裹，顶层按路径分流，让 grading 与主应用**并列**，
使 grading 不被主应用的 8000 健康门禁包住：

```
<BrowserRouter>
  <Routes>
    <Route path="/grading"          element={<GradingMainPage />} />
    <Route path="/grading/results"  element={<GradingResultsPage />} />
    <Route path="/*"                element={<App />} />   {/* 现有主应用，含 8000 门禁 */}
  </Routes>
</BrowserRouter>
```
- 现有 `App`（含 `pingBackend()` 门禁与 activeScreen 三态：main / content-search）整体挪到 `/*`，行为不变。
- grading 两页独立于 `App`，各自只判 grading 后端 9012 是否可达。

### 5.2 grading 子应用目录 `components/Grading/`
| 组件 | 页 | 职责 |
|---|---|---|
| `GradingMainPage.tsx` | main | 页面容器 + 顶部到 results 的入口链接 |
| `RubricPicker.tsx` | main | 列 rubric（GET /rubrics）+ 上传（POST /rubrics/upload）+ 选定 |
| `StartGradingForm.tsx` | main | 输入目标目录 paper_path + rubric_path → 启动任务，拿到 task_id |
| `TaskProgress.tsx` | main | 当前任务 progress/current_step + pause/resume/cancel 按钮 |
| `GradingResultsPage.tsx` | results | 页面容器：读 `?task_id=`，轮询 summary |
| `ResultsTable.tsx` | results | 表格渲染 summary.json 的 students（见 §6 列定义）|
| `StudentDetailModal.tsx` | results | （可选）点某行看该生逐题明细 |

### 5.3 API 层（`services/api.ts` 追加 grading 组）
全部走独立前缀、`safeApiCall` 包裹。除已有 8 个端点外，**新增 summary 端点**（§8 后端改动）：

| 函数 | 方法 & 路径 |
|---|---|
| `gradingListRubrics()` | GET `/rubrics` |
| `gradingUploadRubric(file)` | POST `/rubrics/upload` (multipart) |
| `gradingCreateTask({paper_path, rubric_path?})` | POST `/grading/tasks` |
| `gradingListTasks(status?)` | GET `/grading/tasks?status=` |
| `gradingGetTask(taskId)` | GET `/grading/tasks/{id}` |
| `gradingPause/Resume/Cancel(taskId)` | POST `/grading/tasks/{id}/{action}` |
| `gradingGetTaskSummary(taskId)` | **GET `/grading/tasks/{task_id}/summary`（新增）** |

常量：`const GRADING_API_URL = env.VITE_GRADING_API_URL || '/grading-api';`（对标 `CONTENT_SEARCH_API_URL`）。

### 5.4 轮询 hooks
- `useGradingTaskPoll(taskId)`：main 页轮询任务状态，终态（COMPLETED/FAILED/CANCELLED）停轮询。
- `useTaskSummaryPoll(taskId)`：results 页每 3–5s 轮询 summary，展示最新表格；任务终态后可降频或停。
- 均对标现有 `useResourceMetricTimer` 的 `setInterval` + `useEffect` cleanup 模式。

### 5.5 连通 9012（Vite 代理，同 content-search 做法）
`vite.config.ts` 加独立前缀（`/api/v1` 已被 9011 占用，**不能复用**）：
```ts
'/grading-api': {
  target: 'http://127.0.0.1:9012',
  changeOrigin: true,
  rewrite: p => p.replace(/^\/grading-api/, '/api/v1'),
},
```
Electron 桌面版若要访问 9012，需在 `electron/server.cjs` 加同样反代（现有已为 9011 做过，照抄）。

### 5.6 i18n & 样式
- `i18n/en.json` / `zh.json` 加 `grading.*`（按钮、状态标签、表单占位、表格表头、错误提示）。
- `assets/css/Grading*.css`。

### 5.7 状态管理
先局部 `useState`/`useReducer`（新窗口独立 store，无跨窗共享需求）。确有跨页共享再加 `gradingSlice`。

---

## 6. results 表格（summary.json → 列）

数据来自 `outputs/<task_id>/summary.json`（结构见 api_reference「输出文件」节）。表格建议列：

| 列 | 来源字段 |
|---|---|
| # | students 的序号 key |
| 学号 | `student.exam_number` |
| 姓名 | `student.student_name` |
| 班级 | `student.class_name` |
| 客观分 | `objective_score / objective_max` |
| 主观分 | `subjective_score / subjective_max` |
| 总分 | `total_score / total_max` |
| 详情 | 展开 `student.questions`（逐题 catalog/type/score/max_score）|

表头元信息：`metadata.paper_title` / `metadata.subject` / `metadata.task_id`。
`student_count` 显示已判人数；缺失的 header 字段（name/class/no 可能为 null）显示占位符。

---

## 7. 风险与决策点

1. **主后端 8000 全局门禁 vs grading 独立性**（本次核心）
   现状 `App.tsx` 进入前先 ping 8000，不通整页阻断。grading 要求相对独立，**不应受 8000 存活影响**。
   本设计的解法：把 grading 路由挂在 `App` 之外（§5.1），使新窗口的 `/grading/*` 不经过 8000 门禁，
   只判 9012。→ **不改动主应用的门禁逻辑本身**，只是让 grading 路由并列于门禁之外。

2. **代理前缀冲突**：`/api/v1` 已归 9011，grading 必须用独立前缀 `/grading-api`。

3. **CORS**：9012 若未开 CORS，则必须走代理（dev=Vite，Electron=server.cjs），不能直连。

4. **`paper_path` 是服务器路径，不是浏览器文件**：用户填的「目标目录」是 grading 后端可见的
   服务器路径，无法用 `<input type=file>` 传目录。表单需明确提示。rubric 可用上传接口。

5. **task_id 关联**：results 页依赖 `task_id` 查 summary。`task_id` 由 `POST /grading/tasks` 返回，
   main 页须把它传给 results 页（URL 参数），否则 results 页不知道查哪个任务。已彻底去掉用户自定义的
   `exam_id`——不存在“未显式传就取目录名”的兜底，`task_id` 是唯一键。

6. **summary.json 尚不存在时**：任务刚启动、还没有任何学生判完时 `summary.json` 可能不存在。
   新接口应返回「空 summary」而非 404，results 页显示「暂无结果，评分进行中」。

7. **多窗口/多任务轮询开销**：新窗口各自轮询；results 页任务终态后应降频或停轮询。

---

## 8. 后端改动（grading 服务，已落地）

**GET `/api/v1/grading/tasks/{task_id}/summary`**，读取 `outputs/<task_id>/summary.json`：

- 存在 → 返回其 JSON 内容（原样，含 metadata/students/updated_at/student_count）。
- 不存在（任务刚起、无人判完）→ 返回**空壳**：`{"metadata": {"task_id": <id>}, "students": {}, "student_count": 0}`，HTTP 200。
- `task_id` 校验：只允许目录名字符，防止路径穿越（拒绝含 `/`、`\`、`..` 及空值）。
- 不要求任务 COMPLETED——运行中即可读，满足「随时查看最新」。
- 任务创建时即 seed 一个空 summary（`_seed_empty_summary`），因此从任务存在起就返回 200。

落点（对标已有 `list_rubrics` / `list_tasks`）：
- `services/grading_service_impl.py`：`get_task_summary(task_id)`，读 `_COMPONENT_ROOT/outputs/<task_id>/summary.json`。
- `api/schemas.py`：`TaskSummaryJsonResponse` 薄包装。
- `api/routes.py`：`GET /grading/tasks/{task_id}/summary`，`ValueError`→400（非法 task_id）。
- 输出目录键彻底改为 `task_id`：去掉 `GradingTaskCreateRequest.exam_id`，`outputs/<task_id>/...`。

---

## 9. 分阶段落地

1. **后端接口**（已完成）：`GET /grading/tasks/{task_id}/summary` + 更新 api_reference。
2. **路由骨架**：装 react-router-dom；`main.tsx` 顶层分流，grading 两页占位路由并列于 `App` 之外；主 UI 加 `window.open('/grading')` 入口按钮；Vite `/grading-api` 代理；api.ts 的 grading 函数组。验证 9012 连通。
3. **main 页**：RubricPicker + StartGradingForm + TaskProgress + `useGradingTaskPoll` + 状态机禁用逻辑（PAUSING 时禁 resume，见 api_reference）。
4. **results 页**：ResultsTable + `useTaskSummaryPoll`，表格随 summary 实时增行。
5. **打磨**：i18n 补全、空 summary/错误态、Electron 反代（如需桌面版）。

---

## 10. 改动文件清单（预估）

**后端**（已完成）
- `components/grading/services/grading_service_impl.py`（`get_task_summary` + `_seed_empty_summary`；去 exam_id）
- `components/grading/api/routes.py`（summary 路由）
- `components/grading/api/schemas.py`（`TaskSummaryJsonResponse`；去 exam_id）
- `components/grading/doc/api_reference.md`（端点 + 输出布局）

**前端 · 改**
- `ui/src/main.tsx`（BrowserRouter + 顶层 Routes）
- 主 UI 某处（入口按钮 `window.open('/grading')`——放 TopPanel 或 Menu）
- `ui/src/services/api.ts`（grading 函数组 + 类型 + GRADING_API_URL）
- `ui/vite.config.ts`（/grading-api 代理）
- `ui/src/i18n/en.json`、`zh.json`（grading.*）
- `ui/package.json`（+react-router-dom）
- （如打桌面版）`ui/electron/server.cjs`（9012 反代）

**前端 · 新增**
- `ui/src/components/Grading/GradingMainPage.tsx`、`GradingResultsPage.tsx`、`RubricPicker.tsx`、`StartGradingForm.tsx`、`TaskProgress.tsx`、`ResultsTable.tsx`、（可选 `StudentDetailModal.tsx`）
- `ui/src/hooks/useGradingTaskPoll.ts`、`useTaskSummaryPoll.ts`
- `ui/src/assets/css/Grading*.css`
