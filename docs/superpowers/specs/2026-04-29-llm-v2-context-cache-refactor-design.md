# LLM.V2 缓存/上下文/继承体系整理设计

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

新建 `ai/engine/llm_v2/session_store.py`，引入 `V2SessionStore`：

```python
class SessionEntry:
    mql: Optional[MQLSchema]
    v2state: Optional[V2State]
    created_at: float
    last_accessed: float

    def is_expired(self, ttl_seconds: float) -> bool:
        return time.time() - self.last_accessed > ttl_seconds

class V2SessionStore:
    DEFAULT_TTL = 1800      # 30 分钟无访问则过期
    MAX_SIZE = 10000       # LRU 淘汰上限

    def __init__(self, ttl_seconds=1800, max_size=10000):
        self._store: OrderedDict[str, SessionEntry] = OrderedDict()
        self._lock = threading.RLock()

    def set(self, session_id, mql=None, v2state=None): ...
    def get(self, session_id) -> Optional[SessionEntry]: ...
    def get_mql(self, session_id) -> Optional[MQLSchema]: ...
    def get_state(self, session_id) -> Optional[V2State]: ...
    def delete(self, session_id): ...
    def clear_expired(self) -> int: ...  # 惰性清理
    def stats(self) -> dict: ...
```

**关键设计**：
- **单例模式**：router 和 state_manager 共享同一个 `V2SessionStore` 实例
- **LRU + TTL 双保险**：按访问时间过期，同时限制最大容量防止内存泄漏
- **读写分离**：`get_mql()` 供 router 快速恢复上下文，`get_state()` 供 state_manager 操作完整状态
- **惰性清理**：过期条目在下次 `get()` 时清理，不阻塞主线程

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
| 死字段 | `metric_info_cache`, `original_question`, `suggested_mql`, `quality_warnings`, `anomalies` | 删除写入点 + 删除字段 |
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

    # === 临时缓存（待验证）===
    # 注意：_preload_metric_info 写入了此字段，但探索时未找到明确读者
    # 实施时先 grep 确认是否被读取，如无读者则删除写入点
    metric_info_cache: Optional[Dict[str, Any]] = None

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
| `metric_info_cache` | graph.py _preload_metric_info 行67 — **需先确认是否真的无人读取** |

> 注意：`metric_info_cache` 由 `_preload_metric_info` 写入，但探索时未找到读者。需实施前确认。

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
3. graph.py 所有 `context_cache["xxx"]` → `context_cache.xxx`
4. 删除死字段写入点
5. 验证：服务正常启动

### Phase 3：废弃标记
1. 各 DEPRECATED 位置确认
2. HistoryReuseCache TODO 标注

---

## 7. 验证

1. **多轮对话**：问"销售额" → 追问"同比" → 确认 MQL 上下文继承正常
2. **TTL 验证**：30 分钟无访问后会话过期
3. **启动测试**：Python 服务正常启动，无类型错误
4. **死字段检查**：grep 搜索 `original_question`/`quality_warnings` 等确认无新写入

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
