# SQL 片段组合引擎实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 SQL 模板引擎重构为片段组合架构，每个意图由独立片段组合而成，提高灵活性和可复用性。

**Architecture:** 片段化 SQL 生成器，意图只决定片段组合方式。核心组件：SQLFragment 基类、各类片段（Measure/Where/GroupBy/Window）、FragmentComposer 组装器。

**Tech Stack:** Python 3.11+, dataclasses, ABC, JSON 配置

---

## 文件结构

```
ai/sql_template_engine/
├── __init__.py                          # 模块入口
├── fragments/                           # 新建：片段模块
│   ├── __init__.py
│   ├── base.py                          # SQLFragment 基类
│   ├── measure.py                       # MeasureFragment
│   ├── where.py                         # WhereFragment
│   ├── group_by.py                      # GroupByFragment
│   └── window.py                       # WindowFragment (LAG/RANK/YoY)
├── composer.py                           # FragmentComposer 组装器
├── intent_config.py                      # 意图→片段映射配置
├── engine.py                            # 主引擎（适配新架构）
└── templates.json                       # 保留兼容（旧模板）
```

---

## Task 1: 创建片段基类

**Files:**
- Create: `ai/sql_template_engine/fragments/base.py`

- [ ] **Step 1: 创建片段基类**

```python
"""SQL 片段基类"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List


class SQLFragment(ABC):
    """SQL 片段基类"""

    @abstractmethod
    def render(self, context: Dict[str, Any]) -> str:
        """渲染片段为 SQL 字符串"""

    def required_context(self) -> List[str]:
        """返回渲染所需的最少 context 键"""
        return []
```

- [ ] **Step 2: 验证片段基类可导入**

Run: `cd C:/Users/4014/Desktop/dev_metric/dev_metric && python -c "from ai.sql_template_engine.fragments.base import SQLFragment; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ai/sql_template_engine/fragments/base.py
git commit -m "feat(sql-fragment): add SQLFragment base class"
```

---

## Task 2: 创建 MeasureFragment

**Files:**
- Create: `ai/sql_template_engine/fragments/measure.py`

- [ ] **Step 1: 创建 MeasureFragment**

```python
"""Measure 片段 - 从 starrocks_sql 解析 field 和 table"""
from typing import Dict, Any, List
from .base import SQLFragment


class MeasureFragment(SQLFragment):
    """Measure 片段，从 starrocks_sql 解析"""

    def render(self, context: Dict[str, Any]) -> str:
        """渲染 SELECT 字段部分"""
        return context.get("field", "*")

    def get_table(self, context: Dict[str, Any]) -> str:
        """获取表名"""
        return context.get("table", "metric_table")

    def required_context(self) -> List[str]:
        return ["field", "table"]
```

- [ ] **Step 2: 验证 MeasureFragment**

Run: `cd C:/Users/4014/Desktop/dev_metric/dev_metric && python -c "from ai.sql_template_engine.fragments.measure import MeasureFragment; f = MeasureFragment(); ctx = {'field': 'SUM(SPEND) AS SPEND', 'table': 'ids.IDS_AMZ'}; print(f.render(ctx))"`
Expected: `SUM(SPEND) AS SPEND`

- [ ] **Step 3: Commit**

```bash
git add ai/sql_template_engine/fragments/measure.py
git commit -m "feat(sql-fragment): add MeasureFragment"
```

---

## Task 3: 创建 WhereFragment

**Files:**
- Create: `ai/sql_template_engine/fragments/where.py`

- [ ] **Step 1: 创建 WhereFragment**

```python
"""Where 片段 - 时间过滤"""
from typing import Dict, Any, List
from .base import SQLFragment


class WhereFragment(SQLFragment):
    """时间过滤片段"""

    def render(self, context: Dict[str, Any]) -> str:
        date_col = context.get("date_column", "FDATE")
        start = context.get("start_date", "2026-01-01")
        end = context.get("end_date", "2026-04-12")
        return f"{date_col} BETWEEN '{start}' AND '{end}'"

    def required_context(self) -> List[str]:
        return ["date_column", "start_date", "end_date"]
```

