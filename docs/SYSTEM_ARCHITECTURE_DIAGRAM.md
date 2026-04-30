# System Architecture Diagrams

Updated: 2026-04-30

This file is the diagram-only companion to `docs/PROJECT_ARCHITECTURE.md`.

## 1. Deployment View

```mermaid
flowchart LR
    Browser[Browser]

    subgraph Frontend[Frontend Dev Server]
        Vite[Vite / Vue 3]
    end

    subgraph Backend[Go Backend :18080]
        Gin[Gin Router]
        Meta[Metadata APIs]
        Query[Query Execute API]
        Crud[CRUD / Auth / Session APIs]
    end

    subgraph AI[Python AI :18081]
        FastAPI[FastAPI]
        V2[LLM.V2 Router + Graph]
        Prompt[PromptManager]
        Session[V2SessionStore]
    end

    subgraph Data[Data Stores]
        PG[(PostgreSQL)]
        Redis[(Redis)]
        SR[(StarRocks)]
    end

    subgraph External[External Models]
        DS[DeepSeek via Tencent]
        EMB[Alibaba Embedding]
    end

    Browser --> Vite
    Vite -->|/api/*| Gin
    Vite -->|/api/v1/llm-ask/v2*| FastAPI

    Gin --> PG
    Gin --> Redis
    Gin --> SR

    FastAPI --> V2
    V2 --> Prompt
    V2 --> Session
    V2 --> Gin
    V2 --> Redis
    V2 --> PG
    V2 --> DS
    V2 --> EMB
```

## 2. LLM.V2 Pipeline

```mermaid
flowchart TB
    Q([User Question]) --> R1[intent_router]
    R1 --> R2[context_enhancer]
    R2 --> R3[mql_generator]
    R3 --> R4[mql_syntax_validator]
    R4 -->|retry| R3
    R4 --> R5[mql_semantic_validator]
    R5 -->|retry| R3
    R5 --> R6[sql_generator]
    R6 --> R7[sql_security_auditor]
    R7 -->|blocked| ERR([Error / Reject])
    R7 --> R8[sql_executor]
    R8 --> R9[data_quality_checker]
    R9 --> R10[trigger_analyzer]
    R10 --> R11[result_analyzer]
    R11 --> R12[state_manager]
    R12 --> A([Answer])
```

## 3. Session and Cache Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant AI as Python AI
    participant Store as V2SessionStore
    participant Redis as Redis
    participant GO as Go Backend
    participant PG as PostgreSQL

    FE->>AI: ask / ask stream
    AI->>Store: get_context(session_id)
    Store->>Redis: read v2:session:{id}
    Redis-->>Store: payload or miss
    Store-->>AI: inherited MQL / history / summary

    AI->>GO: load prompts / metrics / vectors / execute SQL
    GO->>PG: metadata / prompt data

    AI->>Store: set_state(V2State)
    Store->>Redis: write session payload
    Store-->>AI: persisted

    AI->>GO: save ask log / save session history
    GO->>PG: write ask_session_summaries / ask_messages
```

## 4. Frontend Routing and Proxy

```mermaid
flowchart LR
    AskPage[/llm-ask-v2]
    OtherPages[/dashboard /metrics /alerts /analysis /config-center]

    AskPage -->|axios / SSE| ProxyLLM[/api/v1/llm-ask/v2*]
    OtherPages -->|axios| ProxyAPI[/api/*]

    ProxyLLM --> PY[Python AI :18081]
    ProxyAPI --> GO[Go Backend :18080]
```
