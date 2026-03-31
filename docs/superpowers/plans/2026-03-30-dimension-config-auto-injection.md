# 维度配置与智能问数自动注入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增维度配置页面 + 修改 AI 语义解析，实现查询时自动将时间和维度条件注入 SQL

**Architecture:** 后端新增 `dimension_configs` 表存储"表名→维度→列名→可用值"映射；AI 服务查询时根据 `starrocks_sql` 确定表名，查维度配置后自动拼接 WHERE 条件

**Tech Stack:** Go (Gin + GORM), Vue 3 (Element Plus), Python (LangGraph nodes.py)

---

## 文件结构

```
后端：
  internal/model/dimension_config.go     # 新增 DimensionConfig 模型
  internal/api/handler/dimension.go      # 新增 CRUD handler
  internal/api/router.go                # 注册 /dimension-configs 路由
  internal/repository/postgres/db.go     # autoMigrate 添加新模型

前端：
  web/src/views/DimensionConfig.vue      # 新增维度配置页面
  web/src/views/Layout.vue              # 添加导航入口
  web/src/api/index.js                  # 添加 dimensionConfigAPI

AI 服务：
  ai/client/metric_client.py            # 添加 get_dimension_configs()
  ai/graph/nodes.py                     # 修改 _apply_dimensions_to_sql() 自动注入
```

---

## Task 1: 后端 - 创建 DimensionConfig 模型

**Files:**
- Create: `internal/model/dimension_config.go`

- [ ] **Step 1: 创建模型文件**

```go
package model

import (
    "time"
)

// DimensionConfig StarRocks 表的维度配置
type DimensionConfig struct {
    ID             uint      `json:"id" gorm:"primaryKey"`
    TableName      string    `json:"table_name" gorm:"size:128;index:idx_table_dimension,unique"`
    DimensionName string    `json:"dimension_name" gorm:"size:64;index:idx_table_dimension,unique"`
    ColumnName     string    `json:"column_name" gorm:"size:64"`
    DimensionValues string   `json:"dimension_values" gorm:"type:text"` // JSON array: ["北京","上海"]
    Status         int16     `json:"status" gorm:"default:1"`          // 1=启用 0=停用
    CreatedAt      time.Time `json:"created_at"`
    UpdatedAt      time.Time `json:"updated_at"`
}

func (DimensionConfig) TableName() string {
    return "dimension_configs"
}
```

- [ ] **Step 2: 提交**

```bash
git add internal/model/dimension_config.go
git commit -m "feat(model): add DimensionConfig model for table-dimension mapping"
```

---

## Task 2: 后端 - 创建 DimensionConfig Handler

**Files:**
- Create: `internal/api/handler/dimension.go`

- [ ] **Step 1: 创建 handler 文件**

