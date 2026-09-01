# Document chatbot — RAG over PDFs → chatqna

**User (business objective):**
> I want employees to ask questions in plain English and get answers from our
> internal policy PDFs.

**Orchestrator (Step 1 — business Q&A):**
1. Outcome — a chat interface that answers from your documents with citations?
   [yes]
2. Inputs — a folder of PDFs/docs to ground answers on? [yes, provide path]
3. Deployment — single-host Docker, or Kubernetes cluster? [Docker]
4. Hardware — Intel GPU (default), or Intel CPU/NPU? [Intel GPU]
5. Interface — web chat UI, an API, or both? [web UI]

**Discovery (Step 2):** verb *ask/answer* + object *documents* + Docker →
**`chatqna-docker-deploy`** (not in this repo; install from
`open-edge-platform/edge-ai-libraries`). If Kubernetes → `chatqna-helm-deploy`.

**Plan (Step 4 — awaits confirmation):**
- Deliverable: ChatQnA Core running via Docker Compose; web chat UI grounded on
  the provided document set.
- Skill: `chatqna-docker-deploy` (must install).
- Inferred technology: OpenVINO GPU profile, default embedding + LLM for GPU.
- Install command (run only after approval):
  `npx skills@1.5.23 add open-edge-platform/skills --skill chatqna-docker-deploy`
- Requirements: Docker + Compose v2; enough RAM for the chosen LLM.

**Build (Step 5, after approval):** install then delegate to
`chatqna-docker-deploy` (env setup → profile → up → health check), point it at
the user's documents, verify health, and return the chat URL.
