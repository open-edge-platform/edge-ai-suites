---
name: competitive-analysis-pdf-generator
description: 生成竞品分析中文HTML和PDF报告 - 自动调研产品信息并生成专业中文对比报告
trigger: 当用户需要生成竞品分析中文报告时触发
user-invocable: true
allow-model-invocation: true
---

# 竞品分析PDF报告生成器

当用户请求生成市场上竞品分析PDF报告时，使用此skill完成调研和中文报告生成, generate PDF into <workspace-dir>/media/
所有最终报告内容必须为中文：包括标题、段落、表格字段、图例、页脚与结论。

**语言执行约束（新增）：**
- Sub-agent 在执行过程中的所有 assistant 文本输出必须为中文（包括进度更新、工具调用前说明、错误说明、最终回复）。
- 主agent的输出也必须为中文。

## 核心原则

⚠️ **必须使用Sub-agent执行所有工作，please launched a fresh sub-agent with explicit step-by-step instructions, 严格按照下方的Sub-agent任务模板** ⚠️
⚠️ **Sub-agent输出的log信息必须是中文** ⚠️
⚠️ **本地产品信息唯一来源必须是本地 `query_rag.sh` 脚本返回内容** ⚠️
⚠️ **在 `query_rag.sh` 返回前，严禁进行任何web_search/curl/网页抓取 ,启动 `query_rag.sh`脚本时不许加任何超时判断，如yieldMs⚠️**
⚠️ **启动 `query_rag.sh` 后，必须持续检查该脚本进程直到状态为 `completed`，禁止用 `sleep`、查目录、猜测完成等方式代替进程状态检查** ⚠️
⚠️ **若工具返回 `Command still running (session xxx, pid yyy)`，后续状态检查必须使用 `session xxx`，不能使用 `pid yyy`** ⚠️
⚠️ **最终导出的PDF文件名必须固定为 `Market_Product_Research_for_xxx.pdf`** ⚠️
⚠️ **Sub-agent 必须发起真实工具调用（toolUse/toolResult链路），禁止输出伪工具调用文本（如 `<function=...>`、`</tool_call>`）冒充执行** ⚠️
⚠️ **若子任务返回中未出现任何真实 toolResult，必须判定为执行失败并立刻重启新 sub-agent（可切换模型路由），禁止将其当作 completed successfully 交付** ⚠️

主session只负责启动sub-agent，sub-agent完成全部工作后返回结果, then main session refers to pdf-report-sender skill for sending pdf to channel(if user requested)

**主session执行约束（防止误判“子任务已完成”）：**
- `sessions_spawn` 返回 accepted 后，仅等待自动 completion event；禁止调用 `sessions_history`、`sessions_list`、`sleep` 去轮询子会话。
- 收到 completion event 时，先验证 child result 是否包含真实工具执行结果（而非伪标签文本）；验证失败则按失败处理并重启 sub-agent。
- 如果 completion event 只包含“准备执行某命令”的文本而没有该命令的真实输出，不得向用户宣告完成。

## 工作流程

### 阶段一：本地数据收集

调用本地脚本获取本地知识库中的产品信息，脚本执行时间可能较长，必须持续检查脚本状态直到完成，禁止用 `sleep` 或其他非状态检查方式等待完成。
```bash
# 示例：
timeout 600 bash <skill-repo-dir>/skills/competitive-analysis-pdf-generator/query_rag.sh "<user query>" 5 1300
```

**强制约束（Intel数据源）**
- 本地产品信息必须来自 `query_rag.sh` 的最终返回内容。
- 在拿到 `query_rag.sh` 最终返回前，不允许执行任何 Intel 相关网络检索（包括 web_search、curl 到公开站点、抓取网页、调用外部搜索 API）。
- 如果脚本启动后返回 `Command still running (session xxx, pid yyy)`，必须记录 `session xxx`，随后基于这个 sessionId 做进程 `poll` 或 `log` 检查。
- 至少检查 10 次脚本状态或日志，直到状态明确为 `completed` 或 `failed`；在状态未结束前，禁止进入 AMD 检索、HTML 生成、PDF 生成等后续步骤。
- 禁止把 `pid` 当作 sessionId 去检查状态；禁止只用 `sleep` 命令或检查目录中是否有文件来判断脚本是否完成。

