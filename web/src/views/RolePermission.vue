<template>
  <div class="role-permission">
    <div class="header">
      <h2>角色权限配置</h2>
    </div>

    <div class="content">
      <!-- 左侧角色列表 -->
      <div class="role-list">
        <div class="role-list-header">
          <span>角色</span>
          <el-button text @click="openCreateDialog">
            <el-icon><Plus /></el-icon> 新增
          </el-button>
        </div>
        <div class="role-items">
          <div
            v-for="role in roles"
            :key="role.id"
            class="role-item"
            :class="{ active: selectedRole?.name === role.name }"
            @click="selectRole(role)"
          >
            <span class="role-name">{{ role.display_name || role.name }}</span>
            <span class="role-desc">{{ role.description }}</span>
          </div>
        </div>
      </div>

      <!-- 右侧权限树 -->
      <div class="permission-tree">
        <div v-if="!selectedRole" class="empty-tip">
          请选择左侧角色进行权限配置
        </div>

        <div v-else>
          <div class="permission-header">
            <span>{{ selectedRole.display_name || selectedRole.name }} 的权限</span>
            <div class="header-actions">
              <el-button size="small" @click="checkAll">全选</el-button>
              <el-button size="small" @click="uncheckAll">取消</el-button>
              <el-button type="primary" size="small" @click="savePermissions" :loading="saving">
                保存
              </el-button>
            </div>
          </div>

          <el-input v-model="searchKeyword" placeholder="搜索权限..." class="search-input" clearable />

          <!-- 按分组显示权限 -->
          <div v-for="group in filteredGroupedMenus" :key="group.name" class="menu-group">
            <div class="group-header">
              <el-checkbox
                :model-value="group.checked"
                :indeterminate="group.indeterminate"
                @change="(val) => handleGroupCheck(group, val)"
              >
                {{ group.name }}
              </el-checkbox>
            </div>
            <div class="group-items">
              <div
                v-for="menu in group.menus"
                :key="menu.path"
                class="menu-item"
              >
                <el-checkbox
                  v-model="menuCheckedState[menu.path]"
                  @change="(val) => handleMenuCheck(menu.path, val)"
                >
                  {{ menu.name }}
                </el-checkbox>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 创建角色弹窗 -->
    <el-dialog v-model="createDialogVisible" title="新增角色" width="400px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="角色标识" required>
          <el-input v-model="createForm.name" placeholder="如: analyst" />
          <span class="tip">角色标识唯一，用于系统识别</span>
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="createForm.display_name" placeholder="如: 分析师" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreateRole">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { roleAPI } from '../api'

const roles = ref([])
const selectedRole = ref(null)
const allMenus = ref([])
const saving = ref(false)
const searchKeyword = ref('')

// 菜单选中状态：key = menu.path, value = checked (boolean)
// 使用普通对象而非 Map，以支持 Vue 响应式追踪
const menuCheckedState = ref({})

const createDialogVisible = ref(false)
const createForm = ref({
  name: '',
  display_name: '',
  description: ''
})

// 菜单分组（静态结构，仅重组不过滤）
const groupedMenus = computed(() => {
  const groups = {}
  allMenus.value.forEach(menu => {
    const groupName = menu.group || '其他'
    if (!groups[groupName]) {
      groups[groupName] = {
        name: groupName,
        menus: []
      }
    }
    groups[groupName].menus.push(menu)
  })
  return Object.values(groups)
})

// 根据搜索过滤，同时附加选中状态
const filteredGroupedMenus = computed(() => {
  const keyword = searchKeyword.value.toLowerCase()

  return groupedMenus.value
    .map(group => {
      const filteredMenus = keyword
        ? group.menus.filter(m =>
            m.name.toLowerCase().includes(keyword) ||
            m.path.toLowerCase().includes(keyword)
          )
        : group.menus

      return {
        ...group,
        menus: filteredMenus,
        // 动态计算 group 的 checked 和 indeterminate
        get checked() {
          return filteredMenus.every(m => menuCheckedState.value[m.path])
        },
        get indeterminate() {
          const checkedCount = filteredMenus.filter(m => menuCheckedState.value[m.path]).length
          return checkedCount > 0 && checkedCount < filteredMenus.length
        }
      }
    })
    .filter(group => group.menus.length > 0)
})

