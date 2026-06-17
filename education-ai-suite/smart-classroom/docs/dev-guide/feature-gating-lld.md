# Low-Level Design (LLD): Configuration-Driven Capability Gating and Shared Services

## 1. Purpose

This design introduces capability-driven runtime composition for Smart Classroom so that only enabled features and required shared services are loaded.

It replaces static startup behavior with:
- feature registry driven by config.yaml
- service manager and service registry
- API route registration based on enabled capabilities
- pipeline component creation based on enabled capabilities
- UI feature visibility based on backend capability status

## 2. Current Baseline (Observed)

The current code initializes most capabilities eagerly:
- app startup always calls route registration and model preload
- pipeline construction eagerly creates ASR, summarizer, mindmap, and content segmentation components
- API endpoints are all mounted unconditionally
- UI tabs/features are state-driven by workflow stage, not by deployment capability

Main integration points:
- main app startup: main.py
- route registration: api/endpoints.py
- pipeline construction: pipeline.py
- static config load: utils/config_loader.py
- runtime project config: utils/runtime_config_loader.py
- UI composition and tabs: ui/src/App.tsx and ui/src/components/LeftPanel/LeftPanel.tsx

## 3. Target Architecture

### 3.1 Style

Capability-Based Modular Monolith with Shared Services:
- each feature has API + pipeline + UI mapping
- shared heavyweight services are single-owner runtime resources
- runtime activation is config-driven

### 3.2 Runtime Graph

config.yaml
  -> CapabilityResolver
  -> ServiceDependencyResolver
  -> ServiceManager
  -> ServiceRegistry
  -> RouteRegistry
  -> PipelineFactory
  -> Capabilities API (/capabilities)
  -> UI gating

## 4. Capability Model

Add a new top-level config section:

features:
  summary: true
  mindmap: true
  topic_segmentation: true
  content_search: true
  qa: false
  grading: false
  asr: true
  summary_with_ocr: false
  va_front: true
  va_back: false
  va_board: false

Rules:
- missing key uses default from code (safe defaults in FeatureRegistry)
- false means capability is absent from runtime
- absent capability must not initialize dependent components or services

## 5. Shared Service Inventory and Dependency Mapping

Shared services (service keys):
- vlm_service: port 9900
- chromadb_service: port 9090
- ocr_service: in-process model owner
- asr_service: in-process model owner
- va_service: MediaMTX + VA stack
- content_search_stack: ports 9011, 9990, 8001

Feature -> service dependencies:
- summary -> vlm_service
- mindmap -> vlm_service
- topic_segmentation -> vlm_service + chromadb_service
- content_search -> content_search_stack + chromadb_service
- qa -> vlm_service + chromadb_service
- grading -> vlm_service + chromadb_service + ocr_service
- summary_with_ocr -> ocr_service + vlm_service
- asr -> asr_service
- va_front/va_back/va_board -> va_service

## 6. New Modules

### 6.1 Feature Registry

File: core/feature_registry.py

Responsibilities:
- define canonical feature keys
- define defaults
- validate config values
- expose enabled_features set

Public API:
- FeatureRegistry.from_config(config) -> FeatureRegistry
- is_enabled(feature: str) -> bool
- enabled() -> set[str]

### 6.2 Service Dependency Resolver

File: core/service_dependency_resolver.py

Responsibilities:
- map enabled features to required shared services
- return deterministic service startup order

Public API:
- resolve(features: set[str]) -> list[str]

Startup order:
1) chromadb_service (if required)
2) content_search_stack (if required)
3) vlm_service (if required)
4) ocr_service (if required)
5) asr_service (if required)
6) va_service (if required)

### 6.3 Service Registry

File: infra/service_registry.py

Responsibilities:
- single source of truth for service lifecycle state
- service handle storage (pid/process/client)
- readiness metadata

Data model:
- ServiceStatus: stopped|starting|ready|failed
- ServiceRecord:
  - key
  - status
  - endpoint
  - started_at
  - health
  - handle

Public API:
- register(service_key, record)
- get(service_key)
- is_ready(service_key)
- stop_all()
- list_status()

### 6.4 Service Manager

