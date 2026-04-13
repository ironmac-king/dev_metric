<template>
  <div class="metrics-page" :class="{ 'dark-mode': isDark }">
    <!-- Top Navigation Bar (Glassmorphism) -->
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
        <span class="nav-title">指标中心</span>
      </div>
      <div class="nav-right">
        <el-button type="primary" class="btn-primary" @click="handleCreate">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
          新建指标
        </el-button>
      </div>
    </div>

    <!-- Main Content -->
    <div class="main-content">
      <!-- Filter Panel (Glassmorphism) -->
      <div class="filter-panel">
        <div class="filter-group">
          <el-select v-model="filters.domain" placeholder="所属域" clearable size="large" class="filter-select">
            <template #prefix><span class="filter-tag">域</span></template>
            <el-option label="全部" value="" />
            <el-option label="营销域" value="营销域" />
            <el-option label="供应链域" value="供应链域" />
          </el-select>
          <el-select v-model="filters.metric_type" placeholder="指标类型" clearable size="large" class="filter-select">
            <template #prefix><span class="filter-tag">类</span></template>
            <el-option label="全部" value="" />
            <el-option label="原子指标" value="原子指标" />
            <el-option label="派生指标" value="派生指标" />
            <el-option label="复合指标" value="复合指标" />
          </el-select>
          <el-select v-model="filters.status" placeholder="状态" clearable size="large" class="filter-select">
            <template #prefix><span class="filter-tag">态</span></template>
            <el-option label="全部" value="" />
            <el-option label="在用" value="在用" />
            <el-option label="停用" value="停用" />
          </el-select>
        </div>
        <div class="search-group">
          <el-input
            v-model="filters.keyword"
            placeholder="搜索指标名称或编号..."
            size="large"
            clearable
            class="search-input"
          >
            <template #prefix>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="6" cy="6" r="4" stroke="currentColor" stroke-width="1.3"/>
                <path d="M9.5 9.5L12.5 12.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
              </svg>
            </template>
          </el-input>
          <el-button size="large" @click="loadMetrics" class="btn-search">搜索</el-button>
        </div>
      </div>

      <!-- Stats Row -->
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-value">{{ stats.total }}</span>
          <span class="stat-label">指标总数</span>
        </div>
        <div class="stat-card">
          <span class="stat-value accent">{{ stats.active }}</span>
          <span class="stat-label">在用指标</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ stats.inactive }}</span>
          <span class="stat-label">停用指标</span>
        </div>
      </div>

      <!-- Table Container -->
      <div class="table-container">
        <!-- Import Button -->
        <div class="table-toolbar">
          <el-upload
            :action="'/api/v1/metrics/import-preview'"
            :headers="{ Authorization: `Bearer ${token}` }"
            :show-file-list="false"
            :on-change="handleImportChange"
            :auto-upload="false"
            accept=".xlsx"
            ref="uploadRef"
          >
            <el-button class="btn-import">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 9.5V2.5M7 2.5L4.5 5M7 2.5L9.5 5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M2 9.5V10.5C2 11 2.5 11.5 3 11.5H11C11.5 11.5 12 11 12 10.5V9.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
              </svg>
              导入
            </el-button>
          </el-upload>
          <el-button class="btn-import" @click="downloadTemplate">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 2.5V9.5M7 9.5L4.5 7M7 9.5L9.5 7" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M2 9.5V10.5C2 11 2.5 11.5 3 11.5H11C11.5 11.5 12 11 12 10.5V9.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
            </svg>
            下载模板
          </el-button>
          <el-button class="btn-import" @click="downloadSample">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 10.5V11.5C2 12 2.5 12.5 3 12.5H11C11.5 12.5 12 12 12 11.5V10.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
              <path d="M7 2.5V9.5M7 9.5L4.5 7M7 9.5L9.5 7" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            下载样例
          </el-button>
        </div>

        <el-table
          :data="metricsList"
          v-loading="loading"
          class="metrics-table"
          row-class-name="table-row"
          @row-click="handleRowClick"
        >
          <el-table-column prop="metric_code" label="指标编号" width="180" align="right">
            <template #default="{ row }">
              <span class="code-text">{{ row.metric_code }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="指标名称" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tooltip :content="row.name + (row.name_en ? '\n' + row.name_en : '')" placement="top" :show-after="300" raw-content>
                <div class="metric-name-cell">
                  <span class="name-text">{{ row.name }}</span>
                  <span v-if="row.name_en" class="name-en">{{ row.name_en }}</span>
                </div>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column prop="domain" label="所属域" width="140" align="center">
            <template #default="{ row }">
              <span class="domain-label">{{ row.domain || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="metric_type" label="类型" width="120" align="center">
            <template #default="{ row }">
              <span class="type-label" :class="getTypeClass(row.metric_type)">
                {{ formatType(row.metric_type) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="owner_dept" label="负责部门" width="150">
            <template #default="{ row }">
              <el-tooltip :content="row.owner_dept || '-'" placement="top" :show-after="300">
                <span class="dept-text">{{ row.owner_dept || '-' }}</span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column prop="frequency" label="统计频度" width="140" align="center">
            <template #default="{ row }">
              <span class="freq-text">{{ row.frequency || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100" align="center">
            <template #default="{ row }">
              <span class="status-label" :class="row.status === '在用' ? 'active' : 'inactive'">
                <span class="status-dot"></span>
                {{ row.status === '在用' ? '在用' : '停用' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="updated_by" label="更新人" width="100" align="center">
            <template #default="{ row }">
              <span class="updater-text">{{ row.updated_by || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="updated_at" label="更新时间" width="160" align="center">
            <template #default="{ row }">
              <span class="update-time">{{ formatTime(row.updated_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" align="center" fixed="right">
            <template #default="{ row }">
              <div class="action-group">
                <el-button link class="action-btn view" @click.stop="handleView(row)" title="查看">
                  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                    <path d="M7.5 3C4.5 3 2 7.5 2 7.5C2 7.5 4.5 12 7.5 12C10.5 12 13 7.5 13 7.5C13 7.5 10.5 3 7.5 3Z" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
                    <circle cx="7.5" cy="7.5" r="2" stroke="currentColor" stroke-width="1.3"/>
                  </svg>
                </el-button>
                <el-button link class="action-btn edit" @click.stop="handleEdit(row)" title="编辑">
                  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                    <path d="M10.5 2.5L12.5 4.5L5 12H3V10L10.5 2.5Z" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </el-button>
                <el-button link class="action-btn delete" @click.stop="handleDelete(row)" title="删除">
                  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                    <path d="M3 4H12M5.5 4V3C5.5 2.5 6 2 6.5 2H8.5C9 2 9.5 2.5 9.5 3V4M11 4V12C11 12.5 10.5 13 10 13H5C4.5 13 4 12.5 4 12V4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                  </svg>
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <!-- Pagination -->
        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :total="pagination.total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            @size-change="loadMetrics"
            @current-change="loadMetrics"
          />
        </div>
      </div>
    </div>

    <!-- Detail Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="900px"
      :close-on-click-modal="false"
      class="metric-dialog"
      destroy-on-close
    >
      <template #header="{ titleId }">
        <div class="dialog-header">
          <div class="dialog-title-wrap">
            <span :id="titleId" class="dialog-title">{{ dialogTitle }}</span>
            <span class="dialog-code" v-if="currentMetric.metric_code">{{ currentMetric.metric_code }}</span>
          </div>
          <div class="dialog-status" :class="currentMetric.status === '在用' ? 'active' : 'inactive'">
            <span class="dialog-status-dot"></span>
            {{ currentMetric.status }}
          </div>
        </div>
      </template>

      <div v-if="dialogMode === 'view'" class="dialog-content view-mode">
        <el-tabs v-model="activeTab" class="metric-tabs">
          <el-tab-pane label="基本信息" name="basic">
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">指标编号</span>
                <span class="info-value code">{{ currentMetric.metric_code || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">指标类型</span>
                <span class="info-value">
                  <span class="type-label" :class="getTypeClass(currentMetric.metric_type)">
                    {{ formatType(currentMetric.metric_type) }}
                  </span>
                </span>
              </div>
              <div class="info-item">
                <span class="info-label">指标名称</span>
                <span class="info-value">{{ currentMetric.name || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">英文名称</span>
                <span class="info-value en">{{ currentMetric.name_en || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">所属域</span>
                <span class="domain-label">{{ currentMetric.domain || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">统计频度</span>
                <span class="info-value">{{ currentMetric.frequency || '-' }}</span>
              </div>
              <div class="info-item full">
                <span class="info-label">分类路径</span>
                <span class="info-value">
                  {{ [currentMetric.category_1, currentMetric.category_2, currentMetric.category_3].filter(Boolean).join(' / ') || '-' }}
                </span>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="业务定义" name="business">
            <div class="info-section">
              <div class="section-item">
                <span class="section-label">业务定义</span>
                <div class="section-content">{{ currentMetric.business_definition || '暂无' }}</div>
              </div>
              <div class="section-item">
                <span class="section-label">业务口径</span>
                <div class="section-content mono">{{ currentMetric.business_rule || '暂无' }}</div>
              </div>
              <div class="section-item">
                <span class="section-label">技术口径</span>
                <div class="section-content mono">{{ currentMetric.technical_rule || '暂无' }}</div>
              </div>
              <div class="section-item">
                <span class="section-label">适用Scope</span>
                <div class="section-content">{{ currentMetric.applicable_scope || '暂无' }}</div>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="技术属性" name="tech">
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">度量单位</span>
                <span class="info-value">{{ currentMetric.unit || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">统计频度</span>
                <span class="info-value">{{ currentMetric.frequency || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">数据格式</span>
                <span class="info-value">{{ currentMetric.data_format || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">精度</span>
                <span class="info-value">{{ currentMetric.precision || '-' }}</span>
              </div>
              <div class="info-item full">
                <span class="info-label">通用维度</span>
                <span class="info-value">{{ currentMetric.common_dimensions || '-' }}</span>
              </div>
              <div class="info-item full">
                <span class="info-label">组织层级</span>
                <span class="info-value">{{ currentMetric.org_level || '-' }}</span>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="管理信息" name="manage">
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">负责部门</span>
                <span class="info-value">{{ currentMetric.owner_dept || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">发布日期</span>
                <span class="info-value">{{ currentMetric.publish_date || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">失效日期</span>
                <span class="info-value">{{ currentMetric.expire_date || '-' }}</span>
              </div>
            </div>
            <div class="section-item" style="margin-top: 20px;">
              <div class="section-header">
                <span class="section-label">查询SQL</span>
                <el-button size="small" @click="showSQLDialog" class="sql-btn">
                  <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                    <rect x="1" y="1" width="11" height="11" rx="2" stroke="currentColor" stroke-width="1.2"/>
                    <path d="M3.5 4.5L6 7L3.5 9.5M7.5 9.5H9.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  查看SQL
                </el-button>
              </div>
              <div class="section-content sql-mini" @click="showSQLDialog">
                <pre>{{ currentMetric.starrocks_sql || '暂无SQL配置' }}</pre>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- Create/Edit Form -->
      <el-form v-else ref="formRef" :model="formData" :rules="formRules" label-position="top" class="metric-form">
        <el-tabs v-model="activeTab" class="metric-tabs">
          <el-tab-pane label="基本信息" name="basic">
            <div class="form-grid">
              <el-form-item label="指标编号" prop="metric_code" class="form-item">
                <el-input v-model="formData.metric_code" placeholder="如 MKI-02-0001" />
              </el-form-item>
              <el-form-item label="指标名称" prop="name" class="form-item">
                <el-input v-model="formData.name" placeholder="如 广告转化率" />
              </el-form-item>
              <el-form-item label="英文名称" prop="name_en" class="form-item">
                <el-input v-model="formData.name_en" placeholder="如 Ad Conversion Rate" />
              </el-form-item>
              <el-form-item label="所属域" prop="domain" class="form-item">
                <el-select v-model="formData.domain" placeholder="请选择所属域" style="width: 100%">
                  <el-option label="营销域" value="营销域" />
                  <el-option label="供应链域" value="供应链域" />
                </el-select>
              </el-form-item>
              <el-form-item label="指标类型" prop="metric_type" class="form-item">
                <el-select v-model="formData.metric_type" placeholder="请选择类型" style="width: 100%">
                  <el-option label="原子指标" value="原子指标" />
                  <el-option label="派生指标" value="派生指标" />
                  <el-option label="复合指标" value="复合指标" />
                </el-select>
              </el-form-item>
              <el-form-item label="状态" prop="status" class="form-item">
                <el-select v-model="formData.status" placeholder="请选择状态" style="width: 100%">
                  <el-option label="在用" value="在用" />
                  <el-option label="停用" value="停用" />
                </el-select>
              </el-form-item>
            </div>
            <div class="form-row">
              <el-form-item label="一级分类" prop="category_1" class="form-item-inline">
                <el-input v-model="formData.category_1" placeholder="如 国内营销" />
              </el-form-item>
              <el-form-item label="二级分类" prop="category_2" class="form-item-inline">
                <el-input v-model="formData.category_2" />
              </el-form-item>
              <el-form-item label="三级分类" prop="category_3" class="form-item-inline">
                <el-input v-model="formData.category_3" />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane label="业务定义" name="business">
            <el-form-item label="业务定义" prop="business_definition">
              <el-input v-model="formData.business_definition" type="textarea" :rows="3" placeholder="请输入业务定义" />
            </el-form-item>
            <el-form-item label="业务口径" prop="business_rule">
              <el-input v-model="formData.business_rule" type="textarea" :rows="3" placeholder="请输入业务口径" />
            </el-form-item>
            <el-form-item label="技术口径" prop="technical_rule">
              <el-input v-model="formData.technical_rule" type="textarea" :rows="3" placeholder="请输入技术口径" />
            </el-form-item>
            <div class="form-grid">
              <el-form-item label="适用Scope" prop="applicable_scope" class="form-item">
                <el-input v-model="formData.applicable_scope" placeholder="如 全平台" />
              </el-form-item>
              <el-form-item label="统计规则" prop="statistics_rule" class="form-item">
                <el-input v-model="formData.statistics_rule" placeholder="如 SUM(revenue)" />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane label="技术属性" name="tech">
            <div class="form-grid">
              <el-form-item label="度量单位" prop="unit" class="form-item">
                <el-input v-model="formData.unit" placeholder="如 元、%、次" />
              </el-form-item>
              <el-form-item label="统计频度" prop="frequency" class="form-item">
                <el-select v-model="formData.frequency" placeholder="请选择频度" style="width: 100%">
                  <el-option label="日" value="日" />
                  <el-option label="周" value="周" />
                  <el-option label="月" value="月" />
                  <el-option label="年" value="年" />
                </el-select>
              </el-form-item>
              <el-form-item label="数据格式" prop="data_format" class="form-item">
                <el-input v-model="formData.data_format" placeholder="如 #,##0.00" />
              </el-form-item>
              <el-form-item label="精度" prop="precision" class="form-item">
                <el-input v-model="formData.precision" placeholder="如 2" />
              </el-form-item>
            </div>
            <el-form-item label="通用维度" prop="common_dimensions">
              <el-input v-model="formData.common_dimensions" placeholder="如 平台、地区、渠道" />
            </el-form-item>
            <el-form-item label="组织层级" prop="org_level">
              <el-input v-model="formData.org_level" placeholder="如 公司-事业部-部门" />
            </el-form-item>
          </el-tab-pane>

          <el-tab-pane label="管理信息" name="manage">
            <div class="form-grid">
              <el-form-item label="负责部门" prop="owner_dept" class="form-item">
                <el-input v-model="formData.owner_dept" placeholder="如 数据产品部" />
              </el-form-item>
              <el-form-item label="发布日期" prop="publish_date" class="form-item">
                <el-date-picker v-model="formData.publish_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
              </el-form-item>
              <el-form-item label="失效日期" prop="expire_date" class="form-item">
                <el-date-picker v-model="formData.expire_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
              </el-form-item>
            </div>
            <el-form-item label="查询SQL" prop="starrocks_sql">
              <el-input v-model="formData.starrocks_sql" type="textarea" :rows="5" placeholder="SELECT ..." />
            </el-form-item>
          </el-tab-pane>
        </el-tabs>
      </el-form>

      <template #footer v-if="dialogMode !== 'view'">
        <div class="dialog-footer">
          <el-button size="large" @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" size="large" @click="dialogMode === 'create' ? submitForm() : submitEdit()" :loading="submitting" class="btn-primary">
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- SQL Dialog -->
    <el-dialog v-model="sqlDialogVisible" title="查询SQL" width="850px" class="sql-dialog">
      <div class="sql-toolbar">
        <span class="sql-label">SQL 预览</span>
        <el-button size="small" @click="copySQL" class="copy-btn">
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <rect x="4" y="4" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.2"/>
            <path d="M2 9V2H9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          复制
        </el-button>
      </div>
      <pre class="sql-preview">{{ currentMetric.starrocks_sql || '暂无SQL' }}</pre>
    </el-dialog>

    <!-- Import Preview Dialog -->
    <el-dialog v-model="importDialogVisible" title="导入预览" width="900px" class="import-dialog">
      <div v-if="importPreviewData" class="import-preview">
        <div class="import-summary">
          <el-row :gutter="20">
            <el-col :span="6">
              <div class="summary-item">
                <span class="summary-label">总条数</span>
                <span class="summary-value">{{ importPreviewData.total }}</span>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-item new">
                <span class="summary-label">新增</span>
                <span class="summary-value">{{ importPreviewData.new_count }}</span>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-item update">
                <span class="summary-label">更新</span>
                <span class="summary-value">{{ importPreviewData.update_count }}</span>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-item error" v-if="importPreviewData.errors && importPreviewData.errors.length > 0">
                <span class="summary-label">错误</span>
                <span class="summary-value">{{ importPreviewData.errors.length }}</span>
              </div>
              <div class="summary-item" v-else>
                <span class="summary-label">错误</span>
                <span class="summary-value success">0</span>
              </div>
            </el-col>
          </el-row>
        </div>

        <div v-if="importPreviewData.errors && importPreviewData.errors.length > 0" class="import-errors">
          <div class="error-title">错误列表</div>
          <div class="error-list">
            <div v-for="(err, idx) in importPreviewData.errors" :key="idx" class="error-item">
              <span class="error-row">第{{ err.row }}行</span>
              <span class="error-field">{{ err.field }}</span>
              <span class="error-msg">{{ err.message }}</span>
            </div>
          </div>
        </div>

        <div class="import-table-wrap">
          <div class="preview-title">预览（前10条）</div>
          <el-table :data="importPreviewData.preview" border size="small" max-height="300">
            <el-table-column prop="metric_code" label="指标编号" width="150" />
            <el-table-column prop="name" label="指标名称" min-width="200" show-overflow-tooltip />
            <el-table-column prop="domain" label="所属域" width="120" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <span :class="row.is_new ? 'status-new' : 'status-update'">
                  {{ row.is_new ? '新增' : '更新' }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button size="large" @click="importDialogVisible = false">取消</el-button>
          <el-button type="primary" size="large" @click="confirmImport" :loading="importing" :disabled="importPreviewData.errors && importPreviewData.errors.length > 0">
            确认导入
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { metricAPI, downloadFile } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const token = localStorage.getItem('access_token') || ''
const isDark = ref(false)
const loading = ref(false)
const metricsList = ref([])
const filters = ref({ domain: '', metric_type: '', status: '', keyword: '' })
const pagination = ref({ page: 1, pageSize: 20, total: 0 })
const stats = ref({ total: 0, active: 0, inactive: 0 })

// Dialog
const dialogVisible = ref(false)
const dialogMode = ref('view')
const dialogTitle = ref('指标详情')
const activeTab = ref('basic')
const submitting = ref(false)
const formRef = ref(null)
const sqlDialogVisible = ref(false)
const currentMetric = ref({})

// Import
const importDialogVisible = ref(false)
const importPreviewData = ref(null)
const importToken = ref('')
const importing = ref(false)
const uploadRef = ref(null)

const formData = ref({
  metric_code: '', name: '', name_en: '', domain: '', category_1: '', category_2: '', category_3: '',
  metric_type: '', status: '在用', business_definition: '', business_rule: '', technical_rule: '',
  applicable_scope: '', statistics_rule: '', unit: '', frequency: '', common_dimensions: '',
  org_level: '', data_format: '', precision: '', owner_dept: '', publish_date: '', expire_date: '', starrocks_sql: ''
})

const formRules = {
  metric_code: [{ required: true, message: '请输入指标编号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入指标名称', trigger: 'blur' }],
  domain: [{ required: true, message: '请选择所属域', trigger: 'change' }]
}

const activeCount = computed(() => {
  return metricsList.value.filter(m => m.status === '在用').length
})

onMounted(() => {
  loadMetrics()
  loadStats()
  // Detect system dark mode
  isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
})

function getTypeClass(type) {
  if (!type) return ''
  if (type.includes('原子')) return 'atomic'
  if (type.includes('派生')) return 'derived'
  if (type.includes('复合')) return 'composite'
  return ''
}

function formatType(type) {
  if (!type) return '-'
  if (type.includes('原子')) return '原子'
  if (type.includes('派生')) return '派生'
  if (type.includes('复合')) return '复合'
  return type
}

function formatTime(time) {
  if (!time) return '-'
  const d = new Date(time)
  if (isNaN(d.getTime())) return '-'
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hour = String(d.getHours()).padStart(2, '0')
  const minute = String(d.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}

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
    await loadStats()
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    const res = await metricAPI.getStats()
    if (res.data) {
      stats.value = res.data
    }
  } catch (e) {
    console.error('加载统计失败:', e)
  }
}

async function handleView(row) {
  dialogMode.value = 'view'
  dialogTitle.value = '指标详情'
  try {
    const res = await metricAPI.get(row.id)
    if (res.data) {
      currentMetric.value = res.data
      dialogVisible.value = true
      activeTab.value = 'basic'
    }
  } catch (e) {
    ElMessage.error('获取详情失败')
  }
}

function handleRowClick(row) {
  // Optional: could highlight selected row
}

function handleCreate() {
  dialogMode.value = 'create'
  dialogTitle.value = '新增指标'
  formData.value = {
    metric_code: '', name: '', name_en: '', domain: '', category_1: '', category_2: '', category_3: '',
    metric_type: '', status: '在用', business_definition: '', business_rule: '', technical_rule: '',
    applicable_scope: '', statistics_rule: '', unit: '', frequency: '', common_dimensions: '',
    org_level: '', data_format: '', precision: '', owner_dept: '', publish_date: '', expire_date: '', starrocks_sql: ''
  }
  dialogVisible.value = true
  activeTab.value = 'basic'
}

async function handleEdit(row) {
  dialogMode.value = 'edit'
  dialogTitle.value = '编辑指标'
  try {
    const res = await metricAPI.get(row.id)
    if (res.data) {
      currentMetric.value = res.data
      formData.value = { ...res.data }
      dialogVisible.value = true
      activeTab.value = 'basic'
    }
  } catch (e) {
    ElMessage.error('获取详情失败')
  }
}

async function submitForm() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
    submitting.value = true
    await metricAPI.create(formData.value)
    ElMessage.success('创建成功')
    dialogVisible.value = false
    loadMetrics()
  } catch (e) {
    if (e !== false) {
      ElMessage.error('创建失败')
    }
  } finally {
    submitting.value = false
  }
}

async function submitEdit() {
  submitting.value = true
  try {
    await metricAPI.update(currentMetric.value.id, formData.value)
    ElMessage.success('更新成功')
    dialogVisible.value = false
    loadMetrics()
  } catch (e) {
    ElMessage.error('更新失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除指标「${row.name}」吗？`,
      '删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await metricAPI.delete(row.id)
    ElMessage.success('删除成功')
    loadMetrics()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

function handleImportChange(file) {
  const formData = new FormData()
  formData.append('file', file.raw)
  formData.append('filename', file.name)

  metricAPI.importPreview(formData).then(res => {
    if (res.code === 0) {
      importPreviewData.value = res.data
      importToken.value = res.data.token
      importDialogVisible.value = true
    } else {
      ElMessage.error(res.message || '预览失败')
    }
  }).catch(err => {
    ElMessage.error('预览请求失败')
    console.error(err)
  })
}

function confirmImport() {
  if (!importToken.value) {
    ElMessage.error('缺少导入token')
    return
  }
  importing.value = true
  metricAPI.importCommit(importToken.value).then(res => {
    if (res.code === 0) {
      ElMessage.success(`导入成功：新增 ${res.data.new_count} 条，更新 ${res.data.update_count} 条`)
      importDialogVisible.value = false
      importPreviewData.value = null
      importToken.value = ''
      loadMetrics()
    } else {
      ElMessage.error(res.message || '导入失败')
    }
  }).catch(err => {
    ElMessage.error('导入请求失败')
    console.error(err)
  }).finally(() => {
    importing.value = false
  })
}

function downloadTemplate() {
  downloadFile('/metrics/export-template', 'metrics_template.xlsx')
    .catch(() => ElMessage.error('下载失败'))
}

function downloadSample() {
  downloadFile('/metrics/export-sample', 'metrics_sample.xlsx')
    .catch(() => ElMessage.error('下载失败'))
}

function copySQL() {
  navigator.clipboard.writeText(currentMetric.value.starrocks_sql || '')
  ElMessage.success('已复制到剪贴板')
}

function showSQLDialog() {
  sqlDialogVisible.value = true
}
</script>

<style scoped>
.metrics-page {
  min-height: 100vh;
  background: #f8f9fa;
}

/* Dark Mode Support */
.metrics-page.dark-mode {
  --bg-primary: #141414;
  --bg-card: rgba(30, 30, 30, 0.7);
  --text-primary: #e6e6e6;
  --text-secondary: #a0a0a0;
  --text-muted: #666666;
  --border: rgba(255, 255, 255, 0.1);
  background: #0a0a0a;
}

/* Top Navigation - Glassmorphism */
.top-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 56px;
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.03);
  position: sticky;
  top: 0;
  z-index: 100;
}

.dark-mode .top-nav {
  background: rgba(30, 30, 30, 0.8);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.nav-icon {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, var(--primary, #1677FF) 0%, #0958D9 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
}

.nav-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary, #1a1a1a);
  letter-spacing: -0.2px;
}

/* Main Content */
.main-content {
  padding: 24px 24px 32px;
  max-width: 1400px;
  margin: 0 auto;
}

/* Filter Panel - Glassmorphism */
.filter-panel {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.04);
}

.dark-mode .filter-panel {
  background: rgba(40, 40, 40, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.filter-group {
  display: flex;
  gap: 10px;
}

.search-group {
  display: flex;
  gap: 10px;
  align-items: center;
}

.filter-select {
  width: 130px;
}

.filter-tag {
  font-size: 11px;
  color: var(--text-muted, #999);
  padding-right: 4px;
}

.search-input {
  width: 220px;
}

.filter-panel :deep(.el-input__wrapper) {
  border-radius: 8px;
  box-shadow: none !important;
  border: 1px solid rgba(0, 0, 0, 0.08);
  transition: all 0.15s ease;
}

.dark-mode .filter-panel :deep(.el-input__wrapper) {
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(50, 50, 50, 0.5);
}

.filter-panel :deep(.el-input__wrapper:hover),
.filter-panel :deep(.el-input__wrapper.is-focus) {
  border-color: var(--primary, #0891B2);
}

/* Stats Row */
.stats-row {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  background: #ffffff;
  border-radius: 20px;
  padding: 20px 24px;
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 100px;
  border: 1px solid rgba(0, 0, 0, 0.04);
  transition: all 0.25s ease;
}

.stat-card:hover {
  transform: translateY(-3px) scale(1.01);
  box-shadow: var(--shadow-card-hover);
}

.dark-mode .stat-card {
  background: rgba(35, 35, 35, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary, #1a1a1a);
  letter-spacing: -0.5px;
}

.stat-value.accent {
  color: var(--primary, #0891B2);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary, #666);
  font-weight: 500;
}

/* Table Container */
.table-container {
  background: #ffffff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(0, 0, 0, 0.04);
}

.dark-mode .table-container {
  background: rgba(30, 30, 30, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.table-toolbar {
  display: flex;
  justify-content: flex-end;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

.dark-mode .table-toolbar {
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

.btn-import {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  color: var(--text-secondary, #666);
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 6px;
  font-weight: 500;
  font-size: 12px;
  padding: 6px 12px;
  transition: all 0.15s ease;
}

.btn-import:hover {
  background: var(--bg-primary, #f8f9fa);
  border-color: var(--primary, #6366F1);
  color: var(--primary, #6366F1);
}

/* Table Styles */
.metrics-table :deep(.el-table__header th) {
  background: #fafafa !important;
  font-weight: 600;
  font-size: 11px;
  color: var(--text-muted, #999);
  padding: 14px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.dark-mode .metrics-table :deep(.el-table__header th) {
  background: rgba(40, 40, 40, 0.5) !important;
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

.metrics-table :deep(.el-table__body td) {
  padding: 14px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
  transition: background-color 0.15s ease;
}

.dark-mode .metrics-table :deep(.el-table__body td) {
  border-bottom-color: rgba(255, 255, 255, 0.04);
}

.metrics-table :deep(.el-table__row) {
  transition: all 0.15s ease;
}

.metrics-table :deep(.el-table__row:hover > td) {
  background: #f8f9fa !important;
}

.dark-mode .metrics-table :deep(.el-table__row:hover > td) {
  background: rgba(50, 50, 50, 0.5) !important;
}

/* Cell Styles */
.code-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary, #666);
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
}

.metric-name-cell {
  display: flex;
  flex-direction: column;
  gap: 1px;
  max-width: 260px;
  cursor: default;
}

.name-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.name-en {
  font-size: 11px;
  color: var(--text-muted, #999);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.domain-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary, #666);
}

.type-label {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  background: #f0f0f0;
  color: var(--text-secondary, #666);
  transition: transform 0.15s ease;
}

.type-label:hover {
  transform: scale(1.05);
}

.type-label.atomic {
  background: rgba(22, 119, 255, 0.1);
  color: #1677FF;
}

.type-label.derived {
  background: #fef3c7;
  color: #d97706;
}

.type-label.composite {
  background: #fce7f3;
  color: #db2777;
}

.dept-text {
  font-size: 12px;
  color: var(--text-secondary, #666);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
  max-width: 140px;
}

.freq-text {
  font-size: 12px;
  color: var(--text-muted, #999);
}

.status-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 500;
  transition: transform 0.15s ease;
}

.status-label:hover {
  transform: scale(1.05);
}

.status-label.active {
  color: #22C55E;
}

.status-label.inactive {
  color: #94A3B8;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.status-label.active .status-dot {
  background: #22C55E;
}

.status-label.inactive .status-dot {
  background: #94A3B8;
}

/* Action Buttons */
.action-group {
  display: flex;
  gap: 4px;
  justify-content: center;
  opacity: 0.5;
  transition: opacity 0.2s ease;
}

.metrics-table :deep(.el-table__row:hover .action-group) {
  opacity: 1;
}

.action-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  color: var(--text-secondary, #666);
  transition: all 0.15s ease;
}

.action-btn:hover {
  background: var(--bg-primary, #f8f9fa);
}

.action-btn.view:hover {
  color: var(--primary, #6366F1);
  background: #eff6ff;
}

.action-btn.edit:hover {
  color: #52c41a;
  background: #f6ffed;
}

.action-btn.delete:hover {
  color: #ff4d4f;
  background: #fff1f0;
}

/* Pagination */
.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 16px;
  padding: 14px 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.04);
}

.dark-mode .pagination-wrap {
  border-top-color: rgba(255, 255, 255, 0.06);
}

:deep(.el-pagination.is-background .el-pager li:not(.is-disabled).is-active) {
  background: var(--primary, #0891B2);
}

/* Buttons */
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--primary, #0891B2);
  color: #ffffff;
  border: none;
  border-radius: 12px;
  font-weight: 600;
  font-size: 14px;
  padding: 10px 20px;
  transition: all 0.25s ease;
  box-shadow: var(--shadow-card);
}

.btn-primary:hover {
  background: var(--primary-dark);
  transform: translateY(-2px) scale(1.01);
  box-shadow: var(--shadow-card-hover);
}

.btn-search {
  background: var(--primary, #0891B2);
  color: #ffffff;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 13px;
  padding: 0 18px;
  height: 40px;
}

.btn-search:hover {
  background: var(--primary-dark);
}

/* Dialog */
.metric-dialog :deep(.el-dialog) {
  border-radius: 12px;
  overflow: hidden;
}

.metric-dialog :deep(.el-dialog__header) {
  padding: 0;
  margin: 0;
  background: #ffffff;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.dark-mode .metric-dialog :deep(.el-dialog__header) {
  background: rgba(35, 35, 35, 0.95);
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
}

.dialog-title-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dialog-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary, #1a1a1a);
}

.dialog-code {
  font-size: 12px;
  color: var(--text-muted, #999);
  background: var(--bg-primary, #f8f9fa);
  padding: 3px 10px;
  border-radius: 4px;
  font-family: 'SF Mono', Monaco, monospace;
}

.dialog-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.dialog-status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
}

.dialog-status.active {
  background: rgba(34, 197, 94, 0.1);
  color: #22C55E;
}

.dialog-status.active .dialog-status-dot {
  background: #22C55E;
}

.dialog-status.inactive {
  background: #f5f5f5;
  color: #94A3B8;
}

.dialog-status.inactive .dialog-status-dot {
  background: #94A3B8;
}

.metric-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.dialog-content {
  max-height: 55vh;
  overflow-y: auto;
}

/* Tabs */
.metric-tabs :deep(.el-tabs__header) {
  margin: 0;
  padding: 0 24px;
  background: var(--bg-primary, #f8f9fa);
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

.dark-mode .metric-tabs :deep(.el-tabs__header) {
  background: rgba(45, 45, 45, 0.5);
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

.metric-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.metric-tabs :deep(.el-tabs__item) {
  padding: 14px 16px;
  font-weight: 500;
  color: var(--text-secondary, #666);
  height: auto;
  line-height: 1.5;
  font-size: 13px;
}

.metric-tabs :deep(.el-tabs__item.is-active) {
  color: var(--primary, #0891B2);
  font-weight: 600;
}

.metric-tabs :deep(.el-tabs__active-bar) {
  height: 2px;
  background: var(--primary, #0891B2);
}

.metric-tabs :deep(.el-tabs__content) {
  padding: 20px 24px;
}

/* Info Display */
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.info-item.full {
  grid-column: span 2;
}

.info-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted, #999);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 13px;
  color: var(--text-primary, #1a1a1a);
  font-weight: 500;
}

.info-value.code {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
}

.info-value.en {
  color: var(--text-secondary, #666);
  font-style: italic;
}

.info-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted, #999);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-content {
  font-size: 13px;
  color: var(--text-primary, #1a1a1a);
  line-height: 1.6;
  padding: 12px;
  background: var(--bg-primary, #f8f9fa);
  border-radius: 6px;
}

.dark-mode .section-content {
  background: rgba(50, 50, 50, 0.5);
}

.section-content.mono {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
}

.sql-mini {
  max-height: 90px;
  overflow: auto;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary, #666);
  transition: background-color 0.15s ease;
}

.sql-mini:hover {
  background: rgba(0, 0, 0, 0.04);
}

.sql-mini pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: 'SF Mono', Monaco, monospace;
}

.sql-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--primary, #6366F1);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 5px;
  font-size: 12px;
}

.sql-btn:hover {
  background: rgba(59, 130, 246, 0.05);
  border-color: var(--primary, #6366F1);
}

/* Form */
.metric-form {
  padding: 20px 24px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}

.form-item {
  margin-bottom: 0;
}

.form-row {
  display: flex;
  gap: 10px;
}

.form-item-inline {
  flex: 1;
  margin-bottom: 12px;
}

.metric-form :deep(.el-form-item__label) {
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  padding-bottom: 5px;
  font-size: 12px;
}

.metric-form :deep(.el-input__wrapper),
.metric-form :deep(.el-textarea__inner) {
  border-radius: 6px;
  box-shadow: none !important;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.metric-form :deep(.el-input__wrapper:hover),
.metric-form :deep(.el-input__wrapper.is-focus),
.metric-form :deep(.el-textarea__inner:hover),
.metric-form :deep(.el-textarea__inner:focus) {
  border-color: var(--primary, #0891B2);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 24px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.dark-mode .dialog-footer {
  border-top-color: rgba(255, 255, 255, 0.06);
}

/* SQL Dialog */
.sql-dialog :deep(.el-dialog__header) {
  padding: 18px 24px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.dark-mode .sql-dialog :deep(.el-dialog__header) {
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

.sql-dialog :deep(.el-dialog__title) {
  font-weight: 700;
  color: var(--text-primary, #1a1a1a);
}

.sql-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.sql-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary, #666);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.copy-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text-primary, #1a1a1a);
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 5px;
}

.copy-btn:hover {
  background: var(--bg-primary, #f8f9fa);
}

.sql-preview {
  background: #0f172a;
  color: #e2e8f0;
  padding: 18px;
  border-radius: 8px;
  font-family: 'SF Mono', Monaco, 'Ubuntu Mono', monospace;
  font-size: 12px;
  line-height: 1.7;
  max-height: 350px;
  overflow: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

/* Import Preview Dialog */
.import-preview {
  max-height: 70vh;
  overflow-y: auto;
}

.import-summary {
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  margin-bottom: 16px;
}

.dark-mode .import-summary {
  background: rgba(255, 255, 255, 0.05);
}

.summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px;
  border-radius: 8px;
  background: white;
}

.dark-mode .summary-item {
  background: rgba(255, 255, 255, 0.1);
}

.summary-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.dark-mode .summary-label {
  color: #999;
}

.summary-value {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a1a;
}

.dark-mode .summary-value {
  color: #fff;
}

.summary-item.new .summary-value {
  color: #67c23a;
}

.summary-item.update .summary-value {
  color: #409eff;
}

.summary-item.error .summary-value {
  color: #f56c6c;
}

.summary-value.success {
  color: #67c23a;
}

.import-errors {
  margin-bottom: 16px;
  padding: 12px;
  background: #fef0f0;
  border: 1px solid #fde2e2;
  border-radius: 8px;
}

.dark-mode .import-errors {
  background: rgba(245, 108, 108, 0.1);
  border-color: rgba(245, 108, 108, 0.3);
}

.error-title {
  font-size: 13px;
  font-weight: 600;
  color: #f56c6c;
  margin-bottom: 8px;
}

.error-list {
  max-height: 120px;
  overflow-y: auto;
}

.error-item {
  display: flex;
  gap: 8px;
  font-size: 12px;
  padding: 4px 0;
  border-bottom: 1px solid rgba(245, 108, 108, 0.2);
}

.error-item:last-child {
  border-bottom: none;
}

.error-row {
  color: #f56c6c;
  font-weight: 600;
  min-width: 60px;
}

.error-field {
  color: #666;
  min-width: 80px;
}

.error-msg {
  color: #1a1a1a;
}

.dark-mode .error-msg {
  color: #fff;
}

.import-table-wrap {
  margin-top: 12px;
}

.preview-title {
  font-size: 13px;
  font-weight: 600;
  color: #666;
  margin-bottom: 8px;
}

.status-new {
  color: #67c23a;
  font-weight: 600;
}

.status-update {
  color: #409eff;
  font-weight: 600;
}

.import-dialog :deep(.el-dialog__body) {
  padding-top: 12px;
}

.import-dialog .dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
