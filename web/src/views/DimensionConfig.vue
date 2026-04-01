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

    <div class="page-content">
      <!-- 左侧表名列表 -->
      <div class="table-panel">
        <div class="panel-header">
          <span>数据表</span>
          <span class="table-count">{{ tables.length }}</span>
        </div>

        <!-- 表名列表 -->
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

        <!-- 新增表输入框 -->
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

      <!-- 右侧维度配置列表 -->
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
const newTableName = ref('')
const form = ref({ table_name: '', dimension_name: '', column_name: '', dimension_values: '[]', status: 1 })

function parseValues(jsonStr) {
  try { return JSON.parse(jsonStr) } catch { return [] }
}

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
  // 新增一个空的维度配置来创建表条目
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

onMounted(() => {
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
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 20px;
  padding: 20px;
  max-width: 1400px;
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

/* 表名列表 */
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

/* 新增表输入框 */
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