File: infra/service_manager.py

Responsibilities:
- start only required shared services
- perform health probes and retries
- publish readiness in ServiceRegistry

Public API:
- start_required(required_services: list[str])
- stop_required(required_services: list[str])
- ensure_ready(service_key)

Integration notes:
- content_search_stack startup wraps existing content_search/start_services.py behavior
- vlm_service startup can shell out to existing provider server (if external) or skip when in-process model owner is used

### 6.5 API Route Registry

File: api/route_registry.py

Responsibilities:
- create capability-aware FastAPI router registration
- register base routes always
- register feature routes only when enabled

Public API:
- register_routes(app, capabilities, services)

Route groups:
- base: /health, /create-session, /project, /metrics
- asr: /upload-audio, /transcribe
- summary: /summarize
- mindmap: /mindmap
- topic_segmentation: /content-segmentation
- content_search: /search-content
- va: /start-video-analytics-pipeline, /stop-video-analytics-pipeline, /class-statistics
- ocr: /ocr/detect-file, /ocr/extract-text

Behavior:
- disabled routes not mounted -> default 404 from FastAPI

### 6.6 Pipeline Factory

File: pipeline_factory.py

Responsibilities:
- instantiate only components required for requested operation
- share model instances via service/model provider

Public API:
- build_for_operation(operation: str, session_id: str) -> PipelineContext

PipelineContext:
- session_id
- components dict
- service clients

Example:
- summarize operation creates only SummarizerComponent
- mindmap operation creates MindmapComponent + shared summarizer model client
- content segmentation uses shared VLM client and content search client only when capability is enabled

### 6.7 Unified VLM Client

File: components/llm/vlm_client.py

Responsibilities:
- single inference client for summary/mindmap/topic_segmentation/qa/grading
- POST /v1/chat/completions abstraction
- stream and non-stream support

Public API:
- chat(messages, stream=False, **kwargs)
- stream_chat(messages, **kwargs)

Integration:
- SummarizerComponent and MindmapComponent switch to VLMClient adapter instead of direct provider binding when vlm_service mode is active

### 6.8 Capability Status API

File: api/capabilities.py

Endpoint:
- GET /capabilities

Response schema:
- enabled_features: list[str]
- active_services: list[{key,status,endpoint}]
- route_groups: list[str]
- generated_at

Purpose:
- source of truth for UI gating

### 6.9 UI Capability Gate

Files:
- ui/src/services/api.ts
- ui/src/redux/slices/uiSlice.ts
- ui/src/components/LeftPanel/LeftPanel.tsx
- ui/src/components/common/Body.tsx (if needed)

Responsibilities:
- fetch /capabilities on startup
- store enabled features in redux
- hide tabs/panels/actions for disabled features
- never call disabled endpoints

UI rules:
- summary tab rendered only if summary enabled
- mindmap tab rendered only if mindmap enabled
- search box rendered only if content_search enabled
- video analytics controls rendered only if any va_* enabled
- OCR preview/actions rendered only if summary_with_ocr or ocr-related capability enabled

## 7. Startup Flow (LLD Sequence)

1) main.py loads config.yaml
2) FeatureRegistry resolves enabled features
3) ServiceDependencyResolver computes required services
4) ServiceManager starts required services and health-checks
5) API route registry mounts only enabled route groups
6) app exposes /capabilities
7) UI bootstraps with /capabilities and renders gated sections
8) PipelineFactory creates components lazily per operation request

## 8. File-Level Change Plan

### Phase 1: Foundation
- Add core/feature_registry.py
- Add core/service_dependency_resolver.py
- Add infra/service_registry.py
- Add infra/service_manager.py
- Add api/capabilities.py
- Extend config.yaml with features section

### Phase 2: Backend Wiring
- Refactor main.py to orchestrate capability and services before route registration
- Replace register_routes in api/endpoints.py with api/route_registry.py grouped registration
- Add per-route capability checks for safety (defense-in-depth)

### Phase 3: Pipeline Refactor
- Add pipeline_factory.py
- Refactor pipeline.py to lazy-build operation-specific components
- Ensure summarizer and mindmap share same VLM/model handle