```go
package handler

import (
    "dev_metric/internal/model"
    "dev_metric/internal/repository/postgres"
    "dev_metric/pkg/response"
    "strconv"

    "github.com/gin-gonic/gin"
)

// ListDimensionConfigs 获取维度配置列表
func ListDimensionConfigs(c *gin.Context) {
    tableName := c.Query("table_name")

    var configs []model.DimensionConfig
    db := postgres.Get().Model(&model.DimensionConfig{})

    if tableName != "" {
        db = db.Where("table_name = ?", tableName)
    }

    db.Order("id ASC").Find(&configs)
    response.Success(c, configs)
}

// GetDimensionTables 获取所有已配置表名
func GetDimensionTables(c *gin.Context) {
    var results []string
    postgres.Get().Model(&model.DimensionConfig{}).
        Where("status = ?", 1).
        Distinct("table_name").
        Pluck("table_name", &results)
    response.Success(c, results)
}

// CreateDimensionConfig 创建维度配置
func CreateDimensionConfig(c *gin.Context) {
    var config model.DimensionConfig
    if err := c.ShouldBindJSON(&config); err != nil {
        response.Error(c, response.CodeBadRequest, "参数错误")
        return
    }

    if err := postgres.Get().Create(&config).Error; err != nil {
        response.Error(c, response.CodeInternalError, "创建失败")
        return
    }
    response.Success(c, config)
}

// UpdateDimensionConfig 更新维度配置
func UpdateDimensionConfig(c *gin.Context) {
    id, _ := strconv.Atoi(c.Param("id"))
    var config model.DimensionConfig
    if err := postgres.Get().First(&config, id).Error; err != nil {
        response.Error(c, response.CodeNotFound, "配置不存在")
        return
    }

    var updates map[string]interface{}
    if err := c.ShouldBindJSON(&updates); err != nil {
        response.Error(c, response.CodeBadRequest, "参数错误")
        return
    }

    if err := postgres.Get().Model(&config).Updates(updates).Error; err != nil {
        response.Error(c, response.CodeInternalError, "更新失败")
        return
    }
    response.Success(c, config)
}

// DeleteDimensionConfig 删除维度配置
func DeleteDimensionConfig(c *gin.Context) {
    id, _ := strconv.Atoi(c.Param("id"))
    if err := postgres.Get().Delete(&model.DimensionConfig{}, id).Error; err != nil {
        response.Error(c, response.CodeInternalError, "删除失败")
        return
    }
    response.SuccessWithMessage(c, "删除成功", nil)
}
```

- [ ] **Step 2: 提交**

```bash
git add internal/api/handler/dimension.go
git commit -m "feat(handler): add DimensionConfig CRUD handlers"
```

---

## Task 3: 后端 - 注册路由 + 添加 AutoMigrate

**Files:**
- Modify: `internal/api/router.go`
- Modify: `internal/repository/postgres/db.go`

- [ ] **Step 1: 在 router.go 添加路由**

在 `v1` group 内添加：

```go
// 维度配置
dimension := v1.Group("/dimension-configs")
{
    dimension.GET("", handler.ListDimensionConfigs)
    dimension.GET("/tables", handler.GetDimensionTables)
    dimension.POST("", handler.CreateDimensionConfig)
    dimension.PUT("/:id", handler.UpdateDimensionConfig)
    dimension.DELETE("/:id", handler.DeleteDimensionConfig)
}
```

- [ ] **Step 2: 在 db.go AutoMigrate 添加新模型**

```go
return db.AutoMigrate(
    // ... existing models ...
    &model.DimensionConfig{},  // 新增
)
```

- [ ] **Step 3: 提交**

```bash
git add internal/api/router.go internal/repository/postgres/db.go
git commit -m "feat(router): register dimension-configs routes and add AutoMigrate"
```

---

## Task 4: 前端 - 添加 API 方法

**Files:**
- Modify: `web/src/api/index.js`

- [ ] **Step 1: 添加 dimensionConfigAPI**

在 `starrocksAPI` 后面添加：

```javascript
// 维度配置 API
export const dimensionConfigAPI = {
  list: (params) => api.get('/dimension-configs', { params }),
  getTables: () => api.get('/dimension-configs/tables'),
  create: (data) => api.post('/dimension-configs', data),
  update: (id, data) => api.put(`/dimension-configs/${id}`, data),
  delete: (id) => api.delete(`/dimension-configs/${id}`)
}
```

- [ ] **Step 2: 提交**

```bash
git add web/src/api/index.js
git commit -m "feat(api): add dimensionConfigAPI methods"
```

---

## Task 5: 前端 - 创建 DimensionConfig.vue 页面

**Files:**
- Create: `web/src/views/DimensionConfig.vue`

- [ ] **Step 1: 创建页面组件**

