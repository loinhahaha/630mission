# 630mission（公文智能校核项目）

本项目用于对政府/机关类公文进行自动化检查，覆盖 **文档上传、规则检测、问题标注、结果导出**。  
仓库包含后端 API、Streamlit 页面、React 页面三套入口。

---

## 1. 项目结构总览

```text
630mission/
├─ govdoc_checker/
│  ├─ backend/               # FastAPI + 规则引擎 + DOCX 标注
│  ├─ ui/                    # Streamlit 页面（中文）
│  ├─ frontend/              # React + Vite 页面
│  ├─ requirements_all.txt
│  ├─ 功能评估报告.md
│  ├─ 党政机关公文格式.doc
├─ connectivity_pr_probe.txt
└─ README.md
```

---

## 2. 代码文件功能

### 后端（`govdoc_checker/backend`）

- `main.py`：FastAPI 入口，提供健康检查、审核接口与独立润色接口。  
- `pipeline.py`：审核主流程编排（抽取文本、执行规则、生成标注文档）。  
- `models.py`：问题数据模型 `Issue`。  
- `docx_utils.py`：Word 文件处理与标注工具。  
- `text_slicer.py`：文本分片工具（供可选智能体处理）。  
- `agent_client.py`：智能体调用适配。  
- `rules/format_rules.py`：格式规则检查。  
- `rules/punct_rules.py`：标点规则检查。  
- `tests/conftest.py`、`tests/test_smoke.py`：后端测试。  
- `requirements.txt`：后端依赖。

### 前端（`govdoc_checker/frontend`）

- `src/main.jsx`：React 挂载入口。  
- `src/App.jsx`：页面交互（审核主页 + 独立润色页面切换）。  
- `src/app.css`：页面样式（含润色双栏编辑区）。  
- `index.html`：前端模板页面。  
- `vite.config.js`：Vite 配置。  
- `package.json`：前端依赖与脚本。

### Streamlit（`govdoc_checker/ui`）

- `app_streamlit.py`：可视化页面入口。

---

## 3. 核心能力

- 支持上传 `.docx/.doc`（`.doc` 依赖 LibreOffice）
- 自动进行格式与标点规则审核
- 输出标注后的 `docx`（高亮 + 批注）
- 提供“公文润色工坊”独立页面（仅文本输入，左输入右输出）
- 润色过程支持动态状态提示（分段处理中/模型处理中/完成）

---

## 4. Windows CMD 运行命令

> 以下命令在 **cmd.exe** 中执行。

### 4.1 启动后端 API

```cmd
cd govdoc_checker\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

健康检查：`http://127.0.0.1:8000/health`

接口自检（Windows CMD 示例）：

```cmd
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/analyze -F "mode=text" -F "text=测试文本" -o result.docx
curl -X POST http://127.0.0.1:8000/polish -F "text=请对这段公文进行润色"
```

> 说明：访问 `http://127.0.0.1:8000/` 返回 `{"detail":"Not Found"}` 是正常现象。后端只定义了 `/health`、`/analyze`、`/polish`，没有定义根路由 `/`。

> 智能体配置建议放在本地配置文件（避免密钥写入仓库）：复制 `govdoc_checker/backend/agent_config.example.json` 为 `govdoc_checker/backend/agent_config.local.json`，填入 `AUTH_KEY`、`AUTH_SECRET`、`AGENT_ID`（可选 `BASE_URL`）。该本地文件已被 `.gitignore` 忽略。

> 也可直接使用环境变量覆盖：`AUTH_KEY`、`AUTH_SECRET`、`AGENT_ID`、`AGENT_BASE_URL`。环境变量优先级高于本地配置文件。

> 说明：在浏览器直接访问 `http://127.0.0.1:8000/analyze`（默认是 GET）出现 `{"detail":"Method Not Allowed"}` 也正常。`/analyze` 只接受 **POST multipart/form-data** 请求（需带 `mode`，并按需带 `text` 或 `file`）。

> 说明：上传文件返回 `Internal Server Error` 时，后端现在会返回更明确的 JSON 错误信息（例如 `.doc` 缺少 LibreOffice、或文件格式不受支持），React 页面会直接展示该错误原因。

> 可选：如需启用 AI 润色能力（独立润色页面或 `/polish` 接口），请在启动后端前设置环境变量 `AUTH_KEY`、`AUTH_SECRET`（可选 `AGENT_ID`、`AGENT_BASE_URL`）。未配置时润色请求会返回错误提示，但不影响格式/标点检查。

### 4.2 启动 Streamlit 页面

```cmd
cd govdoc_checker
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements_all.txt
streamlit run ui\app_streamlit.py
```

