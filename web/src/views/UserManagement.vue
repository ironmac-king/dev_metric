<template>
  <div class="user-management">
    <div class="header">
      <h2>用户管理</h2>
      <el-button type="primary" @click="openCreateDialog">
        <el-icon><Plus /></el-icon> 添加用户
      </el-button>
    </div>

    <el-table :data="users" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" width="150" />
      <el-table-column prop="dept" label="部门" width="150" />
      <el-table-column prop="role" label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : row.role === 'analyst' ? 'warning' : 'success'" size="small">
            {{ getRoleDisplayName(row.role) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="data_filter" label="数据权限（SQL过滤）" min-width="200">
        <template #default="{ row }">
          <span v-if="row.data_filter" class="data-filter-text">{{ row.data_filter }}</span>
          <span v-else class="no-filter">无</span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="openEditDialog(row)">编辑</el-button>
          <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '添加用户'" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" placeholder="请输入用户名" :disabled="isEdit" />
        </el-form-item>
        <el-form-item :label="isEdit ? '新密码' : '密码'" :required="!isEdit">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
          <span v-if="isEdit" class="tip">留空则保持原密码</span>
        </el-form-item>
        <el-form-item label="部门">
          <el-input v-model="form.dept" placeholder="请输入部门" />
        </el-form-item>
        <el-form-item label="部门ID">
          <el-input-number v-model="form.dept_id" :min="0" />
        </el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="form.role" placeholder="请选择角色">
            <el-option v-for="role in roles" :key="role.id" :label="role.display_name" :value="role.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据权限">
          <el-input
            v-model="form.data_filter"
            type="textarea"
            :rows="2"
            placeholder="自定义SQL WHERE条件，如: region = '华东' AND channel = '线上'"
          />
          <span class="tip">设置后用户只能看到符合条件的数据</span>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="loading">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { userAPI, roleAPI } from '../api'

const users = ref([])
const roles = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const loading = ref(false)

const form = ref({
  id: null,
  username: '',
  password: '',
  dept: '',
  dept_id: 0,
  role: 'user',
  data_filter: '',
  status: 1
})

async function fetchUsers() {
  try {
    const res = await userAPI.list()
    users.value = res.data || []
  } catch (e) {
    ElMessage.error('获取用户列表失败')
  }
}

async function fetchRoles() {
  try {
    const res = await roleAPI.list()
    roles.value = res.data || []
  } catch (e) {
    console.error('获取角色列表失败', e)
  }
}

// 根据角色名获取显示名称
function getRoleDisplayName(roleName) {
  const role = roles.value.find(r => r.name === roleName)
  return role ? role.display_name : (roleName === 'admin' ? '管理员' : roleName === 'analyst' ? '分析师' : '普通用户')
}

function openCreateDialog() {
  isEdit.value = false
  form.value = {
    id: null,
    username: '',
    password: '',
    dept: '',
    dept_id: 0,
    role: 'user',
    data_filter: '',
    status: 1
  }
  dialogVisible.value = true
}

function openEditDialog(row) {
  isEdit.value = true
  form.value = {
    id: row.id,
    username: row.username,
    password: '',
    dept: row.dept || '',
    dept_id: row.dept_id || 0,
    role: row.role,
    data_filter: row.data_filter || '',
    status: row.status
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.value.username || (!isEdit.value && !form.value.password)) {
    ElMessage.warning('请填写必填项')
    return
  }

  loading.value = true
  try {
    if (isEdit.value) {
      await userAPI.update(form.value.id, form.value)
      ElMessage.success('更新成功')
    } else {
      await userAPI.create(form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchUsers()
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    loading.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除用户「${row.username}」吗？`, '提示', {
      type: 'warning'
    })
    await userAPI.delete(row.id)
    ElMessage.success('删除成功')
    fetchUsers()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  fetchUsers()
  fetchRoles()
})
</script>

<style scoped>
.user-management {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.data-filter-text {
  font-size: 12px;
  color: #666;
  word-break: break-all;
}

.no-filter {
  color: #999;
  font-size: 13px;
}

.tip {
  display: block;
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
</style>
