<template>
  <div class="metrics-page">
    <div class="page-header">
      <h2>指标管理</h2>
      <div class="header-actions">
        <el-upload
          :action="'/api/v1/metrics/import'"
          :headers="{ Authorization: `Bearer ${token}` }"
          :show-file-list="false"
          :on-success="handleImportSuccess"
          accept=".xlsx"
        >
          <el-button>导入Excel</el-button>
        </el-upload>
        <el-button type="primary" @click="handleCreate">新增指标</el-button>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="filter-bar">
      <el-select v-model="filters.domain" placeholder="所属域" clearable>
        <el-option label="营销域" value="营销域" />
        <el-option label="供应链域" value="供应链域" />
      </el-select>
      <el-select v-model="filters.category1" placeholder="一级分类" clearable>
        <el-option label="国内营销" value="国内营销" />
      </el-select>
      <el-input v-model="filters.keyword" placeholder="搜索指标名称" clearable style="width: 200px" />
      <el-button @click="loadMetrics">查询</el-button>
    </div>

    <!-- 表格 -->
    <div class="table-card">
      <el-table :data="metricsList" v-loading="loading" stripe>
        <el-table-column prop="metric_code" label="指标编号" width="140" />
        <el-table-column prop="name" label="指标名称" min-width="150" />
        <el-table-column prop="domain" label="所属域" width="100" />
        <el-table-column prop="category_1" label="一级分类" width="100" />
        <el-table-column prop="metric_type" label="类型" width="100" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="frequency" label="频度" width="80" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === '在用' ? 'success' : 'info'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">查看</el-button>
            <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadMetrics"
        @current-change="loadMetrics"
        style="margin-top: 20px"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { metricAPI } from '../api'
import { ElMessage } from 'element-plus'

const token = localStorage.getItem('access_token') || ''
const loading = ref(false)
const metricsList = ref([])
const filters = ref({ domain: '', category1: '', keyword: '' })
const pagination = ref({ page: 1, pageSize: 20, total: 0 })

onMounted(() => {
  loadMetrics()
})

async function loadMetrics() {
  loading.value = true
  try {
    const res = await metricAPI.list({
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      ...filters.value
    })
    if (res.data) {
      metricsList.value = res.data.list || []
      pagination.value.total = res.data.total || 0
    }
  } catch (e) {
    // 使用示例数据
    metricsList.value = [
      { id: 1, metric_code: 'MKI-01-0001', name: '日销售额', domain: '营销域', category_1: '国内营销', metric_type: '原子指标', unit: '元', frequency: '日', status: '在用' }
    ]
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  ElMessage.info('创建指标功能开发中')
}

function handleView(row) {
  ElMessage.info('查看指标功能开发中')
}

function handleEdit(row) {
  ElMessage.info('编辑指标功能开发中')
}

async function handleDelete(row) {
  try {
    await metricAPI.delete(row.id)
    ElMessage.success('删除成功')
    loadMetrics()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

function handleImportSuccess() {
  ElMessage.success('导入成功')
  loadMetrics()
}
</script>

<style scoped>
.metrics-page {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  background: rgba(255, 255, 255, 0.9);
  padding: 16px;
  border-radius: 12px;
}

.table-card {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 16px;
  padding: 24px;
}
</style>