- [ ] **Step 2: 验证 WhereFragment**

Run: `cd C:/Users/4014/Desktop/dev_metric/dev_metric && python -c "from ai.sql_template_engine.fragments.where import WhereFragment; f = WhereFragment(); ctx = {'date_column': 'FDATE', 'start_date': '2026-04-01', 'end_date': '2026-04-12'}; print(f.render(ctx))"`
Expected: `FDATE BETWEEN '2026-04-01' AND '2026-04-12'`

- [ ] **Step 3: Commit**

```bash
git add ai/sql_template_engine/fragments/where.py
git commit -m "feat(sql-fragment): add WhereFragment"
```

---

## Task 4: 创建 GroupByFragment

**Files:**
- Create: `ai/sql_template_engine/fragments/group_by.py`

- [ ] **Step 1: 创建 GroupByFragment**

```python
"""GroupBy 片段 - 分组"""
from typing import Dict, Any, List, Optional
from .base import SQLFragment


class GroupByFragment(SQLFragment):
    """分组片段 - 有 dimension 用 dimension，无则用 date_column"""

    def render(self, context: Dict[str, Any]) -> str:
        dimension = context.get("dimension")
        if dimension:
            return f"GROUP BY {dimension}"
        # 无 dimension 时默认按日期分组
        date_col = context.get("date_column", "FDATE")
        return f"GROUP BY {date_col}"

    def required_context(self) -> List[str]:
        return ["date_column"]
```

- [ ] **Step 2: 验证 GroupByFragment（两种情况）**

Run: `cd C:/Users/4014/Desktop/dev_metric/dev_metric && python -c "from ai.sql_template_engine.fragments.group_by import GroupByFragment; f = GroupByFragment(); ctx1 = {'dimension': 'FSITE', 'date_column': 'FDATE'}; ctx2 = {'date_column': 'FDATE'}; print('with dim:', f.render(ctx1)); print('without dim:', f.render(ctx2))"`
Expected: `with dim: GROUP BY FSITE` 和 `without dim: GROUP BY FDATE`

- [ ] **Step 3: Commit**

```bash
git add ai/sql_template_engine/fragments/group_by.py
git commit -m "feat(sql-fragment): add GroupByFragment"
```

---

## Task 5: 创建 WindowFragment

**Files:**
- Create: `ai/sql_template_engine/fragments/window.py`

- [ ] **Step 1: 创建 WindowFragment**

```python
"""Window 片段 - 窗口函数"""
from typing import Dict, Any, List
from .base import SQLFragment


class WindowFragment(SQLFragment):
    """窗口函数片段"""

    def __init__(self, window_type: str):
        self.window_type = window_type  # "LAG", "RANK", "YoY"

    def render(self, context: Dict[str, Any]) -> str:
        field = context.get("field", "*")
        date_col = context.get("date_column", "FDATE")

        if self.window_type == "LAG":
            return f"""{field} AS metric_value,
    LAG({field}, 1) OVER (ORDER BY {date_col}) AS prev_value,
    {field} - LAG({field}, 1) OVER (ORDER BY {date_col}) AS diff,
    ROUND(({field} - LAG({field}, 1) OVER (ORDER BY {date_col})) / NULLIF(LAG({field}, 1) OVER (ORDER BY {date_col}), 0) * 100, 2) AS mom_rate"""

        elif self.window_type == "RANK":
            return f"""{field} AS metric_value,
    RANK() OVER (ORDER BY {field} DESC) AS rank_num,
    ROUND({field} / SUM({field}) OVER () * 100, 2) AS pct_of_total"""

        elif self.window_type == "YoY":
            return f"""t1.{date_col} AS date,
    t1.{field} AS current_value,
    t2.{field} AS last_year_value,
    t1.{field} - t2.{field} AS diff_value,
    ROUND((t1.{field} - t2.{field}) / NULLIF(t2.{field}, 0) * 100, 2) AS yoy_rate"""

        return ""

    def required_context(self) -> List[str]:
        return ["field", "date_column"]
```