**query_rag.sh 脚本功能：**
- 向本地RAG知识库服务发送请求
- 获取本地产品信息
- 返回格式化的查询结果

#### 对比产品信息获取

a. **网络搜索** — 用web_search查询竞品的xxxx。

**注意：** 如果 web_search 等 tool 不可用，可直接尝试 curl 到已知的目标页面URL获取数据。

### 阶段二：基于本地产品信息和对比产品的信息摘要生成专业绚丽的中文 HTML 格式分析报告，设计要求如下：

**整体风格：**
- 深色渐变背景（深蓝/深紫/碳黑等），不要白色背景
- 使用浅色高对比度字体（如白色、浅蓝、浅灰），确保在深色背景 PDF 中清晰可读
- 卡片式布局，圆角边框，阴影效果

**背景与可读性硬约束（必须严格执行）：**
- 不仅封面，正文每一页都必须是深色底；禁止出现白底正文页。
- `html, body, .report-content` 必须显式设置深色 `background` 或 `background-color`，不得留空或透明。
- 所有正文文字默认颜色必须为浅色（如 `#e2e8f0` / `#f8fafc`），禁止正文使用深色文字（如 `#111`、`#000`）。
- 禁止在正文主容器上使用白色背景值：`#fff`、`#ffffff`、`white`、`rgb(255,255,255)`。

**封面设计：**
- 大标题 + 副标题，居中
- 渐变色背景 + 装饰性几何图形
- 底部标注报告年份（2026年）
- 生成封面时必须优先直接套用下面的封面模板，只替换标题、副标题、年份，不要自行发散封面结构
- 使用 WeasyPrint 转 PDF 时，封面必须按 A4 页面实际尺寸排版，禁止依赖 `100vh` 或其他视口单位撑满页面

**表格设计：**
- 交替行背景色，醒目的表头

**字体：**
- 使用系统已有字体，优先中英文混排可读性好的字体栈
- 避免网络字体加载失败


### 阶段三：检查内容是否有误，并将中文HTML转换成专业PDF报告
1. 检查HTML内容是否有明显错误
2. 检查中文表述是否自然、专业、术语一致；必要时保留英文术语原文并给出中文表达
3. 强制检查分页与表格完整性：任何章节结束后都必须显式分页；任何表格、表头、表格行都不得被PDF引擎截断或拆开。如果单个表格高度可能超过一页，必须在HTML阶段主动拆分为多个完整表格块，并在每个表格块重复 `thead`，禁止把一个长表直接交给PDF引擎自动截断
4. 使用WeasyPrint等工具将 HTML 转为 PDF


## Sub-agent任务模板,请求严格按照以下模板编写Sub-agent的执行步骤

