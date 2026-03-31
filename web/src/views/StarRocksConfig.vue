<template>
  <div class="starrocks-page">
    <div class="page-header">
      <h1 class="page-title">数据源配置</h1>
      <p class="page-desc">配置 StarRocks 连接信息，用于查询指标数据</p>
    </div>

    <div class="config-card">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px" class="config-form">
        <el-form-item label="配置名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：生产环境" />
        </el-form-item>

        <el-form-item label="Host" prop="host">
          <el-input v-model="form.host" placeholder="localhost 或 IP 地址" />
        </el-form-item>

        <el-form-item label="端口" prop="port">
          <el-input-number v-model="form.port" :min="1" :max="65535" placeholder="9030" />
        </el-form-item>

        <el-form-item label="用户名" prop="user">
          <el-input v-model="form.user" placeholder="root" />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="留空表示无密码" />
        </el-form-item>

        <el-form-item label="数据库" prop="database">
          <el-input v-model="form.database" placeholder="例如：metrics_db" />
        </el-form-item>

        <el-form-item label="连接超时">
          <el-input-number v-model="form.timeout" :min="1" :max="60" /> 秒
        </el-form-item>

        <el-form-item label="查询超时">
          <el-input-number v-model="form.query_timeout" :min="5" :max="300" /> 秒
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleTest" :loading="testing">
            测试连接
          </el-button>
          <el-button type="success" @click="handleSave" :loading="saving">
            保存配置
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="tips-card">
      <h3>使用说明</h3>
      <ul>
        <li>配置 StarRocks 连接后，指标数据将实时从 StarRocks 查询</li>
        <li>查询结果会缓存在 Redis 中，默认 5 分钟</li>
        <li>修改配置后会自动重连</li>
        <li>确保 StarRocks 的连接信息正确，否则指标数据无法查询</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { starrocksAPI } from '../api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const formRef = ref(null)

const form = reactive({
  name: '',
  host: 'localhost',
  port: 9030,
  user: 'root',
  password: '',
  database: 'metrics_db',
  timeout: 10,
  query_timeout: 30
})

const rules = {
  host: [{ required: true, message: '请输入 Host', trigger: 'blur' }],
  port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
  user: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  database: [{ required: true, message: '请输入数据库名', trigger: 'blur' }]
}

onMounted(() => {
  loadConfig()
})

async function loadConfig() {
  loading.value = true
  try {
    const res = await starrocksAPI.getConfig()
    if (res.code === 0 && res.data) {
      const d = res.data
      form.name = d.name || ''
      form.host = d.host || 'localhost'
      form.port = d.port || 9030
      form.user = d.user || 'root'
      form.database = d.database || ''
      form.timeout = d.timeout || 10
      form.query_timeout = d.query_timeout || 30
      form.password = ''
    }
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

async function handleTest() {
  testing.value = true
  try {
    const res = await starrocksAPI.testConnection({
      host: form.host,
      port: form.port,
      user: form.user,
      password: form.password,
      database: form.database,
      timeout: form.timeout
    })
    if (res.code === 0) {
      ElMessage.success('连接成功')
    } else {
      ElMessage.error(res.message || '连接失败')
    }
  } catch (err) {
    ElMessage.error('连接测试失败')
  } finally {
    testing.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    const res = await starrocksAPI.updateConfig(form)
    if (res.code === 0) {
      ElMessage.success('保存成功')
    } else {
      ElMessage.error(res.message || '保存失败')
    }
  } catch (err) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.starrocks-page {
  padding: 32px;
  max-width: 800px;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  margin: 0 0 8px 0;
}

.page-desc {
  font-size: 14px;
  color: var(--text-secondary, #666);
  margin: 0;
}

.config-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  margin-bottom: 20px;
}

.dark-mode .config-card {
  background: rgba(255, 255, 255, 0.05);
}

.config-form {
  max-width: 500px;
}

.tips-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px 20px;
  border-left: 4px solid #409eff;
}

.dark-mode .tips-card {
  background: rgba(64, 158, 255, 0.1);
}

.tips-card h3 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: #409eff;
}

.tips-card ul {
  margin: 0;
  padding-left: 20px;
  color: var(--text-secondary, #666);
  font-size: 13px;
  line-height: 1.8;
}
</style>