默认地址：`http://localhost:8501`

> 说明：Streamlit 页面是**直连本地 Python pipeline**，不是通过 `http://127.0.0.1:8000` 调后端 API，所以它可以单独运行。

### 4.3 启动 React 前端

```cmd
cd govdoc_checker\frontend
npm install
npm run dev
```

默认地址：`http://localhost:5173`

> 说明：React 前端通过 Vite 代理把 `/analyze`、`/health`、`/polish` 转发到 `http://localhost:8000`，因此使用 React 页面时必须先启动 4.1 的后端。

> 调试补充（`Failed to fetch`）：该错误通常表示浏览器在网络层就失败了（例如后端没启动、Vite 代理不可用、前端页面不在本机 `localhost` 环境而仍请求相对路径）。当前前端已增加多地址兜底：`/analyze` 与 `/polish` 都会按相对路径、`localhost:8000`、`127.0.0.1:8000` 依次尝试（非 localhost 场景还会补充 `当前主机:8000`），用于降低本地代理异常导致的请求失败概率。

---

## 5. 启动顺序与简化建议

### 5.1 是否必须按 4.1 → 4.2 → 4.3 顺序启动？

- **不是必须三者都启动。**
- 如果你使用 **React 前端（4.3）**，需要先启动 **后端 API（4.1）**。
- 如果你只使用 **Streamlit（4.2）**，可以不启动后端 API。
- 4.2 和 4.3 是两套前端入口，通常二选一即可。

### 5.2 能否简化成一段命令？（Windows CMD）

可以。下面这段命令会一次性打开三个新窗口，分别启动后端、Streamlit、React：

```cmd
start "backend" cmd /k "cd /d %cd%\govdoc_checker\backend && if not exist .venv python -m venv .venv && call .venv\Scripts\activate && pip install -r requirements.txt && uvicorn main:app --reload --port 8000"
start "streamlit" cmd /k "cd /d %cd%\govdoc_checker && if not exist .venv python -m venv .venv && call .venv\Scripts\activate && pip install -r requirements_all.txt && streamlit run ui\app_streamlit.py"
start "react" cmd /k "cd /d %cd%\govdoc_checker\frontend && npm install && npm run dev"
```

说明：
- 原 README 的 4.1/4.2/4.3 命令本身是正确的，但每段最后一个命令都会占用当前终端，需要手动开多个窗口。
- 上述写法把“开多个窗口”的动作也自动化了，体验上等价于“一次执行”。

---

## 6. Docker 部署可行性（只给结论与做法，不改代码）

### 6.1 结论

- **可以部署到 Docker。**
- 现有代码结构支持拆成两个容器：
  - 后端容器：运行 FastAPI（`uvicorn main:app --host 0.0.0.0 --port 8000`）
  - 前端容器：打包 React 静态资源并由 Nginx（或同类静态服务器）提供

### 6.2 推荐做法

1. **后端镜像**
   - 基础镜像使用 Python 3.11+。
   - 安装 `govdoc_checker/backend/requirements.txt` 依赖。
   - 工作目录切到 `govdoc_checker/backend`，启动 `uvicorn` 并监听 `0.0.0.0:8000`。

2. **前端镜像**
   - 构建阶段执行 `npm ci && npm run build`。
   - 运行阶段仅托管 `dist` 静态文件。
   - 前端请求后端时，不依赖 Vite 开发代理；改为通过网关/Nginx 反向代理 `/analyze`、`/health`、`/polish` 到后端容器。

3. **编排（docker compose）**
   - 定义 `backend` 与 `frontend` 两个服务。
   - `frontend` 依赖 `backend`，并通过容器网络访问后端。
   - 将必要环境变量（如 `AUTH_KEY`、`AUTH_SECRET`）通过 compose 注入后端。

4. **与 `.doc` 相关的注意事项**
   - 若需支持上传 `.doc`，容器内仍需安装 LibreOffice（与本地运行要求一致）。

### 6.3 是否必须改代码

- **不必须。**
- 仅通过 Dockerfile + 反向代理/compose 配置即可上线。
- 如果后续希望在任意域名和路径前缀下更稳定运行，可再考虑把前端 API 基地址抽成环境变量，但这属于可选优化而非 Docker 必选改造。

## 7. 最近更新（2026-03）

- 前端新增“公文润色工坊”独立页面：按钮进入、可返回；左侧输入原文，右侧展示润色结果。
- 后端新增 `POST /polish` 文本润色接口，便于前端独立调用。
- 原审核流程保留格式/标点检查与文档下载，不再与润色勾选强耦合。

