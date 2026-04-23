<template>
  <div class="dimension-config-page">
    <!-- 顶部导航 -->
    <div class="top-nav">
      <div class="nav-left">
        <div class="nav-icon">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <rect x="2" y="2" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
            <rect x="10" y="2" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
            <rect x="2" y="10" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
            <rect x="10" y="10" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
          </svg>
        </div>
        <span class="nav-title">维度配置</span>
      </div>
    </div>

    <!-- 顶部 Tab 切换 -->
    <div class="page-tabs">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'values' }"
        @click="activeTab = 'values'"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <rect x="2" y="3" width="12" height="2" rx="1" stroke="currentColor" stroke-width="1.2"/>
          <rect x="2" y="7" width="12" height="2" rx="1" stroke="currentColor" stroke-width="1.2"/>
          <rect x="2" y="11" width="8" height="2" rx="1" stroke="currentColor" stroke-width="1.2"/>
        </svg>
        维度值列表
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'configs' }"
        @click="activeTab = 'configs'"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.2"/>
          <path d="M8 5V8L10 10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
        维度配置
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'types' }"
        @click="switchToTypeMappings"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M2 4H14M2 8H10M2 12H12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        类型映射
      </button>
    </div>

    <div class="page-content">
      <!-- ========== 标签页1：维度值列表（统一表） ========== -->
      <div class="full-width-panel" v-if="activeTab === 'values'">
        <!-- 工具栏 -->
        <div class="value-toolbar">
          <div class="toolbar-filters">
            <el-select
              v-model="filterTableName"
              placeholder="选择表名"
              clearable
              size="small"
              style="width:240px;margin-right:8px"
              @change="handleFilterChange"
            >
              <el-option
                v-for="t in availableTables"
                :key="t"
                :label="t"
                :value="t"
              />
            </el-select>
            <el-select
              v-model="filterColumn"
              placeholder="选择列名"
              clearable
              size="small"
              style="width:180px;margin-right:8px"
              @change="handleFilterChange"
            >
              <el-option
                v-for="c in availableColumns"
                :key="c"
                :label="c"
                :value="c"
              />
            </el-select>
            <el-select
              v-model="filterDimensionType"
              placeholder="选择维度类型"
              clearable
              size="small"
              style="width:160px"
              @change="handleFilterChange"
            >
              <el-option
                v-for="dt in availableDimensionTypes"
                :key="dt"
                :label="dt"
                :value="dt"
              />
            </el-select>
          </div>
          <div class="toolbar-actions">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索维度值"
              size="small"
              clearable
              style="width:200px;margin-right:8px"
              @keyup.enter="handleSearch"
              @clear="handleSearch"
            >
              <template #prefix>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style="margin-top:2px">
                  <circle cx="6" cy="6" r="4.5" stroke="currentColor" stroke-width="1.2"/>
                  <path d="M9.5 9.5L13 13" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                </svg>
              </template>
            </el-input>
            <el-button type="primary" size="small" @click="handleSync" :loading="syncing" :disabled="!filterColumn">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style="margin-right:4px">
                <path d="M12.5 7A5.5 5.5 0 112.2 3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
                <path d="M2.5 3.5V7H6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              {{ syncing ? '同步中...' : '从StarRocks同步' }}
            </el-button>
            <el-button size="small" @click="sqlSyncDialogVisible = true">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style="margin-right:4px">
                <path d="M7 2V12M4 9L7 12L10 9M4 5L7 2L10 5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              批量同步
            </el-button>
          </div>
        </div>

        <!-- 维度值表格 -->
        <el-table
          :data="valueList"
          stripe
          class="value-table"
          v-loading="loading"
        >
          <el-table-column prop="table_name" label="表名" width="220" show-overflow-tooltip />
          <el-table-column prop="column_name" label="列名" width="140" />
          <el-table-column prop="dimension_type" label="维度类型" width="120" />
          <el-table-column prop="dimension_value" label="维度值" min-width="200" show-overflow-tooltip />
          <el-table-column prop="frequency" label="频次" width="80" align="center" />
          <el-table-column prop="status" label="状态" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
                {{ row.status === 1 ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="openEditValueDialog(row)">编辑</el-button>
              <el-button type="danger" link size="small" @click="handleDeleteValue(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-row">
          <span class="pagination-info">共 {{ pagination.total }} 条</span>
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :page-sizes="[20, 50, 100, 200]"
            :total="pagination.total"
            layout="sizes, prev, pager, next"
            background
            small
            @current-change="loadValues"
            @size-change="handleSizeChange"
          />
        </div>
      </div>

      <!-- ========== 标签页2：维度配置（旧，兼容） ========== -->
      <div class="two-col-layout" v-if="activeTab === 'configs'">
        <!-- 左侧表名列表 -->
        <div class="table-panel">
          <div class="panel-header">
            <span>数据表</span>
            <span class="table-count">{{ tables.length }}</span>
          </div>

          <div class="table-list">
            <div
              v-for="t in tables"
              :key="t"
              class="table-item"
              :class="{ active: selectedTable === t }"
              @click="selectTable(t)"
            >
              <svg class="table-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
                <rect x="2" y="3" width="12" height="2" rx="1" stroke="currentColor" stroke-width="1.2"/>
                <rect x="2" y="7" width="12" height="2" rx="1" stroke="currentColor" stroke-width="1.2"/>
                <rect x="2" y="11" width="8" height="2" rx="1" stroke="currentColor" stroke-width="1.2"/>
              </svg>
              <span class="table-name" :title="t">{{ t }}</span>
              <button class="delete-btn" @click.stop="handleDeleteTable(t)" title="删除表">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M2 4H12M5 4V3C5 2.4 5.4 2 6 2H8C8.6 2 9 2.4 9 3V4M11 4V11C11 11.6 10.6 12 10 12H4C3.4 12 3 11.6 3 11V4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                </svg>
              </button>
            </div>

            <div v-if="tables.length === 0" class="table-empty">
              暂无数据表
            </div>
          </div>

          <div class="add-table-row">
            <el-input
              v-model="newTableName"
              placeholder="输入新表名"
              size="small"
              @keyup.enter="handleAddTable"
            >
              <template #append>
                <el-button @click="handleAddTable" :disabled="!newTableName.trim()">添加</el-button>
              </template>
            </el-input>
          </div>
        </div>

        <!-- 右侧配置列表 -->
        <div class="config-panel">
          <div class="config-header">
            <span class="config-title">维度配置 {{ selectedTable ? `- ${selectedTable}` : '' }}</span>
            <el-button type="primary" size="small" @click="openCreateDialog" :disabled="!selectedTable">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style="margin-right:4px">
                <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
              新增维度
            </el-button>
          </div>

          <el-table :data="configs" stripe class="config-table">
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
        </div>
      </div>

      <!-- ========== 标签页3：类型映射（独占一行） ========== -->
      <div class="full-width-panel" v-if="activeTab === 'types'">
        <div class="config-header" style="margin-bottom:16px">
          <span class="config-title">维度类型映射（全局）</span>
          <el-button type="primary" size="small" @click="openTypeMappingDialog()">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style="margin-right:4px">
              <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            新增映射
          </el-button>
        </div>

        <el-table :data="typeMappings" stripe class="config-table">
          <el-table-column prop="dimension_type" label="维度类型" width="180" />
          <el-table-column prop="column_name" label="列名" width="180" />
          <el-table-column prop="description" label="描述" min-width="200" />
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
                {{ row.status === 1 ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="openTypeMappingDialog(row)">编辑</el-button>
              <el-button type="danger" link size="small" @click="handleDeleteTypeMapping(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 新增/编辑维度值弹窗 -->
    <el-dialog v-model="valueDialogVisible" :title="isValueEdit ? '编辑维度值' : '新增维度值'" width="500px">
      <el-form :model="valueForm" label-width="100px">
        <el-form-item label="表名">
          <el-input v-model="valueForm.table_name" placeholder="如 ids.IDS_AMZ_COMPREHENSIVE_DI" />
        </el-form-item>
        <el-form-item label="列名">
          <el-input v-model="valueForm.column_name" placeholder="如 GROUP_2、PLATFORM" />
        </el-form-item>
        <el-form-item label="维度类型">
          <el-input v-model="valueForm.dimension_type" placeholder="如 二级品类、平台" />
        </el-form-item>
        <el-form-item label="维度值">
          <el-input v-model="valueForm.dimension_value" placeholder="如 智能云存储" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="valueForm.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="valueDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveValue">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑维度配置弹窗（兼容旧） -->
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
            placeholder="JSON数组格式，如 [&#34;北京&#34;,&#34;上海&#34;,&#34;华南&#34;]" />
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

    <!-- 新增/编辑类型映射弹窗 -->
    <el-dialog v-model="typeMappingDialogVisible" :title="typeMappingEditId ? '编辑映射' : '新增映射'" width="500px">
      <el-form :model="typeMappingForm" label-width="100px">
        <el-form-item label="维度类型">
          <el-input v-model="typeMappingForm.dimension_type" placeholder="如 日期、日、月" />
        </el-form-item>
        <el-form-item label="列名">
          <el-input v-model="typeMappingForm.column_name" placeholder="如 FDATE、MONTHS、WEEKS" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="typeMappingForm.description" placeholder="如 日期维度、季度维度" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="typeMappingForm.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="typeMappingDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveTypeMapping">保存</el-button>
      </template>
    </el-dialog>

    <!-- 批量同步 SQL 弹窗 -->
    <el-dialog v-model="sqlSyncDialogVisible" title="批量同步维度值（SQL）" width="700px">
      <div style="margin-bottom:12px">
        <el-alert type="info" :closable="false" show-icon>
          <template #title>
            SQL 格式说明：从 StarRocks 查询结果需包含 <code>table_name</code>、<code>column_name</code>、<code>dimension_type</code>、<code>dimension_value</code> 四列
          </template>
        </el-alert>
      </div>
      <el-input
        v-model="batchSyncSQL"
        type="textarea"
        :rows="8"
        placeholder="示例：
SELECT
  'ids.IDS_AMZ_COMPREHENSIVE_DI' AS table_name,
  'FSITECODE' AS column_name,
  '站点编码' AS dimension_type,
  FSITECODE AS dimension_value
FROM ids.IDS_AMZ_COMPREHENSIVE_DI
WHERE LENGTH(FSITECODE) > 0"
        style="font-family:monospace;font-size:13px"
      />
      <template #footer>
        <el-button @click="sqlSyncDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleBatchSync" :loading="batchSyncing">执行同步</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { dimensionConfigAPI, dimensionTypeMappingAPI, dimensionValueAPI } from '@/api'

// ===== 维度值列表（新统一表） =====
const activeTab = ref('values')
const loading = ref(false)
const syncing = ref(false)
const valueList = ref([])
const searchKeyword = ref('')
const filterTableName = ref('')
const filterColumn = ref('')
const filterDimensionType = ref('')
const availableTables = ref([])
const availableColumns = ref([])
const availableDimensionTypes = ref([])

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0
})

const valueDialogVisible = ref(false)
const isValueEdit = ref(false)

// 批量同步
const sqlSyncDialogVisible = ref(false)
const batchSyncSQL = ref('')
const batchSyncing = ref(false)

const valueForm = ref({
  table_name: 'ids.IDS_AMZ_COMPREHENSIVE_DI',
  column_name: '',
  dimension_type: '',
  dimension_value: '',
  status: 1
})

async function loadValues() {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      table_name: filterTableName.value || undefined,
      column_name: filterColumn.value || undefined,
      dimension_type: filterDimensionType.value || undefined,
      dimension_value: searchKeyword.value || undefined
    }
    const res = await dimensionValueAPI.list(params)
    valueList.value = res.data.list || []
    pagination.value.total = res.data.pagination?.total || 0
  } catch (e) {
    console.error('加载维度值失败', e)
  } finally {
    loading.value = false
  }
}