```vue
<template>
  <div class="dimension-config">
    <el-row :gutter="20">
      <!-- 左侧：表名选择 -->
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>
            <span>数据表</span>
          </template>
          <el-select v-model="selectedTable" placeholder="选择表名" style="width:100%" filterable @change="loadConfigs">
            <el-option v-for="t in tables" :key="t" :label="t" :value="t" />
          </el-select>
          <el-divider />
          <el-button type="primary" plain style="width:100%" @click="openCreateDialog">新增维度</el-button>
        </el-card>
      </el-col>

      <!-- 右侧：维度配置列表 -->
      <el-col :span="18">
        <el-card shadow="hover">
          <template #header>
            <span>维度配置 {{ selectedTable ? `- ${selectedTable}` : '' }}</span>
          </template>
          <el-table :data="configs" stripe>
            <el-table-column prop="dimension_name" label="维度名称" width="150" />
            <el-table-column prop="column_name" label="列名" width="150" />
            <el-table-column prop="dimension_values" label="可用值" min-width="300">
              <template #default="{ row }">
                <el-tag v-for="v in parseValues(row.dimension_values)" :key="v" size="small" style="margin:2px">
                  {{ v }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
                  {{ row.status === 1 ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="openEditDialog(row)">编辑</el-button>
                <el-button type="danger" link size="small" @click="handleDelete(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑维度' : '新增维度'" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="维度名称">
          <el-input v-model="form.dimension_name" placeholder="如 region, platform" />
        </el-form-item>
        <el-form-item label="列名">
          <el-input v-model="form.column_name" placeholder="如 region_id, platform_code" />
        </el-form-item>
        <el-form-item label="可用值">
          <el-input v-model="form.dimension_values" type="textarea" :rows="3"
            placeholder="JSON数组格式，如 [&quot;北京&quot;,&quot;上海&quot;,&quot;华南&quot;]" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { dimensionConfigAPI } from '@/api'

const tables = ref([])
const selectedTable = ref('')
const configs = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const form = ref({ dimension_name: '', column_name: '', dimension_values: '[]', status: 1 })

function parseValues(jsonStr) {
  try { return JSON.parse(jsonStr) } catch { return [] }
}

async function loadTables() {
  const res = await dimensionConfigAPI.getTables()
  tables.value = res.data || []
}

async function loadConfigs() {
  if (!selectedTable.value) return
  const res = await dimensionConfigAPI.list({ table_name: selectedTable.value })
  configs.value = res.data || []
}

function openCreateDialog() {
  if (!selectedTable.value) {
    ElMessage.warning('请先选择表名')
    return
  }
  isEdit.value = false
  form.value = { table_name: selectedTable.value, dimension_name: '', column_name: '', dimension_values: '[]', status: 1 }
  dialogVisible.value = true
}

function openEditDialog(row) {
  isEdit.value = true
  form.value = { ...row }
  dialogVisible.value = true
}

async function handleSave() {
  try {
    if (isEdit.value) {
      await dimensionConfigAPI.update(form.value.id, form.value)
    } else {
      await dimensionConfigAPI.create(form.value)
    }
    dialogVisible.value = false
    ElMessage.success('保存成功')
    loadConfigs()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function handleDelete(id) {
  await ElMessageBox.confirm('确认删除？', '提示')
  await dimensionConfigAPI.delete(id)
  ElMessage.success('删除成功')
  loadConfigs()
}

onMounted(() => {
  loadTables()
})
</script>

<style scoped>
.dimension-config { padding: 20px; }
</style>
```

- [ ] **Step 2: 提交**

```bash
git add web/src/views/DimensionConfig.vue
git commit -m "feat(frontend): add DimensionConfig page"
```

---

## Task 6: 前端 - 添加导航入口

**Files:**
- Modify: `web/src/views/Layout.vue`

- [ ] **Step 1: 添加导航菜单项**

找到导航菜单配置的位置，添加：

```vue
<el-menu-item index="/dimension-config">
  <el-icon><Setting /></el-icon>
  <span>维度配置</span>
</el-menu-item>
```

（具体位置需要根据 Layout.vue 的实际结构调整）