- [ ] **Step 2: 验证 WindowFragment (RANK)**

Run: `cd C:/Users/4014/Desktop/dev_metric/dev_metric && python -c "from ai.sql_template_engine.fragments.window import WindowFragment; f = WindowFragment('RANK'); ctx = {'field': 'SUM(SPEND) AS SPEND', 'date_column': 'FDATE'}; print(f.render(ctx))"`
Expected: 包含 `RANK()` 和 `SUM()` 窗口函数的 SQL

- [ ] **Step 3: Commit**

```bash
git add ai/sql_template_engine/fragments/window.py
git commit -m "feat(sql-fragment): add WindowFragment with LAG/RANK/YoY"
```

---

## Task 6: 创建 FragmentComposer

**Files:**
- Create: `ai/sql_template_engine/composer.py`

- [ ] **Step 1: 创建 FragmentComposer**

```python
"""片段组装器"""
from typing import List, Dict, Any
from .fragments.base import SQLFragment


class FragmentComposer:
    """片段组装器"""

    def __init__(self):
        self.fragments: List[SQLFragment] = []

    def add(self, fragment: SQLFragment) -> "FragmentComposer":
        """添加片段，支持链式调用"""
        self.fragments.append(fragment)
        return self

    def render(self, context: Dict[str, Any]) -> str:
        """渲染所有片段为完整 SQL"""
        parts = []
        for f in self.fragments:
            rendered = f.render(context)
            if rendered:
                parts.append(rendered)
        return "\n".join(parts)

    def clear(self) -> "FragmentComposer":
        """清空所有片段"""
        self.fragments = []
        return self
```

- [ ] **Step 2: 验证 FragmentComposer**

Run: `cd C:/Users/4014/Desktop/dev_metric/dev_metric && python -c "from ai.sql_template_engine.fragments.measure import MeasureFragment; from ai.sql_template_engine.fragments.where import WhereFragment; from ai.sql_template_engine.composer import FragmentComposer; c = FragmentComposer().add(MeasureFragment()).add(WhereFragment()); ctx = {'field': 'SUM(SPEND)', 'table': 't', 'date_column': 'FDATE', 'start_date': '2026-04-01', 'end_date': '2026-04-12'}; print(c.render(ctx))"`
Expected: `SUM(SPEND)` 和 `FDATE BETWEEN...` 两行

- [ ] **Step 3: Commit**

```bash
git add ai/sql_template_engine/composer.py
git commit -m "feat(sql-fragment): add FragmentComposer"
```

---

## Task 7: 创建意图配置

**Files:**
- Create: `ai/sql_template_engine/intent_config.py`

- [ ] **Step 1: 创建意图配置**

```python
"""意图→片段映射配置"""
from typing import Dict, List, Type
from .fragments.base import SQLFragment
from .fragments.measure import MeasureFragment
from .fragments.where import WhereFragment
from .fragments.group_by import GroupByFragment
from .fragments.window import WindowFragment


# 意图→片段配置
INTENT_FRAGMENTS: Dict[str, List[Type[SQLFragment]]] = {
    "query_value": [MeasureFragment],
    "query_trend": [MeasureFragment, WhereFragment, GroupByFragment],
    "query_ranking": [MeasureFragment, WhereFragment, GroupByFragment],
    "query_comparison": [MeasureFragment, WhereFragment],
}


def get_composer_for_intent(intent: str) -> "FragmentComposer":
    """根据意图获取配置好的 Composer"""
    from .composer import FragmentComposer

    composer = FragmentComposer()
    fragment_types = INTENT_FRAGMENTS.get(intent, [MeasureFragment])

    for ft in fragment_types:
        # 特殊处理需要参数的片段
        if ft == WindowFragment:
            if intent == "query_trend":
                composer.add(WindowFragment("LAG"))
            elif intent == "query_ranking":
                composer.add(WindowFragment("RANK"))
            elif intent == "query_comparison":
                composer.add(WindowFragment("YoY"))
        else:
            composer.add(ft())

    return composer
```

