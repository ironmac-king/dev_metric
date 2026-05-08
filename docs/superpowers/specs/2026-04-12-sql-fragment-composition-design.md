# SQL 片段组合引擎设计

## 背景

当前 SQL 模板引擎将"意图计算逻辑"和"SQL 结构"耦合在一起，每个意图一个完整 SQL 模板字符串，导致：

1. GROUP BY 等片段不能条件化（有无 dimension 需要不同 SQL）
2. 模板难以复用和组合
3. 新增意图需要写完整 SQL 模板

## 设计目标

将 SQL 拆分为独立可组合的片段，意图只决定使用哪些片段以及如何组合。

## 架构设计

```
意图识别 → 实体提取 → 片段组装 → SQL 生成
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
              基础片段             意图特有片段
         (SELECT, WHERE)      (GROUP BY, 窗口函数)
```

## 核心组件

### 1. 片段基类 (SQLFragment)

```python
class SQLFragment(ABC):
    @abstractmethod
    def render(self, context: Dict[str, Any]) -> str:
        """渲染片段为 SQL 字符串"""

    def required_context(self) -> List[str]:
        """返回渲染所需的最少 context 键"""
        return []
```

### 2. MeasureFragment

从 starrocks_sql 解析 field 和 table。

```python
class MeasureFragment(SQLFragment):
    def render(self, context: Dict[str, Any]) -> str:
        # 返回 "SUM(SPEND) AS SPEND" 这样的字段表达式
        return context.get("field", "*")

    def get_table(self, context: Dict[str, Any]) -> str:
        # 返回 "ids.IDS_AMZ_COMPREHENSIVE_DI" 这样的表名
        return context.get("table", "metric_table")
```

### 3. WhereFragment

时间过滤片段。

```python
class WhereFragment(SQLFragment):
    def render(self, context: Dict[str, Any]) -> str:
        date_col = context.get("date_column", "FDATE")
        start = context.get("start_date", "2026-01-01")
        end = context.get("end_date", "2026-04-12")
        return f"{date_col} BETWEEN '{start}' AND '{end}'"
```

### 4. GroupByFragment

分组片段（可选）。

```python
class GroupByFragment(SQLFragment):
    def render(self, context: Dict[str, Any]) -> str:
        dimension = context.get("dimension")
        if dimension:
            return f"GROUP BY {dimension}"
        # 无 dimension 时默认按日期分组
        date_col = context.get("date_column", "FDATE")
        return f"GROUP BY {date_col}"
```

### 5. WindowFragment

窗口函数片段（意图特有）。

```python
class WindowFragment(SQLFragment):
    def __init__(self, window_type: str):
        self.window_type = window_type  # "LAG", "RANK", "YoY"

    def render(self, context: Dict[str, Any]) -> str:
        field = context.get("field", "*")
        date_col = context.get("date_column", "FDATE")

        if self.window_type == "LAG":
            return f"""
    LAG({field}, 1) OVER (ORDER BY {date_col}) AS prev_value,
    {field} - LAG({field}, 1) OVER (ORDER BY {date_col}) AS diff,
    ROUND(({field} - LAG({field}, 1) OVER (ORDER BY {date_col})) / NULLIF(LAG({field}, 1) OVER (ORDER BY {date_col}), 0) * 100, 2) AS mom_rate"""
        elif self.window_type == "RANK":
            return f"""
    RANK() OVER (ORDER BY {field} DESC) AS rank_num,
    ROUND({field} / SUM({field}) OVER () * 100, 2) AS pct_of_total"""
        elif self.window_type == "YoY":
            return f"""
    t1.{date_col} AS date,
    t1.{field} AS current_value,
    t2.{field} AS last_year_value,
    t1.{field} - t2.{field} AS diff_value,
    ROUND((t1.{field} - t2.{field}) / NULLIF(t2.{field}, 0) * 100, 2) AS yoy_rate"""
        return ""
```

### 6. FragmentComposer

片段组装器。

```python
class FragmentComposer:
    def __init__(self):
        self.fragments: List[SQLFragment] = []

    def add(self, fragment: SQLFragment) -> "FragmentComposer":
        self.fragments.append(fragment)
        return self

    def render(self, context: Dict[str, Any]) -> str:
        parts = []
        for f in self.fragments:
            rendered = f.render(context)
            if rendered:
                parts.append(rendered)
        return "\n".join(parts)
```

## 意图与片段映射

| 意图 | 片段组合 |
|------|---------|
| query_value | MeasureFragment |
| query_trend | MeasureFragment + GroupByFragment + WindowFragment(LAG) |
| query_ranking | MeasureFragment + GroupByFragment + WindowFragment(RANK) |
| query_comparison | MeasureFragment + WindowFragment(YoY) + 自连接 |

## 上下文 context 结构

```python
context = {
    # 从 starrocks_sql 解析
    "field": "SUM(SPEND) AS SPEND",
    "table": "ids.IDS_AMZ_COMPREHENSIVE_DI",

    # 从 entity_node 传入
    "metric_code": "MKI-02-0008",
    "dimension": "FSITE",  # 可选，无则默认 date_column
    "start_date": "2026-04-01",
    "end_date": "2026-04-12",

    # 从 dimension_configs 查找
    "date_column": "FDATE",
}
```

## 关键优势

1. **片段可复用**：Measure、Where、GroupBy 等独立存在
2. **意图可扩展**：新增意图只需定义片段组合
3. **配置驱动**：意图→片段映射在 JSON/DB 配置
4. **可测试**：每个片段可独立单元测试

## 文件结构

```
ai/sql_template_engine/
├── __init__.py
├── fragments/
│   ├── __init__.py
│   ├── base.py          # SQLFragment 基类
│   ├── measure.py       # MeasureFragment
│   ├── where.py         # WhereFragment
│   ├── group_by.py      # GroupByFragment
│   ├── window.py        # WindowFragment (LAG, RANK, YoY)
│   └── composer.py       # FragmentComposer
├── intent_config.py     # 意图→片段映射配置
├── engine.py            # 主引擎（适配新架构）
└── templates.json       # 保留兼容（可选迁移）
```

## 迁移策略

1. 新架构作为独立模块 `fragments/`
2. `engine.py` 先支持两种渲染方式：片段组合 和 模板字符串
3. 逐步将 `templates.json` 迁移到片段组合
4. 最终弃用模板字符串方式

## 验证

- 单元测试：每个片段独立测试
- 集成测试：query_value/trend/ranking/comparison 各场景验证
- 对比测试：新旧两种渲染方式输出对比