async function loadFilterOptions() {
  try {
    const res = await dimensionValueAPI.getColumns({})
    const cols = res.data || []
    const tables = [...new Set(cols.map(c => c.table_name))].filter(Boolean)
    availableTables.value = tables
  } catch (e) {
    console.error('加载过滤选项失败', e)
  }
}

async function handleFilterChange() {
  // 加载可用的列名选项
  if (filterTableName.value) {
    try {
      const res = await dimensionValueAPI.getColumns({ table_name: filterTableName.value })
      const cols = res.data || []
      availableColumns.value = [...new Set(cols.filter(c => c.column_name).map(c => c.column_name))]
      availableDimensionTypes.value = [...new Set(cols.map(c => c.dimension_type).filter(Boolean))]
    } catch (e) {
      console.error('加载列名选项失败', e)
    }
  } else {
    availableColumns.value = []
    availableDimensionTypes.value = []
  }
  // 如果当前选的列不在新选项里，清掉
  if (filterColumn.value && !availableColumns.value.includes(filterColumn.value)) {
    filterColumn.value = ''
  }
  if (filterDimensionType.value && !availableDimensionTypes.value.includes(filterDimensionType.value)) {
    filterDimensionType.value = ''
  }
  pagination.value.page = 1
  loadValues()
}