- [ ] **Step 2: 验证意图配置**

Run: `cd C:/Users/4014/Desktop/dev_metric/dev_metric && python -c "from ai.sql_template_engine.intent_config import get_composer_for_intent; c = get_composer_for_intent('query_ranking'); print(len(c.fragments))"`
Expected: `3` (MeasureFragment + WhereFragment + GroupByFragment + WindowFragment)

- [ ] **Step 3: Commit**

```bash
git add ai/sql_template_engine/intent_config.py
git commit -m "feat(sql-fragment): add intent fragment mapping config"
```

---

## Task 8: 集成到 engine.py

**Files:**
- Modify: `ai/sql_template_engine/engine.py`

- [ ] **Step 1: 修改 engine.py 使用片段组合**

```python
"""SQL 模板引擎主入口 - 片段组合模式"""
from typing import Any, Dict, Optional
from .composer import FragmentComposer
from .intent_config import get_composer_for_intent


class SQLTemplateEngine:
    """SQL 模板引擎（片段组合模式）"""

    def __init__(self):
        pass

    def generate_sql(self, intent: str, entities: Dict[str, Any], drill_dims: list = None) -> Optional[str]:
        """生成 SQL"""
        # 构建 context
        context = self._build_context(entities, drill_dims)

        # 获取意图对应的 Composer
        composer = get_composer_for_intent(intent)
        if composer is None:
            return None

        # 渲染 SQL
        return composer.render(context)

    def _build_context(self, entities: Dict[str, Any], drill_dims: list = None) -> Dict[str, Any]:
        """构建渲染上下文"""
        starrocks_sql = entities.get("starrocks_sql", "")

        # 从 starrocks_sql 解析 field 和 table
        field = self._parse_field(starrocks_sql)
        table = self._parse_table(starrocks_sql)

        # 获取时间信息
        time_info = entities.get("time_info", {})
        start_date = time_info.get("start_date", "2026-01-01")
        end_date = time_info.get("end_date", "2026-04-12")

        # 获取日期列
        date_column = entities.get("date_column", "FDATE")

        # 获取维度
        dimension = entities.get("dimension")
        if drill_dims and len(drill_dims) > 0:
            dimension = drill_dims[0]

        context = {
            "field": field,
            "table": table,
            "start_date": start_date,
            "end_date": end_date,
            "date_column": date_column,
            "dimension": dimension,
            "top_n": entities.get("top_n", "10"),
        }

        return context

    def _parse_field(self, starrocks_sql: str) -> str:
        """从 starrocks_sql 解析字段"""
        import re
        if not starrocks_sql:
            return "*"
        match = re.search(r'SELECT\s+(.+?)\s+FROM\s+', starrocks_sql, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return "*"

    def _parse_table(self, starrocks_sql: str) -> str:
        """从 starrocks_sql 解析表名"""
        import re
        if not starrocks_sql:
            return "metric_table"
        match = re.search(r'FROM\s+([^\s;]+)', starrocks_sql, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "metric_table"


# 全局单例
_engine: Optional[SQLTemplateEngine] = None


def get_engine() -> SQLTemplateEngine:
    global _engine
    if _engine is None:
        _engine = SQLTemplateEngine()
    return _engine


def generate_sql(intent: str, entities: Dict[str, Any], drill_dims: list = None) -> Optional[str]:
    """便捷函数"""
    return get_engine().generate_sql(intent, entities, drill_dims)
```

- [ ] **Step 2: 验证片段组合引擎**