- [ ] **Step 2: 提交**

```bash
git add web/src/views/Layout.vue
git commit -m "feat(frontend): add navigation entry for DimensionConfig"
```

---

## Task 7: AI 服务 - 添加 get_dimension_configs API

**Files:**
- Modify: `ai/client/metric_client.py`

- [ ] **Step 1: 添加方法**

```python
def get_dimension_configs(self, table_name: str = None) -> List[Dict[str, Any]]:
    """获取维度配置"""
    params = {}
    if table_name:
        params["table_name"] = table_name
    response = httpx.get(
        f"{self.base_url}/api/v1/dimension-configs",
        params=params,
        timeout=10
    )
    response.raise_for_status()
    return response.json().get("data", [])
```

- [ ] **Step 2: 提交**

```bash
git add ai/client/metric_client.py
git commit -m "feat(ai): add get_dimension_configs to MetricClient"
```

---

## Task 8: AI 服务 - 修改 _apply_dimensions_to_sql 自动注入

**Files:**
- Modify: `ai/graph/nodes.py`

- [ ] **Step 1: 修改 _apply_dimensions_to_sql 函数**

找到现有的 `_apply_dimensions_to_sql` 函数（约在 928 行），在函数开头添加"自动注入时间条件到 WHERE"的逻辑：

```python
def _apply_dimensions_to_sql(self, sql: str, dimensions: Dict[str, Any], entities: Dict[str, Any], time_info: Dict = None) -> str:
    """
    将维度参数应用到 SQL 模板中
    支持:
      - {dimension} 动态 GROUP BY (如 department)
      - {start_date}, {end_date} 时间范围替换
      - {platform} 等维度占位符替换
      - 无 dimension 时默认聚合 (去掉 GROUP BY)
      - 时间条件自动追加到 WHERE（不依赖占位符）
      - 维度条件按配置映射追加到 WHERE（不依赖占位符）
    """
    if not sql:
        return sql

    adjusted_sql = sql
    table_name = self._extract_table_name(sql)

    # === 新增：自动注入时间条件到 WHERE ===
    if time_info:
        start_date = time_info.get("start")
        end_date = time_info.get("end")
        # 替换占位符
        if start_date:
            adjusted_sql = adjusted_sql.replace("{start_date}", f"'{start_date}'")
        if end_date:
            adjusted_sql = adjusted_sql.replace("{end_date}", f"'{end_date}'")
        # 如果没有占位符，自动追加到 WHERE
        if table_name and ("{start_date}" not in adjusted_sql and "{end_date}" not in adjusted_sql):
            # 时间列统一三个字段都加条件（冗余但安全）
            time_conditions = [
                f"fdate = '{start_date}'" if start_date else None,
                f"report_month = '{start_date[:7]}'" if start_date else None,
                f"the_year = '{start_date[:4]}'" if start_date else None,
            ]
            for cond in [c for c in time_conditions if c]:
                if "WHERE" in adjusted_sql.upper():
                    adjusted_sql += f" AND {cond}"
                else:
                    adjusted_sql += f" WHERE {cond}"
    # === 新增 END ===

    # === 新增：自动注入维度条件到 WHERE ===
    if table_name and dimensions:
        dim_configs = self._get_table_dimensions_cached(table_name)
        for dim_key, dim_value in dimensions.items():
            if not dim_value or dim_key == "dimension":
                continue
            if dim_key in dim_configs:
                column_name = dim_configs[dim_key].get("column_name", dim_key)
                # 替换占位符
                for pattern in [f"{{{dim_key}}}", f"{{{{{dim_key}}}}}", f"{{{dim_key}_name}}"]:
                    if pattern in adjusted_sql:
                        if dim_value.startswith("'") and dim_value.endswith("'"):
                            adjusted_sql = adjusted_sql.replace(pattern, dim_value)
                        else:
                            adjusted_sql = adjusted_sql.replace(pattern, f"'{dim_value}'")
                # 如果没有占位符，追加到 WHERE
                if f"{{{dim_key}}}" not in adjusted_sql and f"{{{{{dim_key}}}}}" not in adjusted_sql:
                    if "WHERE" in adjusted_sql.upper():
                        adjusted_sql += f" AND {column_name} = '{dim_value}'"
                    else:
                        adjusted_sql += f" WHERE {column_name} = '{dim_value}'"
    # === 新增 END ===

    # 原有逻辑继续保留（维度替换、GROUP BY 处理等）
    # ... (原有的 964-1010 行代码保持不变)
```