async function handleSearch() {
  pagination.value.page = 1
  loadValues()
}

async function handleSync() {
  if (!filterColumn.value) {
    ElMessage.warning('请先选择一个列名')
    return
  }
  syncing.value = true
  try {
    const res = await dimensionValueAPI.sync({
      column_name: filterColumn.value,
      table_name: filterTableName.value || 'ids.IDS_AMZ_COMPREHENSIVE_DI'
    })
    const data = res.data || {}
    ElMessage.success(`同步完成：新增 ${data.synced || 0} 条，跳过 ${data.skipped || 0} 条`)
    loadValues()
    loadFilterOptions()
  } catch (e) {
    ElMessage.error('同步失败')
  } finally {
    syncing.value = false
  }
}

function handleSizeChange() {
  pagination.value.page = 1
  loadValues()
}

function openEditValueDialog(row) {
  isValueEdit.value = true
  valueForm.value = { ...row }
  valueDialogVisible.value = true
}

async function handleSaveValue() {
  try {
    if (isValueEdit.value) {
      await dimensionValueAPI.update(valueForm.value.id, valueForm.value)
    }
    valueDialogVisible.value = false
    ElMessage.success('保存成功')
    loadValues()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function handleDeleteValue(id) {
  try {
    await ElMessageBox.confirm('确认删除？', '提示')
    await dimensionValueAPI.delete(id)
    ElMessage.success('删除成功')
    loadValues()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function handleBatchSync() {
  if (!batchSyncSQL.value.trim()) {
    ElMessage.warning('SQL 不能为空')
    return
  }
  batchSyncing.value = true
  try {
    const res = await dimensionValueAPI.syncBySQL(batchSyncSQL.value)
    const data = res.data || {}
    ElMessage.success(`同步完成：新增 ${data.synced || 0} 条，跳过 ${data.skipped || 0} 条`)
    sqlSyncDialogVisible.value = false
    batchSyncSQL.value = ''
    loadValues()
    loadFilterOptions()
  } catch (e) {
    ElMessage.error('批量同步失败')
  } finally {
    batchSyncing.value = false
  }
}

// ===== 维度配置（旧，兼容） =====
const tables = ref([])
const selectedTable = ref('')
const configs = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const newTableName = ref('')
const form = ref({ table_name: '', dimension_name: '', column_name: '', dimension_values: '[]', status: 1 })

async function loadTables() {
  try {
    const res = await dimensionConfigAPI.getTables()
    tables.value = res.data || []
  } catch (e) {
    console.error('加载表名失败', e)
  }
}

async function loadConfigs() {
  if (!selectedTable.value) {
    configs.value = []
    return
  }
  try {
    const res = await dimensionConfigAPI.list({ table_name: selectedTable.value })
    configs.value = res.data || []
  } catch (e) {
    console.error('加载配置失败', e)
  }
}

function selectTable(t) {
  selectedTable.value = t
  loadConfigs()
}

async function handleAddTable() {
  const name = newTableName.value.trim()
  if (!name) return
  try {
    await dimensionConfigAPI.create({
      table_name: name,
      dimension_name: '',
      column_name: '',
      dimension_values: '[]',
      status: 1
    })
    newTableName.value = ''
    await loadTables()
    selectedTable.value = name
    loadConfigs()
    ElMessage.success('表已添加')
  } catch (e) {
    ElMessage.error('添加失败')
  }
}

async function handleDeleteTable(tableName) {
  try {
    await ElMessageBox.confirm(`确定要删除表「${tableName}」及其所有维度配置吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await dimensionConfigAPI.deleteTable(tableName)
    ElMessage.success('删除成功')
    if (selectedTable.value === tableName) {
      selectedTable.value = ''
    }
    loadTables()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
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
  try {
    await ElMessageBox.confirm('确认删除？', '提示')
    await dimensionConfigAPI.delete(id)
    ElMessage.success('删除成功')
    loadConfigs()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

function parseValues(jsonStr) {
  try { return JSON.parse(jsonStr) } catch { return [] }
}

// ===== 类型映射 =====
const typeMappings = ref([])
const typeMappingDialogVisible = ref(false)
const typeMappingEditId = ref(null)
const typeMappingForm = ref({ dimension_type: '', column_name: '', description: '', status: 1 })

function switchToTypeMappings() {
  activeTab.value = 'types'
  loadTypeMappings()
}

async function loadTypeMappings() {
  try {
    const res = await dimensionTypeMappingAPI.list()
    typeMappings.value = res.data || []
  } catch (e) {
    console.error('加载类型映射失败', e)
  }
}

function openTypeMappingDialog(row) {
  if (row) {
    typeMappingEditId.value = row.id
    typeMappingForm.value = { ...row }
  } else {
    typeMappingEditId.value = null
    typeMappingForm.value = { dimension_type: '', column_name: '', description: '', status: 1 }
  }
  typeMappingDialogVisible.value = true
}

async function handleSaveTypeMapping() {
  try {
    if (typeMappingEditId.value) {
      await dimensionTypeMappingAPI.update(typeMappingEditId.value, typeMappingForm.value)
    } else {
      await dimensionTypeMappingAPI.create(typeMappingForm.value)
    }
    typeMappingDialogVisible.value = false
    ElMessage.success('保存成功')
    loadTypeMappings()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function handleDeleteTypeMapping(id) {
  try {
    await ElMessageBox.confirm('确认删除？', '提示')
    await dimensionTypeMappingAPI.delete(id)
    ElMessage.success('删除成功')
    loadTypeMappings()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => {
  loadValues()
  loadFilterOptions()
  loadTables()
})
</script>

<style scoped>
.dimension-config-page {
  padding: 0;
  min-height: 100vh;
  background: var(--bg-page);
}

/* 顶部导航 */
.top-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
}

/* Tab 切换 */
.page-tabs {
  display: flex;
  gap: 8px;
  padding: 16px 20px 0;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  background: transparent;
  border-radius: 8px 8px 0 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s ease;
  border-bottom: 2px solid transparent;
}

.tab-btn:hover {
  color: var(--primary);
  background: var(--bg-primary);
}

.tab-btn.active {
  color: var(--primary);
  background: var(--bg-card);
  border-bottom: 2px solid var(--primary);
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.nav-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  border-radius: 8px;
  color: var(--primary);
}

.nav-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

/* 页面内容 */
.page-content {
  padding: 20px;
}

/* 全宽面板（类型映射、维度值列表） */
.full-width-panel {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.03);
}

/* 两列布局（维度配置） */
.two-col-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 20px;
}

/* 维度值列表工具栏 */
.value-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}

.toolbar-filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.toolbar-actions {
  display: flex;
  align-items: center;
}

/* 维度值表格 */
.value-table {
  border-radius: 8px;
  overflow: hidden;
}

/* 分页 */
.pagination-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-top: 16px;
  gap: 8px;
}

.pagination-info {
  font-size: 13px;
  color: var(--text-muted);
}

/* 左侧表名面板 */
.table-panel {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.03);
  height: fit-content;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.table-count {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  background: var(--bg-primary);
  padding: 2px 8px;
  border-radius: 10px;
}

.table-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.table-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
}

.table-item:hover {
  background: var(--bg-primary);
}

.table-item.active {
  background: var(--bg-primary);
  border-left: 3px solid var(--primary);
}

.table-icon {
  flex-shrink: 0;
  color: var(--text-muted);
}

.table-name {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.delete-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  color: var(--text-muted);
  opacity: 0;
  transition: all 0.15s ease;
}

.table-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background: #fef2f2;
  color: #dc2626;
}

.table-empty {
  padding: 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}

.add-table-row {
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

/* 右侧配置面板 */
.config-panel {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.03);
}

.config-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.config-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.config-table {
  border-radius: 8px;
  overflow: hidden;
}
</style>