Run: `cd C:/Users/4014/Desktop/dev_metric/dev_metric && python -c "
from ai.sql_template_engine.engine import generate_sql
ctx = {
    'starrocks_sql': 'SELECT SUM(SPEND) AS SPEND FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE 1=1',
    'time_info': {'start_date': '2026-04-01', 'end_date': '2026-04-12'},
    'date_column': 'FDATE',
    'dimension': 'FSITE',
    'top_n': '10'
}
sql = generate_sql('query_ranking', ctx)
print(sql)
"`
Expected: 包含 `SUM(SPEND)`, `GROUP BY FSITE`, `RANK()`, `FDATE BETWEEN` 的完整 SQL

- [ ] **Step 3: Commit**

```bash
git add ai/sql_template_engine/engine.py
git commit -m "refactor(sql-fragment): integrate fragment composition into engine"
```

---

## Task 9: 创建 fragments/__init__.py

**Files:**
- Create: `ai/sql_template_engine/fragments/__init__.py`

- [ ] **Step 1: 创建 __init__.py**

```python
"""SQL 片段模块"""
from .base import SQLFragment
from .measure import MeasureFragment
from .where import WhereFragment
from .group_by import GroupByFragment
from .window import WindowFragment

__all__ = [
    "SQLFragment",
    "MeasureFragment",
    "WhereFragment",
    "GroupByFragment",
    "WindowFragment",
]
```

- [ ] **Step 2: 验证导入**

Run: `cd C:/Users/4014/Desktop/dev_metric/dev_metric && python -c "from ai.sql_template_engine.fragments import MeasureFragment, WhereFragment, GroupByFragment, WindowFragment; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ai/sql_template_engine/fragments/__init__.py
git commit -m "feat(sql-fragment): add fragments module __init__"
```

---

## Task 10: 端到端测试

**Files:**
- Modify: `ai/graph/nodes.py:_sql_build_by_template` (可选，保持向后兼容)

- [ ] **Step 1: 测试所有意图类型**

Run: `cd C:/Users/4014/Desktop/dev_metric/dev_metric && python -c "
from ai.sql_template_engine.engine import generate_sql

ctx = {
    'starrocks_sql': 'SELECT SUM(SPEND) AS SPEND FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE 1=1',
    'time_info': {'start_date': '2026-04-01', 'end_date': '2026-04-12'},
    'date_column': 'FDATE',
    'dimension': 'FSITE',
    'top_n': '10'
}

for intent in ['query_value', 'query_trend', 'query_ranking', 'query_comparison']:
    print(f'=== {intent} ===')
    print(generate_sql(intent, ctx))
    print()
"`

- [ ] **Step 2: 测试无 dimension 情况**

Run: `cd C:/Users/4014/Desktop/dev_metric/dev_metric && python -c "
from ai.sql_template_engine.engine import generate_sql

ctx = {
    'starrocks_sql': 'SELECT SUM(SPEND) AS SPEND FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE 1=1',
    'time_info': {'start_date': '2026-04-01', 'end_date': '2026-04-12'},
    'date_column': 'FDATE',
    # 无 dimension
}

sql = generate_sql('query_ranking', ctx)
print('No dimension:')
print(sql)
print()
assert 'GROUP BY FDATE' in sql, 'Should default to date_column in GROUP BY'
print('OK: defaults to date_column GROUP BY')
"`

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(sql-fragment): add e2e tests for fragment composition"
```

---

## 验证清单

- [ ] MeasureFragment 正确解析 starrocks_sql 的 field 和 table
- [ ] WhereFragment 生成正确的时间过滤
- [ ] GroupByFragment 有 dimension 用 dimension，无用 date_column
- [ ] WindowFragment(LAG) 生成环比 SQL
- [ ] WindowFragment(RANK) 生成排名 SQL
- [ ] WindowFragment(YoY) 生成同比 SQL
- [ ] FragmentComposer 正确组合所有片段
- [ ] query_value/trend/ranking/comparison 四种意图都能生成 SQL
- [ ] 无 dimension 时默认使用 date_column 作为 GROUP BY
