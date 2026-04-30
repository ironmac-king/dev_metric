# LLM.V2 缓存/上下文/继承体系整理设计

## Implementation Status

截至 2026-04-30，以下内容已落地：

- `v2_session_mql` 已从 router 移除，`router` / `state_manager` 共用 `V2SessionStore`
- `V2SessionStore` 当前实现为 **Redis 持久化 + 进程内 memory fallback**
- `V2State.context_cache` 已类型化为 `ContextScope`
- `session_state` / `multi_metric_mode` / `drilldown_category` / `conversation_summary` 已迁入 `V2State` 一等字段
- `original_question` / `suggested_mql` / `quality_warnings` / `anomalies` 的写入点已删除
- `metric_info_cache` 已不再写入，也不再作为 `ContextScope` 一等字段保留

仍保留在 `ContextScope` 的是外部链路仍在读取的字段：

- `clarification_message`
- `clarification_options`
- `similar_cases`
- `suggestions`
- `drilldown_type`
- `comparison_results`

## Context

大哥反馈：LLM.V2 里缓存、上下文、继承体系混乱，难以维护。

具体问题：
- `context_cache` 是 `Dict[str, Any]`，15个字段随意读写，无类型约束，4个死字段从未被读取
- `v2_session_mql`（router.py）和 `state_manager._session_store` 是两个互不同步的内存 dict，无 TTL，进程重启丢失
- `comparison_results` 被 router 读取并写入 DB，但从未有任何节点写入（幽灵字段）
- `VolatilityTrigger` 每次 `check()` 都查库，无缓存（DB 热点）

**整理目标**：消除混乱 + 打标废弃，不动现有逻辑
**重构深度**：全面重构
**comparison_results**：暂时不动，后续处理

---

## 1. 会话存储统一 — V2SessionStore

### 问题

两个互不同步的会话存储：

| 存储 | 位置 | 内容 | 问题 |
|------|------|------|------|
| `v2_session_mql` | router.py:38 | `Dict[str, MQLSchema]` | 无 TTL，无持久化 |
| `state_manager._session_store` | state_manager.py:160 | `Dict[str, V2State]` | 与上者互不通信 |

### 方案

新建 `ai/engine/llm_v2/session_store.py`，引入 `V2SessionStore`。

当前实现不是最初草案中的纯内存 LRU，而是：

- 优先使用 Redis
- Redis 异常时自动回退到进程内 memory store
- router / state_manager 共享同一个单例

核心形态如下：

```python
class V2SessionStore:
    DEFAULT_TTL = 7 * 24 * 3600

    def __init__(self, redis_url=None, ttl_seconds=DEFAULT_TTL, redis_client=None):
        ...

    def set(self, session_id, mql=None, history_stack=None, conversation_summary=None, user_id="default"): ...
    def get_mql(self, session_id) -> Optional[MQLSchema]: ...
    def get_state(self, session_id) -> Optional[V2State]: ...
    def set_state(self, state: V2State) -> None: ...
    def delete(self, session_id): ...
    def clear_all(self) -> None: ...
```

**关键设计**：
- **单例模式**：router 和 state_manager 共享同一个 `V2SessionStore` 实例
- **Redis 持久化**：多轮上下文不再依赖单进程内存
- **memory fallback**：本地开发/测试不会因 Redis 不可用直接阻塞
- **读写分离**：`get_context()` / `get_mql()` / `get_state()` 面向不同调用面
- **状态持久化收口**：`set_state()` 只持久化 durable 字段，不再从 `context_cache` 兜底读取内部状态

### 迁移

```python
# router.py 旧
v2_session_mql: Dict[str, MQLSchema] = {}
v2_session_mql[session_id] = mql

# router.py 新
from .session_store import get_session_store
_session_store = get_session_store()
_session_store.set(session_id, mql=mql)
```

---

## 2. context_cache 类型化 — ContextScope

### 问题

`V2State.context_cache: Dict[str, Any]` 是 free-form dict，字段命名散漫、死字段多、无约束。

### 字段分类结果

| 分类 | 字段 | 处置 |
|------|------|------|
| 跨节点通信 | `clarification_message`, `clarification_options`, `similar_cases`, `suggestions`, `drilldown_type` | 保留，移入 `ContextScope` |
| 内部状态泄漏 | `session_state`, `multi_metric_mode`, `drilldown_category`, `conversation_summary` | 移入 `V2State` 作为一等字段 |
| 死字段 | `original_question`, `suggested_mql`, `quality_warnings`, `anomalies` | 删除写入点 + 删除字段 |
| 兼容残留 | `metric_info_cache` | 不再写入，不再保留为 `ContextScope` 一等字段；旧值仅通过 `extras` 兼容 |
| 幽灵字段 | `comparison_results` | 暂时不动，标记 @deprecated |

### ContextScope dataclass