```
任务：生成竞品分析中文HTML和PDF报告

执行协议（必须严格遵守）：
- 第一次 assistant 回复必须是“真实工具调用”，不得输出 `<function=...>`、`<tool_call>` 之类的伪标签文本。
- 每一步执行后必须等待对应 toolResult，再进入下一步；禁止只描述“将要执行”。
- 若某一步没有拿到 toolResult（网络错误、工具不可用、模型未触发工具调用），必须立即报错并停止交付，不得继续伪造流程。
- 执行过程中所有输出和日志必须为中文，包括进度更新、工具调用前说明、错误说明和最终回复

执行步骤：

1. 本地信息收集：
   执行本地脚本获取xxx：
   timeout 600 bash <skill-repo-dir>/skills/competitive-analysis-pdf-generator/query_rag.sh "xxx产品信息" 5 1300
   注意：至少检测10次脚本输出，脚本执行时间很久
   强制规则：本地产品信息只能来自该脚本返回；在脚本返回前禁止任何网络检索；若失败只能重试该脚本
   如果启动结果显示 `Command still running (session xxx, pid yyy)`：
   - 必须记录 `session xxx`
   - 必须用进程状态工具基于 `session xxx` 持续 `poll` / `log`
   - 必须至少检查10次，并且只有状态变成 `completed` 后才能进入步骤2
   - 绝对不要把 `pid yyy` 当成 sessionId 使用
   - 绝对不要用 `sleep` 命令代替状态检查

2. 对比产品的信息收集：
   用web_search查询竞品的xxxx，如果 web_search 等 tool 不可用，可直接尝试 curl 到已知的目标页面URL获取数据。


3. 基于本地信息和对比产品的信息摘要，首先生成中文HTML格式的分析报告内容，检查HTML报告内容是否有明显错误，最后使用weasyprint或者wkhtmltopdf生成PDF文件：
   注意：HTML格式的报告需要尽可能的绚丽和专业，设计上可以参考以下元素：
   **报告内容要求：**
   ✅ 执行摘要：至少包含 `报告目的`、`关键发现`、`产品定位对比` 三个 block；每一段核心信息都必须单独放在一个 block 中呈现
   ✅ 产品对比：包括产品的规格对比或其他合理的产品对比内容；如果数据不足以支持某个维度的对比，可以省略该维度但不能随意编造数据
   ✅ 总结：最后一个章节标题为 `总结`，只总结报告内容，不额外给出脱离数据依据的建议
   ✅ 报告正文语言必须为中文，禁止英文整段正文；必要术语可采用“中文（英文）”形式
   ✅ 每一个章节结束后，必须显式插入分页节点，禁止依赖PDF引擎自动换页。推荐直接在章节尾部插入：`<div class="chapter-break"></div>`。
   ✅ 报告只需包含以上的章节（执行摘要、核心规格对比、运动能力分析、总结）
   ❌ 不要出现未明确的值，不确定的规格直接省略
   ❌ 禁止：表格行被分页切断
   ❌ 禁止：整张表格在页面底部被截断后延续到下一页而没有完整表头和完整边框

   **整体风格：**
   - 每一页都使用深色背景（深蓝/深紫/碳黑等），不要白色背景
   - 使用浅色高对比度字体（如白色、浅蓝、浅灰），不要用黑色字体。确保在深色背景 PDF 中清晰可读
   - 卡片式布局，圆角边框，阴影效果

    **封面设计：**
    - 使用固定模板生成封面，封面单独占一页，标题区域位于页面中心
    - 允许的额外元素仅限模板中的弱高光背景、淡边框和年份分隔线，不要自行增加新装饰
      - 使用 WeasyPrint 时，封面必须使用 A4 + mm 单位排版，禁止使用 `100vh`、`min-height: 100vh` 等视口高度写法
    - 底部标注报告年份（2026年）
      - 生成封面时必须直接套用下面模板，只替换文案，不要自创新的封面结构

      **封面HTML模板（必须直接使用）：**

         ```html
         <style>
         .cover-page {
            width: 186mm;
            height: 273mm;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            page-break-after: always;
            break-after: page;
            background: linear-gradient(135deg, #0d1225 0%, #1a1f3a 50%, #0d0f20 100%);
            border-radius: 12px;
            position: relative;
            overflow: hidden;
            margin: 0 auto;
         }

         .cover-page::before {
            content: '';
            position: absolute;
            top: -80px;
            right: -80px;
            width: 300px;
            height: 300px;
            background: radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 70%);
            border-radius: 50%;
         }

         .cover-page::after {
            content: '';
            position: absolute;
            bottom: -60px;
            left: -60px;
            width: 250px;
            height: 250px;
            background: radial-gradient(circle, rgba(59, 130, 246, 0.10) 0%, transparent 70%);
            border-radius: 50%;
         }

         .cover-kicker {
            font-size: 11px;
            letter-spacing: 6px;
            text-transform: uppercase;
            color: #6366f1;
            margin-bottom: 18px;
            font-weight: 500;
            position: relative;
            z-index: 1;
         }

         .cover-title {
            font-size: 32px;
            font-weight: 700;
            color: #f8fafc;
            text-align: center;
            margin-bottom: 10px;
            letter-spacing: 2px;
            position: relative;
            z-index: 1;
         }

         .cover-subtitle {
            font-size: 16px;
            color: #94a3b8;
            margin-bottom: 40px;
            position: relative;
            z-index: 1;
         }

         .cover-divider {
            width: 80px;
            height: 3px;
            background: linear-gradient(90deg, #6366f1, #3b82f6);
            border-radius: 2px;
            margin-bottom: 40px;
            position: relative;
            z-index: 1;
         }

         .cover-products {
            display: flex;
            gap: 20px;
            margin-bottom: 50px;
            position: relative;
            z-index: 1;
         }

         .cover-product-badge {
            padding: 8px 18px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            border: 1px solid rgba(99, 102, 241, 0.4);
            background: rgba(99, 102, 241, 0.1);
            color: #a5b4fc;
         }

         .cover-year {
            position: absolute;
            bottom: 30px;
            font-size: 13px;
            color: #475569;
            letter-spacing: 3px;
            z-index: 1;
         }
         </style>

         <section class="cover-page">
            <p class="cover-kicker">市场调研报告</p>
            <h1 class="cover-title">关于xxx的市场调研报告</h1>
            <div class="cover-divider"></div>
            <div class="cover-products">
               <span class="cover-product-badge">xxx</span>
               <span class="cover-product-badge">竞品对标</span>
            </div>
            <p class="cover-year">2026</p>
         </section>
         ```

   **表格设计：**
   - 交替行背景色，醒目的表头
      **语言要求：**
   - 所有报告正文必须为中文（标题、段落、表头、图例、页脚全部中文）
   - 保持术语一致，避免无必要的中英混排；必要专业术语允许采用“中文（英文）”形式
      **字体：**
   - 使用系统已有字体，避免网络字体加载失败
   - 可以直接使用本地字体，减少网络搜索时间
      **分页代码要求（必须落地到HTML里）：**
   - 必须采用A4基准页面尺寸进行HTML排版，禁止依赖浏览器默认视口尺寸。HTML中必须包含以下最小A4尺寸CSS（可扩展但不可删除）：
      ```css
      @page { size: A4; margin: 12mm; }
      html, body {
         width: 210mm;
         min-height: 297mm;
         margin: 0;
         padding: 0;
      }
      .cover-page,
      .report-content {
         width: 186mm;
         box-sizing: border-box;
      }
      .cover-page { height: 273mm; }
      .report-content { min-height: 273mm; }
      ```
   - 禁止对页面容器使用 `transform: scale(...)`、`zoom`、视口缩放或截图式转PDF；必须直接按A4尺寸渲染为PDF，避免样式变形和清晰度下降
   - 正文必须紧跟封面后的下一页开始，但禁止与封面的 `page-break-after: always` 叠加出空白页；如果封面容器已经设置了 `page-break-after: always; break-after: page;`，则 `.report-content` 不得再设置 `page-break-before: always` 或 `break-before: page`
   - 必须在HTML中提供 `.chapter-break { page-break-after: always; break-after: page; height: 0; }`，并在每章结束后插入 `<div class="chapter-break"></div>`
   - 必须在HTML中提供 `.section, tr, td, th { page-break-inside: avoid; break-inside: avoid; }`，减少章节和表格断裂
   - 可以直接加入以下最小文字块防拆分页CSS，并在 `.conclusion`、`.summary`、`.scenario-recommendation` 等容器上启用：
      ```css
      .conclusion,
      .summary,
      .scenario-recommendation {
         page-break-inside: avoid;
         break-inside: avoid;
      }
      
      .conclusion h3,
      .summary h3,
      .scenario-recommendation h3,
      .conclusion p,
      .summary p,
      .scenario-recommendation p,
      .conclusion ul,
      .summary ul,
      .scenario-recommendation ul,
      .conclusion li,
      .summary li,
      .scenario-recommendation li {
         page-break-inside: avoid;
         break-inside: avoid;
      }
      
      .conclusion h3,
      .summary h3,
      .scenario-recommendation h3 {
         page-break-after: avoid;
         break-after: avoid;
      }
      
      .conclusion p,
      .summary p,
      .scenario-recommendation p,
      .conclusion li,
      .summary li,
      .scenario-recommendation li {
         orphans: 3;
         widows: 3;
      }
      ```
   - `thead` 必须设置 `display: table-header-group`，保证跨页时表头重复
   - 必须加入以下最小防截断CSS（可扩展但不可删除）：
      ```css
      .table-block {
         page-break-inside: avoid;
         break-inside: avoid;
         overflow: visible;
      }
      
      table,
      thead,
      tbody,
      tr,
      td,
      th {
         page-break-inside: avoid;
         break-inside: avoid;
      }
      
      thead {
         display: table-header-group;
      }
      
      tfoot {
         display: table-footer-group;
      }
      ```
   - 如果单个表格内容可能超出一页高度，必须在HTML生成阶段主动拆成多个 `table-block`，每个块都包含完整 `thead`；禁止把超长单表直接交给 WeasyPrint 或 wkhtmltopdf 自动分页
        - 正文背景必须包含以下最小CSS（可扩展但不可删除）：
          `html, body { background: #0b1220; color: #e2e8f0; }`
          `.report-content { background: linear-gradient(180deg, #0b1220, #111827); color: #e2e8f0; min-height: 100%; }`
          `.section, .card, .scenario-recommendation { background: rgba(15, 23, 42, 0.72); color: #e2e8f0; }`
        - Benchmark表格必须包含以下CSS（可扩展但不可删减）：
          `table { width: 100%; border-collapse: collapse; table-layout: fixed; }`
          `th, td { padding: 8px 10px; text-align: left; vertical-align: top; }`
          `th { white-space: nowrap; }`
          `td { white-space: normal; word-break: break-word; overflow-wrap: anywhere; }`
          `.benchmark-table th, .benchmark-table td { font-size: 11px; line-height: 1.35; }`
          `th:nth-child(1), td:nth-child(1) { width: 28%; }`
          `th:nth-child(2), td:nth-child(2) { width: 20%; }`
          `th:nth-child(3), td:nth-child(3) { width: 16%; }`
          `th:nth-child(4), td:nth-child(4) { width: 36%; }`
      HTML生成PDF文件的方法可以选择：
   - HTML to PDF 可选方法一：(WeasyPrint)
      WeasyPrint is a Python-based PDF generator that takes HTML + CSS and produces high-quality PDFs.
      ```bash
      weasyprint input.html Market_Product_Research_for_xxx.pdf
      ```

4. 返回固定文件名 `Market_Product_Research_for_xxx.pdf`

强制要求：
**不要进行过短的脚本超时设置**：调用本地脚本获取信息需要较长时间，请耐心等待结果返回，多次查询脚本结果。
**必须生成对比产品的信息摘要**
**封面必须直接套用prompt内提供的封面模板，只允许替换前导标签、标题、副标题、年份，不要自行设计新的封面结构**
**WeasyPrint 转 PDF 时，封面必须使用 `@page` 和 `mm`/`pt` 单位，禁止使用 `vh` 作为封面高度依据**
**为避免封面后出现空白页，封面和正文之间只允许存在一次强制分页：保留 `.cover-page { page-break-after: always; break-after: page; }` 时，必须删除或禁止 `.report-content { page-break-before: always; break-before: page; }`**
**若脚本运行结果出现 `session xxx` 与 `pid yyy`，后续状态检查必须使用 `session xxx`；错误使用 pid 视为没有正确等待脚本完成**
**在本地脚本状态变为 `completed` 前，禁止开始 AMD 检索、禁止开始写 HTML、禁止生成 PDF、禁止宣告任务完成**
**Sub-agent 的执行日志与过程说明必须为中文；不得使用英文进行进度播报或工具说明**
**最终导出的PDF文件名必须固定为 `Market_Product_Research_for_xxx.pdf`，xxx是用户询问的产品型号**
**每章结束后必须显式插入 `<div class="chapter-break"></div>` 并配套 `.chapter-break { page-break-after: always; break-after: page; }`，禁止依赖自动分页**
**所有表格必须使用 `.table-block` 包裹，并为 `.table-block, table, thead, tbody, tr, td, th` 设置 `page-break-inside: avoid; break-inside: avoid;`；如果单表高度可能超页，必须主动拆表，不得让PDF引擎截断表格**
**所有结论块、摘要块、测试环境块、场景建议块等完整文字容器必须设置 `page-break-inside: avoid; break-inside: avoid;`；其标题必须设置 `page-break-after: avoid; break-after: avoid;`，禁止标题与后续正文分离到不同页面**
**页面尺寸必须严格使用A4(mm单位)进行HTML布局：`@page size: A4`、正文容器固定宽度；禁止 `zoom`/`transform: scale` 导致的缩放转PDF**
```

## 脚本依赖

### query_rag.sh
- API端点：/v1/chatqna
- 参数：问题文本、top_n(默认5)、max_tokens(默认1300)

## 输出示例

```
✅ 竞品分析报告已生成

📄 中文PDF报告路径：直接在对话窗口返回
注意不用返回报告概要。
```

## 扩展性

此skill可扩展用于：
- 其他竞争产品对比