async function fetchRoles() {
  try {
    const res = await roleAPI.list()
    roles.value = res.data || []
  } catch (e) {
    ElMessage.error('获取角色列表失败')
  }
}

async function fetchAllMenus() {
  try {
    const res = await roleAPI.getAllMenus()
    allMenus.value = res.data || []
  } catch (e) {
    ElMessage.error('获取菜单列表失败')
  }
}

async function selectRole(role) {
  selectedRole.value = role

  try {
    const res = await roleAPI.getMenus(role.name)
    const userMenus = res.data || []

    // 重置选中状态
    menuCheckedState.value = {}

    // 设置选中状态
    allMenus.value.forEach(menu => {
      const isChecked = userMenus.some(m => m.menu_path === menu.path)
      menuCheckedState.value[menu.path] = isChecked
    })
  } catch (e) {
    ElMessage.error('获取角色权限失败')
  }
}

function handleMenuCheck(menuPath, isChecked) {
  // isChecked 是 Element Plus 传来的新值，直接使用
  menuCheckedState.value[menuPath] = isChecked
}

function handleGroupCheck(group, isChecked) {
  // isChecked 是 Element Plus 传来的新值，直接使用
  group.menus.forEach(menu => {
    menuCheckedState.value[menu.path] = isChecked
  })
}

function checkAll() {
  filteredGroupedMenus.value.forEach(group => {
    group.menus.forEach(menu => {
      menuCheckedState.value[menu.path] = true
    })
  })
}

function uncheckAll() {
  filteredGroupedMenus.value.forEach(group => {
    group.menus.forEach(menu => {
      menuCheckedState.value[menu.path] = false
    })
  })
}

async function savePermissions() {
  if (!selectedRole.value) return

  saving.value = true
  try {
    const menus = []
    allMenus.value.forEach((menu, index) => {
      if (menuCheckedState.value[menu.path]) {
        menus.push({
          menu_path: menu.path,
          menu_name: menu.name,
          parent_path: menu.parent_path || '',
          sort_order: index + 1
        })
      }
    })

    await roleAPI.updateMenus(selectedRole.value.name, menus)
    ElMessage.success('权限保存成功')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleCreateRole() {
  if (!createForm.value.name) {
    ElMessage.warning('请输入角色标识')
    return
  }

  try {
    await roleAPI.create(createForm.value)
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    createForm.value = { name: '', display_name: '', description: '' }
    fetchRoles()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

function openCreateDialog() {
  createForm.value = { name: '', display_name: '', description: '' }
  createDialogVisible.value = true
}

onMounted(() => {
  fetchRoles()
  fetchAllMenus()
})
</script>

<style scoped>
.role-permission {
  padding: 20px;
  height: 100%;
}

.header {
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.content {
  display: flex;
  gap: 20px;
  height: calc(100vh - 160px);
}

.role-list {
  width: 240px;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  flex-shrink: 0;
}

.role-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  font-weight: 600;
}

.role-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.role-item {
  padding: 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.role-item:hover {
  background: #f5f5f5;
}

.role-item.active {
  background: #e6f7ff;
  border: 1px solid #1890ff;
}

.role-name {
  display: block;
  font-weight: 500;
  margin-bottom: 4px;
}

.role-desc {
  font-size: 12px;
  color: #999;
}

.permission-tree {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  overflow-y: auto;
}

.empty-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
}

.permission-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.search-input {
  margin-bottom: 20px;
  max-width: 300px;
}

.menu-group {
  margin-bottom: 20px;
  border: 1px solid #eee;
  border-radius: 8px;
  overflow: hidden;
}

.group-header {
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #eee;
}

.group-items {
  padding: 12px 16px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

.menu-item {
  padding: 4px 0;
}

.tip {
  display: block;
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
</style>