```python
@dataclass
class ContextScope:
    """
    V2 上下文作用域

    替代自由形式的 context_cache Dict[str, Any]。
    字段按生命周期分类：
    - 跨节点通信：多个节点读写的共享状态
    - 临时缓存：单次请求内有效的缓存
    """
    # === 跨节点通信 ===
    clarification_message: Optional[str] = None
    clarification_options: List[Dict[str, Any]] = field(default_factory=list)
    similar_cases: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    drilldown_type: Optional[str] = None

    # === 幽灵字段（暂时不动）===
    @deprecated("幽灵字段：写入点缺失，暂不动")
    comparison_results: Optional[Any] = None
```

### V2State 一等字段（内部状态迁移）

以下字段从 `context_cache` 迁移到 `V2State`：

```python
@dataclass
class V2State:
    # ... 现有字段 ...
    # === 从 context_cache 迁入的内部状态 ===
    session_state: Optional[Dict[str, Any]] = None
    multi_metric_mode: bool = False
    drilldown_category: Optional[str] = None
    conversation_summary: Optional[Dict[str, Any]] = None
```

---

## 3. 死字段删除清单

| 字段 | 删除位置 |
|------|---------|
| `original_question` | graph.py intent_router 行125 |
| `suggested_mql` | graph.py context_enhancer 行206 |
| `quality_warnings` | graph.py data_quality_checker 行636 |
| `anomalies` | graph.py result_analyzer 行1102 |
| `metric_info_cache` | graph.py _preload_metric_info 行67（写入点已删除，一等字段已移除） |

> `metric_info_cache` 最终按“无人读取”处理：删除写入点，并从 `ContextScope` 一等字段降级为普通兼容 `extras`。

---

## 4. 废弃标记

除字段删除外，对以下位置添加 `[DEPRECATED]` 标记：

| 文件 | 内容 |
|------|------|
| `ai/graph/state.py` | 已有 [DEPRECATED]，确认注释准确 |
| `ai/engine/llm.py` | 已有 [DEPRECATED] |
| `ai/engine/rule_engine.py` | 已有 [DEPRECATED] |
| `ai/engine/llm_v2/cache.py` — `HistoryReuseCache` | 标注 TODO embedding 部分 |
| `ContextScope.comparison_results` | 标注 @deprecated |

---

## 5. 不动现有逻辑

本次整理**不涉及**：
- `MQLSQLCache`（L1+L2 缓存）— 运作良好，不改
- `VolatilityTrigger DB 热点`— 大哥选择不动（属于 bug 修复范畴）
- `comparison_results` 幽灵字段接线上— 暂不动
- graph.py 节点调用链

---

## 6. 实施阶段

### Phase 1：V2SessionStore（最小风险）
1. 新建 `session_store.py`
2. router.py 替换 `v2_session_mql` → `_session_store.set/get_mql`
3. state_manager.py 替换 `_session_store` → 同一 `_session_store` 实例
4. 验证：多轮对话正常

### Phase 2：ContextScope + V2State 一等字段
1. schema.py 新增 `ContextScope` dataclass
2. `V2State.context_cache` 类型从 `Dict[str, Any]` 改为 `ContextScope`
3. 内部状态迁入 `V2State` 一等字段，`context_cache` 只保留外部链路仍在读取的字段
4. 删除死字段写入点
5. 保留 dict-style 兼容接口，避免一次性打断旧调用
6. 验证：服务正常启动

### Phase 3：废弃标记
1. 各 DEPRECATED 位置确认
2. HistoryReuseCache TODO 标注

---

## 7. 验证

1. **多轮对话**：问"销售额" → 追问"同比" → 确认 MQL 上下文继承正常
2. **TTL 验证**：30 分钟无访问后会话过期
3. **启动测试**：Python 服务正常启动，无类型错误
4. **死字段检查**：grep 搜索 `original_question`/`quality_warnings` 等确认无新写入
5. **当前已执行**：`python -m unittest test_llm_v2_refactor_unittest.py -v`
6. **当前已执行**：`python -m py_compile ai/engine/llm_v2/schema.py ai/engine/llm_v2/session_store.py ai/engine/llm_v2/nodes/state_manager.py ai/engine/llm_v2/graph.py ai/engine/llm_v2/router.py`

---

## 涉及文件

| 文件 | 操作 |
|------|------|
| `ai/engine/llm_v2/session_store.py` | 新建 |
| `ai/engine/llm_v2/schema.py` | 修改：ContextScope + V2State 一等字段 |
| `ai/engine/llm_v2/router.py` | 修改：V2SessionStore 替换 v2_session_mql |
| `ai/engine/llm_v2/graph.py` | 修改：context_cache 类型化，删除死字段写入 |
| `ai/engine/llm_v2/nodes/state_manager.py` | 修改：V2SessionStore 替换 _session_store |
| `ai/engine/llm_v2/cache.py` | 修改：HistoryReuseCache TODO 标注 |