### Phase 4: Unified VLM
- Add components/llm/vlm_client.py
- Adapt summarizer/mindmap/content segmentation paths to VLMClient abstraction
- Preserve existing provider classes as adapters for compatibility

### Phase 5: UI Gating
- Add capabilities fetch in ui/src/services/api.ts
- Persist features in redux ui slice
- Conditionally render tabs/sections and disable API calls for absent capabilities

### Phase 6: Validation and Rollout
- Add integration tests for route absence/presence and service startup matrix
- Add capability matrix tests for key deployment profiles
- Add docs and migration notes

## 9. API and Class Contracts

### 9.1 Capability Evaluation Contract

Input:
- config.models
- config.features

Output:
- enabled_features set
- validation errors list

Validation behavior:
- unknown feature keys -> warning
- non-boolean values -> startup error

### 9.2 Service Startup Contract

Input:
- required_services list

Output:
- ServiceRegistry with ready services

Failure behavior:
- required service failed to start -> startup fails fast
- optional service failed (none in this design) -> warning and continue

### 9.3 Route Registration Contract

Input:
- capabilities

Output:
- mounted routers list

Behavior:
- disabled route group not mounted

### 9.4 Pipeline Build Contract

Input:
- operation
- session_id

Output:
- operation-specific component graph

Behavior:
- operation requiring disabled capability -> HTTP 404 from missing route or HTTP 403 from guard if route is internal-only

## 10. Health and Observability

Add health categories:
- /health: liveness only
- /capabilities: runtime composition
- /health/services (optional): readiness by service

Metrics to emit:
- startup_time_total
- startup_time_by_service{service}
- enabled_feature_count
- loaded_model_count
- route_group_count

## 11. Backward Compatibility

Compatibility policy:
- if features section missing, default to current behavior for mandatory baseline flows
- no breaking change in request/response payloads for existing enabled routes
- existing runtime_config.yaml project settings remain unchanged

## 12. Security and Failure Handling

- do not expose disabled capabilities via route docs if route is not mounted
- validate startup config before any heavy model/service initialization
- add timeout/retry/circuit-breaker for service probes
- on shutdown, ServiceManager stop_all in reverse startup order

## 13. Test Plan

Backend tests:
- feature->route matrix (mounted/not mounted)
- feature->service matrix (started/not started)
- startup failure when required service health probe fails
- lazy pipeline creation (no component construction for disabled feature)

UI tests:
- tabs hidden for disabled features
- no API invocation for disabled features
- capability refresh behavior on page load

E2E profiles:
- full profile: all features true
- light profile: summary + mindmap only
- search-only profile: content_search only
- analytics-only profile: va_* only

## 14. Implementation Notes for Existing Files

main.py:
- move preload_models behind capability checks
- replace direct register_routes(app) call with capability-aware registration

api/endpoints.py:
- split into route groups by capability
- keep shared DTOs and helper functions reusable

pipeline.py:
- remove eager constructor binding for all components
- instantiate per operation using factory and cached shared model handles

components/summarizer_component.py and components/mindmap_component.py:
- support dependency injection of shared vlm client/model handle
- keep existing behavior as fallback adapter mode

ui/src/components/LeftPanel/LeftPanel.tsx:
- switch from disabled tab to conditional tab rendering for absent features

## 15. Acceptance Criteria

1. Disabled feature endpoints return 404 because they are not mounted.
2. Startup does not initialize models/services unrelated to enabled features.
3. Summary, mindmap, and segmentation share one VLM endpoint/client path.
4. UI hides disabled feature sections and does not call corresponding APIs.
5. /capabilities accurately reflects enabled features and active services.
6. Existing enabled flows preserve current request/response schema.

## 16. Estimated Delivery (Suggested)

- Sprint 1: foundation + route gating + capabilities API
- Sprint 2: service manager and startup optimization
- Sprint 3: pipeline lazy build + unified vlm client adapter
- Sprint 4: UI gating + tests + rollout profiles

## 17. Conclusion

Yes, this can be implemented in the current project structure with incremental refactoring. The design keeps your current modules but introduces capability and service orchestration layers so disabled features are absent from runtime, not merely hidden.
