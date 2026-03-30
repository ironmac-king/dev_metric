<template>
  <div class="dimension-config-page">
    <div class="page-header">
      <h1 class="page-title">维度配置</h1>
      <p class="page-desc">配置 StarRocks 表的维度列名映射和可用值，用于智能问数的自动 SQL 注入</p>
    </div>

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
  if (!selectedTable.value) return
  try {
    const res = await dimensionConfigAPI.list({ table_name: selectedTable.value })
    configs.value = res.data || []
  } catch (e) {
    console.error('加载配置失败', e)
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
.dimension-config-page { padding: 20px; }
.page-header { margin-bottom: 20px; }
.page-title { margin: 0 0 8px 0; font-size: 18px; font-weight: 600; }
.page-desc { margin: 0; color: #909399; font-size: 14px; }
</style>