- [ ] **Step 2: 添加辅助函数**

在 `_apply_dimensions_to_sql` 函数之前添加：

```python
# 维度配置缓存（避免每次查询都调 API）
_table_dimensions_cache: Dict[str, Dict[str, Dict]] = {}

def _get_table_dimensions_cached(self, table_name: str) -> Dict[str, Dict]:
    """获取表的维度配置，带缓存"""
    if table_name in _table_dimensions_cache:
        return _table_dimensions_cache[table_name]
    try:
        configs = self.metric_client.get_dimension_configs(table_name)
        result = {}
        for cfg in configs:
            if cfg.get("status") == 1:
                result[cfg["dimension_name"]] = {
                    "column_name": cfg["column_name"],
                    "values": json.loads(cfg["dimension_values"]) if cfg.get("dimension_values") else []
                }
        _table_dimensions_cache[table_name] = result
    except Exception as e:
        print(f"[DEBUG] 获取维度配置失败: {e}")
        _table_dimensions_cache[table_name] = {}
    return _table_dimensions_cache[table_name]

def _extract_table_name(self, sql: str) -> str:
    """从 SQL 中提取表名（FROM 后第一个表名）"""
    import re
    match = re.search(r'FROM\s+([^\s,;]+)', sql, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""
```

同时在文件顶部添加 `import json`（如果还没有的话）。

- [ ] **Step 3: 提交**

```bash
git add ai/graph/nodes.py
git commit -m "feat(ai): auto-inject time and dimension conditions in _apply_dimensions_to_sql"
```

---

## Task 9: 验证测试

**Files:**
- 测试文件无需修改，手动验证即可

- [ ] **Step 1: 启动后端，测试 API**

```bash
# 测试列表
curl http://localhost:8080/api/v1/dimension-configs

# 测试按表名筛选
curl http://localhost:8080/api/v1/dimension-configs?table_name=dws.DWS_IMC_BUSINESSREPORT

# 测试创建
curl -X POST http://localhost:8080/api/v1/dimension-configs \
  -H "Content-Type: application/json" \
  -d '{"table_name":"dws.DWS_IMC_BUSINESSREPORT","dimension_name":"region","column_name":"region_id","dimension_values":"[\"北京\",\"上海\",\"华南\"]","status":1}'
```

- [ ] **Step 2: 重启 Python AI 服务，测试智能问数**

```bash
# 问：昨天页面访问量是多少
curl -X POST http://localhost:8081/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"昨天页面访问量是多少"}'

# 验证 SQL 中是否包含 fdate = '2026-xx-xx' 条件
```

- [ ] **Step 3: 提交所有变更**

如果所有验证通过：

```bash
git status
git log --oneline -3
```

---

## 实施检查清单

- [ ] Task 1: DimensionConfig 模型创建
- [ ] Task 2: DimensionConfig Handler 创建
- [ ] Task 3: 路由注册 + AutoMigrate
- [ ] Task 4: 前端 API 方法添加
- [ ] Task 5: DimensionConfig.vue 页面创建
- [ ] Task 6: Layout.vue 导航入口
- [ ] Task 7: metric_client.get_dimension_configs()
- [ ] Task 8: _apply_dimensions_to_sql 自动注入逻辑
- [ ] Task 9: 手动验证测试
