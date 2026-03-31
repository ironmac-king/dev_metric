# 维度配置与智能问数自动注入设计

## Context

智能问数（AI 问数）功能中，用户问"昨天页面访问量是多少"时，生成的 SQL 缺少时间条件和维度过滤，原因是 `starrocks_sql` 模板里没有占位符，系统无法注入条件。

需要设计一套完整的方案：
1. **维度配置页面**：让用户配置每个 StarRocks 表的维度列名映射和可用值
2. **自动注入**：查询时根据用户 query 里的时间/维度信息，自动拼接到 SQL WHERE 条件
3. **语义增强**：维度配置同时用于语义解析时的精确匹配和值域校验

## 设计

### 1. 数据模型

**新增表 `dimension_configs`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| table_name | VARCHAR(128) | 表名（如 dws.DWS_IMC_BUSINESSREPORT） |
| dimension_name | VARCHAR(64) | 维度名（如 region, platform, channel） |
| column_name | VARCHAR(64) | 对应 StarRocks 列名（如 region_id） |
| dimension_values | TEXT | 可选值列表，JSON 格式：`["北京","上海","华南"]` |
| status | SMALLINT | 1=启用 0=停用 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

**唯一索引**：`UNIQUE(table_name, dimension_name)`

---

### 2. API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/dimension-configs | 列表（支持 table_name 筛选） |
| POST | /api/v1/dimension-configs | 创建 |
| PUT | /api/v1/dimension-configs/:id | 更新 |
| DELETE | /api/v1/dimension-configs/:id | 删除 |
| GET | /api/v1/dimension-configs/tables | 获取所有已配置表名 |

---

### 3. 前端页面

**新增页面：`web/src/views/DimensionConfig.vue`**

布局：
- 左侧：表名下拉选择（从已配置的表名列表中选）
- 右侧：该表的维度配置列表（维度名、列名、可用值、状态）
- 支持新增/编辑/删除维度配置
- 支持批量导入可用值（逗号分隔或 JSON）

---

### 4. AI 语义解析改动

**修改文件：`ai/graph/nodes.py`**

**4.1 新增维度配置查询**

```python
def get_table_dimensions(table_name: str) -> Dict[str, Dict]:
    """根据表名获取维度配置 {dimension_name: {column_name, values}}"""
    # 调用 Go 后端 GET /api/v1/dimension-configs?table_name=xxx
```

**4.2 修改 `_apply_dimensions_to_sql`**

原逻辑：只做 `{start_date}` 占位符替换，找不到就直接跳过

新逻辑：
1. 从 `starrocks_sql` 解析表名（最后一段 `FROM` 和 `JOIN` 后的表名）
2. 查该表维度配置，得到 `dimension_name → column_name` 映射
3. 时间条件自动追加到 WHERE：
   - 用户问"昨天" → 追加 `AND fdate = '2026-03-29'`
   - 用户问"本月" → 追加 `AND report_month = '2026-03'`
   - 用户问"今年" → 追加 `AND the_year = '2026'`
4. 维度条件按配置映射追加：
   - 用户说"北京"且配置了 `region → region_id` → 追加 `AND region_id = '北京'`
5. 如果 SQL 里已有对应占位符 → 替换；没有 → 追加到 WHERE

**4.3 语义解析值域校验**

```python
# entity_node 中，提取到维度值后
if dimension_value not in config_values:
    # 值不在可用值列表中，触发追问
    state.needs_clarification = True
    state.clarification_message = f"'{dimension_value}' 不在可用值列表中，可选值：{config_values}"
```

---

### 5. 时间字段规范（已确认）

所有 StarRocks 表统一使用：
- **日数据**：`fdate`（格式 `2026-03-29`）
- **月数据**：`report_month`（格式 `2026-03`）
- **年数据**：`the_year`（格式 `2026`）

---

### 6. 文件清单

**后端：**
| 文件 | 改动 |
|------|------|
| `internal/model/dimension.go` | 新增 DimensionConfig 模型 |
| `internal/api/handler/dimension.go` | 新增 handler |
| `internal/api/router.go` | 注册路由 |
| `internal/repository/postgres/db.go` | 可选，确认 GORM AutoMigrate 支持新表 |

**前端：**
| 文件 | 改动 |
|------|------|
| `web/src/views/DimensionConfig.vue` | 新增维度配置页面 |
| `web/src/views/Layout.vue` | 添加导航入口 |
| `web/src/api/index.js` | 添加 API 方法 |

**AI 服务：**
| 文件 | 改动 |
|------|------|
| `ai/graph/nodes.py` | `_apply_dimensions_to_sql` 增加自动注入逻辑 |
| `ai/client/metric_client.py` | 添加 `get_dimension_configs` 方法 |

---

## 验证

1. 启动后端，访问 `GET /api/v1/dimension-configs?table_name=dws.DWS_IMC_BUSINESSREPORT`
2. 在 DimensionConfig 页面配置 `region → region_id`，可用值 `["北京","上海","华南"]`
3. 问"昨天北京访客数"，确认生成的 SQL 包含 `AND fdate = '2026-03-29' AND region_id = '北京'`
4. 问"昨天深圳访客数"（深圳不在可用值里），确认系统追问而不是瞎匹配
5. 配置 `platform → platform_code` 后，问"昨天安卓平台访客数"，确认正确注入
