<template>
  <div class="nlp-config-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <div class="page-icon">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M4 6L11 4L18 6V16L11 18L4 16V6Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
            <path d="M8 11L10 13L14 9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="header-text">
          <h1>意图配置</h1>
          <p>管理意图识别和 SQL 模板</p>
        </div>
      </div>
    </div>

    <!-- Vector Management -->
    <div class="vector-bar">
      <div class="vector-info">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <circle cx="9" cy="9" r="7" stroke="currentColor" stroke-width="1.5"/>
          <circle cx="9" cy="9" r="3" fill="currentColor"/>
        </svg>
        <span>向量管理</span>
      </div>
      <div class="vector-actions">
        <el-button @click="rebuildIntentEmbeddings">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 7C2 4.2 4.2 2 7 2C9.8 2 12 4.2 12 7M12 7C12 9.8 9.8 12 7 12C4.2 12 2 9.8 2 7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
            <path d="M10 5L12 7L10 9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          重新生成意图向量
        </el-button>
        <el-button @click="rebuildMetricEmbeddings">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 7C2 4.2 4.2 2 7 2C9.8 2 12 4.2 12 7M12 7C12 9.8 9.8 12 7 12C4.2 12 2 9.8 2 7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
            <path d="M10 5L12 7L10 9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          重新生成指标向量
        </el-button>
      </div>
    </div>

    <!-- Tabs -->
    <div class="config-tabs-wrapper">
      <el-tabs v-model="activeTab" class="config-tabs">
        <!-- 意图模板 -->
        <el-tab-pane label="意图模板" name="intents">
          <div class="section">
            <div class="section-header">
              <h2 class="section-title">意图模板管理</h2>
              <el-button type="primary" class="btn-primary" @click="showIntentDialog('create')">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                添加模板
              </el-button>
            </div>
            <div class="table-card">
              <table class="config-table">
                <thead>
                  <tr>
                    <th>模板名称</th>
                    <th>意图类型</th>
                    <th>匹配模式</th>
                    <th>优先级</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="tpl in paginatedIntents" :key="tpl.id">
                    <td class="name-cell">{{ tpl.name }}</td>
                    <td><span class="intent-badge">{{ tpl.intent }}</span></td>
                    <td class="patterns-cell">{{ tpl.patterns }}</td>
                    <td class="priority-cell">{{ tpl.priority }}</td>
                    <td>
                      <el-switch
                        v-model="tpl.status"
                        :active-value="1"
                        :inactive-value="0"
                        @change="updateIntentStatus(tpl)"
                      />
                    </td>
                    <td>
                      <div class="action-group">
                        <el-button link class="action-btn" @click="showIntentDialog('edit', tpl)">编辑</el-button>
                        <el-button link class="action-btn delete" @click="deleteIntent(tpl.id)">删除</el-button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div class="table-pagination" v-if="intentTemplates.length > 0">
                <el-pagination
                  v-model:current-page="intentPage.current"
                  :page-size="intentPage.size"
                  :total="intentTemplates.length"
                  layout="prev, pager, next"
                  background
                />
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- SQL 模板 -->
        <el-tab-pane label="SQL 模板" name="sql">
          <div class="section">
            <div class="section-header">
              <h2 class="section-title">SQL 模板管理</h2>
              <el-button type="primary" class="btn-primary" @click="showSQLDialog('create')">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                添加模板
              </el-button>
            </div>
            <div class="table-card">
              <table class="config-table">
                <thead>
                  <tr>
                    <th>模板名称</th>
                    <th>指标编号</th>
                    <th>适意图图</th>
                    <th>SQL 模板</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="tpl in paginatedSqlTemplates" :key="tpl.id">
                    <td class="name-cell">{{ tpl.name }}</td>
                    <td><code class="metric-code">{{ tpl.metric_code }}</code></td>
                    <td><span class="intent-badge">{{ tpl.intent }}</span></td>
                    <td class="sql-cell">{{ tpl.sql_template }}</td>
                    <td>
                      <el-switch
                        v-model="tpl.status"
                        :active-value="1"
                        :inactive-value="0"
                        @change="updateSQLStatus(tpl)"
                      />
                    </td>
                    <td>
                      <div class="action-group">
                        <el-button link class="action-btn" @click="showSQLDialog('edit', tpl)">编辑</el-button>
                        <el-button link class="action-btn delete" @click="deleteSQL(tpl.id)">删除</el-button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div class="table-pagination" v-if="sqlTemplates.length > 0">
                <el-pagination
                  v-model:current-page="sqlPage.current"
                  :page-size="sqlPage.size"
                  :total="sqlTemplates.length"
                  layout="prev, pager, next"
                  background
                />
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 公式语法配置 -->
        <el-tab-pane label="公式语法" name="formula">
          <div class="section">
            <div class="section-header">
              <h2 class="section-title">公式语法配置</h2>
              <div class="header-right">
                <el-input
                  v-model="formulaSearch"
                  placeholder="搜索规则名称、关键词..."
                  prefix-icon="Search"
                  clearable
                  class="search-input"
                />
                <el-button type="primary" class="btn-primary" @click="showFormulaDialog('create')">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                  添加配置
                </el-button>
              </div>
            </div>
            <div class="table-card">
              <table class="config-table">
                <thead>
                  <tr>
                    <th>规则名称</th>
                    <th>分类</th>
                    <th>意图类型</th>
                    <th>触发关键词</th>
                    <th>SQL 片段模板</th>
                    <th>优先级</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="cfg in paginatedFormulaConfigs" :key="cfg.id">
                    <td class="name-cell">{{ cfg.name }}</td>
                    <td><span class="category-badge">{{ cfg.category }}</span></td>
                    <td><span class="intent-badge">{{ cfg.intent_type }}</span></td>
                    <td class="patterns-cell">{{ cfg.keywords }}</td>
                    <td class="sql-cell">{{ cfg.sql_pattern }}</td>
                    <td class="priority-cell">{{ cfg.priority }}</td>
                    <td>
                      <el-switch
                        v-model="cfg.status"
                        :active-value="1"
                        :inactive-value="0"
                        @change="updateFormulaStatus(cfg)"
                      />
                    </td>
                    <td>
                      <div class="action-group">
                        <el-button link class="action-btn" @click="showFormulaDialog('edit', cfg)">编辑</el-button>
                        <el-button link class="action-btn delete" @click="deleteFormula(cfg.id)">删除</el-button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div class="table-pagination" v-if="filteredFormulaConfigs.length > 0">
                <el-pagination
                  v-model:current-page="formulaPage.current"
                  :page-size="formulaPage.size"
                  :total="filteredFormulaConfigs.length"
                  layout="prev, pager, next"
                  small
                />
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 槽位配置 -->
        <el-tab-pane label="槽位配置" name="slots">
          <div class="section">
            <div class="section-header">
              <h2 class="section-title">槽位定义管理</h2>
              <el-button type="primary" class="btn-primary" @click="showSlotDialog('create')">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                添加槽位
              </el-button>
            </div>
            <div class="table-card">
              <table class="config-table">
                <thead>
                  <tr>
                    <th>槽位名称</th>
                    <th>显示名称</th>
                    <th>类型</th>
                    <th>值类型</th>
                    <th>优先级</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="slot in slotDefinitions" :key="slot.id">
                    <td class="name-cell">{{ slot.slot_name }}</td>
                    <td>{{ slot.display_name }}</td>
                    <td><span class="intent-badge">{{ getSlotTypeText(slot.slot_type) }}</span></td>
                    <td>{{ getValueTypeText(slot.value_type) }}</td>
                    <td class="priority-cell">{{ slot.priority }}</td>
                    <td>
                      <el-switch
                        v-model="slot.status"
                        :active-value="1"
                        :inactive-value="0"
                        @change="saveSlotStatus(slot)"
                      />
                    </td>
                    <td>
                      <div class="action-group">
                        <el-button link class="action-btn" @click="showSlotDialog('edit', slot)">编辑</el-button>
                        <el-button link class="action-btn delete" @click="deleteSlot(slot.id)">删除</el-button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div v-if="slotDefinitions.length === 0" class="empty-state">
                <span>暂无槽位配置</span>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 业务术语 -->
        <el-tab-pane label="业务术语" name="terms">
          <div class="section">
            <div class="section-header">
              <h2 class="section-title">业务术语映射</h2>
              <div class="header-right">
                <el-input
                  v-model="termSearch"
                  placeholder="搜索术语、同义词..."
                  prefix-icon="Search"
                  clearable
                  class="search-input"
                />
                <el-button type="primary" class="btn-primary" @click="showTermDialog('create')">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                  添加映射
                </el-button>
              </div>
            </div>
            <div class="table-card">
              <table class="config-table">
                <thead>
                  <tr>
                    <th>术语</th>
                    <th>同义词</th>
                    <th>维度字段</th>
                    <th>维度值</th>
                    <th>关联指标</th>
                    <th>描述</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="term in paginatedBusinessTerms" :key="term.id">
                    <td class="name-cell">{{ term.term }}</td>
                    <td>
                      <div class="synonym-tags">
                        <el-tag
                          v-for="(syn, idx) in (term.synonyms || [])"
                          :key="syn"
                          size="small"
                          type="info"
                          closable
                          @close="removeSynonym(term.id, idx)"
                          style="margin: 2px"
                        >
                          {{ syn }}
                        </el-tag>
                        <span v-if="!term.synonyms || term.synonyms.length === 0" class="no-synonym">暂无</span>
                      </div>
                    </td>
                    <td><code>{{ term.dimension_field || '-' }}</code></td>
                    <td><code>{{ term.dimension_value || '-' }}</code></td>
                    <td>
                      <span v-if="term.metric_ids && term.metric_ids.length > 0" class="metric-ids">
                        {{ term.metric_ids.length }}个
                      </span>
                      <span v-else class="no-synonym">-</span>
                    </td>
                    <td class="desc-cell">{{ term.description || '-' }}</td>
                    <td>
                      <div class="action-group">
                        <el-button link class="action-btn" @click="showTermDialog('edit', term)">编辑</el-button>
                        <el-button link class="action-btn delete" @click="deleteTerm(term.id)">删除</el-button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div class="table-pagination" v-if="filteredBusinessTerms.length > 0">
                <el-pagination
                  v-model:current-page="termPage.current"
                  :page-size="termPage.size"
                  :total="filteredBusinessTerms.length"
                  layout="prev, pager, next"
                  small
                />
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- Prompt 配置 -->
        <el-tab-pane label="Prompt 配置" name="prompts">
          <div class="section">
            <div class="section-header">
              <div class="header-left">
                <h2 class="section-title">Prompt 模板管理</h2>
                <span class="data-count">{{ filteredPromptConfigs.length }} 条</span>
              </div>
              <div class="header-right">
                <el-input
                  v-model="promptSearch"
                  placeholder="搜索名称、描述..."
                  prefix-icon="Search"
                  clearable
                  class="search-input"
                  style="width: 180px"
                />
                <el-select v-model="promptCategoryFilter" placeholder="全部分类" clearable style="width: 140px">
                  <el-option label="全部" value="" />
                  <el-option label="nl2structure" value="nl2structure" />
                  <el-option label="sql_generation" value="sql_generation" />
                  <el-option label="general" value="general" />
                  <el-option label="decision_analysis" value="decision_analysis" />
                </el-select>
                <el-select v-model="promptStatusFilter" placeholder="全部状态" clearable style="width: 110px">
                  <el-option label="全部" value="" />
                  <el-option label="启用" :value="1" />
                  <el-option label="停用" :value="0" />
                </el-select>
                <el-button type="primary" class="btn-primary" @click="showPromptDialog('create')">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M7 3V11M3 7H11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                  新增
                </el-button>
                <el-button @click="loadPrompts" :loading="promptLoading" class="btn-refresh">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M2 7C2 4.2 4.2 2 7 2C9.8 2 12 4.2 12 7M12 7C12 9.8 9.8 12 7 12C4.2 12 2 9.8 2 7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                    <path d="M10 5L12 7L10 9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  刷新
                </el-button>
              </div>
            </div>
            <div class="table-card">
              <table class="config-table prompt-config-table" v-if="filteredPromptConfigs.length > 0">
                <thead>
                  <tr>
                    <th class="col-name">名称</th>
                    <th class="col-category">分类</th>
                    <th class="col-desc">描述</th>
                    <th class="col-preview">内容预览</th>
                    <th class="col-vars">变量</th>
                    <th class="col-chars">字符</th>
                    <th class="col-version">版本</th>
                    <th class="col-status">状态</th>
                    <th class="col-actions">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="cfg in paginatedPromptConfigs" :key="cfg.id">
                    <td class="name-cell">
                      <span class="prompt-name">{{ cfg.name }}</span>
                    </td>
                    <td><span class="category-badge">{{ cfg.category }}</span></td>
                    <td class="desc-cell" :title="cfg.description">{{ cfg.description || '-' }}</td>
                    <td class="preview-cell" :title="cfg.prompt_text">{{ truncatePrompt(cfg.prompt_text) }}</td>
                    <td class="vars-cell">
                      <el-tag size="small" type="info">{{ getVarCount(cfg.variables) }}个</el-tag>
                    </td>
                    <td class="chars-cell">{{ formatChars(cfg.prompt_text) }}</td>
                    <td class="priority-cell">v{{ cfg.version }}</td>
                    <td>
                      <el-tag :type="cfg.status === 1 ? 'success' : 'info'" size="small">
                        {{ cfg.status === 1 ? '启用' : '停用' }}
                      </el-tag>
                    </td>
                    <td>
                      <div class="action-group">
                        <el-button link class="action-btn" @click="viewPromptDetail(cfg)">查看</el-button>
                        <el-button link class="action-btn" @click="editPrompt(cfg)">编辑</el-button>
                        <el-button link class="action-btn delete" @click="deletePrompt(cfg.id)">删除</el-button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div class="table-pagination" v-if="filteredPromptConfigs.length > 0">
                <el-pagination
                  v-model:current-page="promptPage.current"
                  :page-size="promptPage.size"
                  :total="filteredPromptConfigs.length"
                  layout="prev, pager, next"
                  small
                />
              </div>
              <div v-else-if="promptConfigs.length > 0" class="empty-state">
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                  <circle cx="24" cy="24" r="20" stroke="currentColor" stroke-width="2"/>
                  <path d="M16 24L22 30L32 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <p>无匹配结果</p>
                <el-button link @click="clearPromptFilters" class="clear-filter-btn">清除筛选</el-button>
              </div>
              <div v-else class="empty-state">
                <p>暂无 Prompt 配置</p>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 意图反馈审核 -->
        <el-tab-pane label="意图反馈" name="feedback">
          <div class="section">
            <div class="section-header">
              <h2 class="section-title">意图反馈审核</h2>
              <el-button @click="loadFeedback" :loading="feedbackLoading" class="btn-refresh">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M2 7C2 4.2 4.2 2 7 2C9.8 2 12 4.2 12 7M12 7C12 9.8 9.8 12 7 12C4.2 12 2 9.8 2 7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                  <path d="M10 5L12 7L10 9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                刷新
              </el-button>
            </div>
            <div class="table-card">
              <table class="config-table" v-if="intentFeedbacks.length > 0">
                <thead>
                  <tr>
                    <th>用户输入</th>
                    <th>预测意图</th>
                    <th>正确意图</th>
                    <th>会话ID</th>
                    <th>时间</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="fb in paginatedFeedbacks" :key="fb.id">
                    <td class="name-cell">{{ fb.user_input }}</td>
                    <td><span class="intent-badge error">{{ fb.predicted_intent }}</span></td>
                    <td><span class="intent-badge success">{{ fb.correct_intent }}</span></td>
                    <td class="mono-cell">{{ fb.session_id?.substring(0, 8) }}...</td>
                    <td class="time-cell">{{ formatTime(fb.created_at) }}</td>
                    <td>
                      <el-tag v-if="fb.status === 0" type="warning" size="small">待审核</el-tag>
                      <el-tag v-else-if="fb.status === 1" type="success" size="small">已通过</el-tag>
                      <el-tag v-else type="info" size="small">已拒绝</el-tag>
                    </td>
                    <td>
                      <div class="action-group" v-if="fb.status === 0">
                        <el-button link class="action-btn approve" @click="reviewFeedback(fb, 1)">通过</el-button>
                        <el-button link class="action-btn delete" @click="reviewFeedback(fb, 2)">拒绝</el-button>
                      </div>
                      <span v-else class="reviewed-label">已处理</span>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div class="table-pagination" v-if="intentFeedbacks.length > 0">
                <el-pagination
                  v-model:current-page="feedbackPage.current"
                  :page-size="feedbackPage.size"
                  :total="intentFeedbacks.length"
                  layout="prev, pager, next"
                  small
                />
              </div>
              <div v-else class="empty-state">
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                  <circle cx="24" cy="24" r="20" stroke="currentColor" stroke-width="2"/>
                  <path d="M16 24L22 30L32 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <p>暂无待审核的意图反馈</p>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- Intent Dialog -->
    <el-dialog v-model="intentDialogVisible" :title="intentDialogTitle" width="550px" class="config-dialog">
      <el-form :model="intentForm" label-width="90px" class="config-form">
        <el-form-item label="模板名称">
          <el-input v-model="intentForm.name" placeholder="如：查询昨日数据" />
        </el-form-item>
        <el-form-item label="意图类型">
          <el-select v-model="intentForm.intent" placeholder="选择意图" style="width: 100%">
            <el-option label="查数值" value="query_value" />
            <el-option label="查趋势" value="query_trend" />
            <el-option label="对比分析" value="query_comparison" />
            <el-option label="查元数据" value="query_metadata" />
            <el-option label="打招呼" value="greeting" />
          </el-select>
        </el-form-item>
        <el-form-item label="匹配模式">
          <el-input
            v-model="intentForm.patterns"
            type="textarea"
            :rows="2"
            placeholder="关键词用逗号分隔，如：昨天,昨日,昨天数据"
          />
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="intentForm.priority" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="默认回复">
          <el-input v-model="intentForm.response" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="Few-Shot 示例">
          <el-input
            v-model="intentForm.few_shot_examples"
            type="textarea"
            :rows="3"
            placeholder='JSON 格式示例，如：[{"input": "昨天数据", "output": "intent: query_value"}]'
          />
          <div class="form-tip">JSON 格式，用于 few-shot learning 示例</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="large" @click="intentDialogVisible = false">取消</el-button>
        <el-button type="primary" size="large" @click="saveIntent" class="btn-primary">保存</el-button>
      </template>
    </el-dialog>

    <!-- SQL Dialog -->
    <el-dialog v-model="sqlDialogVisible" :title="sqlDialogTitle" width="650px" class="config-dialog">
      <el-form :model="sqlForm" label-width="90px" class="config-form">
        <el-form-item label="模板名称">
          <el-input v-model="sqlForm.name" placeholder="如：访客数昨日查询" />
        </el-form-item>
        <el-form-item label="指标编号">
          <el-select v-model="sqlForm.metric_code" placeholder="选择指标" filterable style="width: 100%">
            <el-option
              v-for="m in metricsList"
              :key="m.metric_code"
              :label="`${m.name} (${m.metric_code})`"
              :value="m.metric_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="适用意图">
          <el-select v-model="sqlForm.intent" placeholder="选择意图" style="width: 100%">
            <el-option label="查数值" value="query_value" />
            <el-option label="查趋势" value="query_trend" />
            <el-option label="对比分析" value="query_comparison" />
          </el-select>
        </el-form-item>
        <el-form-item label="SQL 模板">
          <el-input
            v-model="sqlForm.sql_template"
            type="textarea"
            :rows="4"
            placeholder="SELECT * FROM metric_data WHERE metric_id = '{metric_id}' AND date = CURRENT_DATE - INTERVAL '1 day'"
          />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="sqlForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="large" @click="sqlDialogVisible = false">取消</el-button>
        <el-button type="primary" size="large" @click="saveSQL" class="btn-primary">保存</el-button>
      </template>
    </el-dialog>

    <!-- Formula Syntax Dialog -->
    <el-dialog v-model="formulaDialogVisible" :title="formulaDialogTitle" width="600px" class="config-dialog">
      <el-form :model="formulaForm" label-width="100px" class="config-form">
        <el-form-item label="规则名称">
          <el-input v-model="formulaForm.name" placeholder="如：排名前十" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="formulaForm.category" placeholder="选择分类" style="width: 100%">
            <el-option label="时间序列" value="时间序列" />
            <el-option label="排名分析" value="排名分析" />
            <el-option label="占比分析" value="占比分析" />
            <el-option label="留存分析" value="留存分析" />
            <el-option label="排序分析" value="排序分析" />
            <el-option label="移动窗口" value="移动窗口" />
            <el-option label="用户分群" value="用户分群" />
            <el-option label="地理分析" value="地理分析" />
            <el-option label="文本处理" value="文本处理" />
            <el-option label="数值计算" value="数值计算" />
            <el-option label="条件逻辑" value="条件逻辑" />
            <el-option label="业务指标" value="业务指标" />
            <el-option label="预算预测" value="预算预测" />
            <el-option label="高级分析" value="高级分析" />
          </el-select>
        </el-form-item>
        <el-form-item label="意图类型">
          <el-select v-model="formulaForm.intent_type" placeholder="选择意图" style="width: 100%">
            <el-option label="查数值" value="query_value" />
            <el-option label="查趋势" value="query_trend" />
            <el-option label="对比分析" value="query_comparison" />
            <el-option label="排名查询" value="query_ranking" />
          </el-select>
        </el-form-item>
        <el-form-item label="触发关键词">
          <el-input
            v-model="formulaForm.keywords"
            type="textarea"
            :rows="2"
            placeholder="关键词用逗号分隔，如：排名前,前几名,Top"
          />
        </el-form-item>
        <el-form-item label="SQL 片段模板">
          <el-input
            v-model="formulaForm.sql_pattern"
            type="textarea"
            :rows="3"
            placeholder="如：ORDER BY {metric} DESC LIMIT {n}"
          />
          <div class="form-tip">占位符：{metric}=指标列名，{n}=排名前N</div>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="formulaForm.priority" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="formulaForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="large" @click="formulaDialogVisible = false">取消</el-button>
        <el-button type="primary" size="large" @click="saveFormula" class="btn-primary">保存</el-button>
      </template>
    </el-dialog>

    <!-- Term Dialog -->
    <el-dialog v-model="termDialogVisible" :title="termDialogTitle" width="650px" class="config-dialog">
      <el-form :model="termForm" label-width="100px" class="config-form">
        <el-form-item label="术语">
          <el-input v-model="termForm.term" placeholder="如：amazon" />
        </el-form-item>
        <el-form-item label="同义词">
          <el-select
            v-model="termForm.synonyms"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入后按回车添加"
            style="width: 100%"
          >
            <el-option
              v-for="syn in termForm.synonyms"
              :key="syn"
              :label="syn"
              :value="syn"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关联指标">
          <el-select
            v-model="termForm.metric_ids"
            multiple
            placeholder="选择关联的指标（可选）"
            style="width: 100%"
            filterable
            clearable
          >
            <el-option
              v-for="m in metricsList"
              :key="m.id"
              :label="`${m.metric_code} - ${m.name}`"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="维度字段">
          <el-select
            v-model="termForm.dimension_field"
            placeholder="选择维度字段"
            filterable
            allow-create
            clearable
            style="width: 100%"
            @change="(val) => loadDimensionValues(val)"
          >
            <el-option
              v-for="f in dimensionFieldOptions"
              :key="f"
              :label="f"
              :value="f"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="维度值">
          <el-select
            v-model="termForm.dimension_value"
            placeholder="选择或输入维度值"
            filterable
            allow-create
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="v in dimensionValueOptions"
              :key="v"
              :label="v"
              :value="v"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="termForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="large" @click="termDialogVisible = false">取消</el-button>
        <el-button type="primary" size="large" @click="saveTerm" class="btn-primary">保存</el-button>
      </template>
    </el-dialog>

    <!-- Prompt 详情对话框 -->
    <el-dialog
      v-model="promptDialogVisible"
      :title="promptDialogTitle"
      :width="promptFullscreen ? '100vw' : '1200px'"
      :fullscreen="promptFullscreen"
      class="config-dialog prompt-detail-dialog"
    >
      <div v-if="promptDetail" class="prompt-detail">
        <!-- Meta 信息栏 -->
        <div class="prompt-meta-bar">
          <div class="meta-left">
            <span class="meta-item">
              <span class="meta-label">分类</span>
              <el-tag size="small" type="info">{{ promptDetail.category }}</el-tag>
            </span>
            <span class="meta-item">
              <span class="meta-label">版本</span>
              <span class="meta-value">v{{ promptDetail.version }}</span>
            </span>
            <span class="meta-item">
              <span class="meta-label">状态</span>
              <el-tag size="small" :type="promptDetail.status === 1 ? 'success' : 'info'">
                {{ promptDetail.status === 1 ? '启用' : '停用' }}
              </el-tag>
            </span>
          </div>
          <div class="meta-right">
            <span class="meta-item">
              <span class="meta-label">{{ promptDetail.prompt_text?.length || 0 }}</span>
              <span class="meta-unit">chars</span>
            </span>
            <el-button size="small" @click="viewPromptVersions(promptDetail)" class="history-btn">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="5.5" stroke="currentColor" stroke-width="1.2"/>
                <path d="M7 4.5V7L9 9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
              </svg>
              版本历史
            </el-button>
            <el-button size="small" @click="copyPromptContent" class="copy-btn">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <rect x="4" y="4" width="8" height="8" rx="1.5" stroke="currentColor" stroke-width="1.2"/>
                <path d="M2 10V2.5C2 2.22386 2.22386 2 2.5 2H10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
              </svg>
              复制
            </el-button>
            <div class="font-size-selector">
              <el-slider v-model="promptFontSize" :min="10" :max="20" :step="1" size="small" />
              <span class="font-size-label">{{ promptFontSize }}px</span>
            </div>
            <el-button size="small" @click="togglePromptFullscreen" class="fullscreen-btn">
              <svg v-if="!promptFullscreen" width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M2 5V2H5M9 2H12V5M12 9V12H9M5 12H2V9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <svg v-else width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M5 2V5H2M9 2H12V5M12 9V12H9M5 12H2V9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              {{ promptFullscreen ? '退出全屏' : '全屏' }}
            </el-button>
          </div>
        </div>

        <!-- 描述 -->
        <div class="prompt-desc-section" v-if="promptDetail.description">
          <div class="section-label">描述</div>
          <div class="section-content">{{ promptDetail.description }}</div>
        </div>

        <!-- 变量列表 -->
        <div class="prompt-vars-section" v-if="promptDetail.variables">
          <div class="section-label">变量</div>
          <div class="variable-tags">
            <el-tag
              v-for="v in parseVariables(promptDetail.variables)"
              :key="v"
              size="small"
              class="var-tag"
            >
              {{ v }}
            </el-tag>
          </div>
        </div>

        <!-- 内容区 -->
        <div class="prompt-content-section">
          <div class="section-label">内容</div>
          <div class="code-container">
            <div class="code-line-numbers">
              <div v-for="n in getLineNumbers(promptDetail.prompt_text)" :key="n" class="line-number">{{ n }}</div>
            </div>
            <pre class="code-content" :style="{ fontSize: promptFontSize + 'px' }" v-html="highlightVariables(promptDetail.prompt_text)"></pre>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- Prompt 编辑对话框 -->
    <el-dialog v-model="promptEditDialogVisible" :title="promptDialogTitle" width="100vw" class="config-dialog prompt-edit-dialog" fullscreen>
      <div class="prompt-edit-body">
        <div class="edit-top-row">
          <el-form-item label="名称" class="form-item-inline">
            <el-input v-model="promptEditForm.name" :disabled="!!promptEditForm.id" placeholder="输入 Prompt 名称" />
          </el-form-item>
          <el-form-item label="分类" class="form-item-inline">
            <el-select v-model="promptEditForm.category" :disabled="!!promptEditForm.id">
              <el-option label="nl2structure" value="nl2structure" />
              <el-option label="sql_generation" value="sql_generation" />
              <el-option label="general" value="general" />
              <el-option label="decision_analysis" value="decision_analysis" />
            </el-select>
          </el-form-item>
          <el-form-item label="描述" class="form-item-inline form-item-desc">
            <el-input v-model="promptEditForm.description" placeholder="配置描述" />
          </el-form-item>
        </div>
        <!-- 左右对比布局 -->
        <div class="compare-container">
          <div class="compare-panel compare-current">
            <div class="panel-header">
              <span class="panel-title">待编辑</span>
              <span class="panel-badge" v-if="promptEditForm.id">v{{ promptDetail?.version }}</span>
            </div>
            <textarea
              ref="compareCurrentTextareaRef"
              v-model="promptEditForm.prompt_text"
              class="compare-textarea"
              placeholder="输入 Prompt 内容..."
              @scroll="onCompareCurrentScroll"
            ></textarea>
          </div>
          <div class="compare-divider"></div>
          <div class="compare-panel compare-prev">
            <div class="panel-header">
              <span class="panel-title">当前版本</span>
              <span class="panel-badge" v-if="promptEditForm.id">v{{ promptDetail?.version }}</span>
            </div>
            <div
              ref="comparePrevContentRef"
              class="prev-content"
              @scroll="onComparePrevScroll"
            >{{ promptPrevText || '暂无上一版本' }}</div>
          </div>
        </div>
        <div class="edit-bottom-row">
          <div class="edit-vars">
            <label class="bottom-label">变量</label>
            <el-input
              v-model="promptEditForm.variables_text"
              type="textarea"
              :rows="1"
              placeholder='JSON 格式，如：{"indicators": [...]}'
              class="vars-input"
            />
            <span class="form-tip">decision_analysis 模板需要此字段配置指标</span>
          </div>
          <div class="edit-actions">
            <el-button size="large" @click="promptEditDialogVisible = false">取消</el-button>
            <el-button type="primary" size="large" @click="savePrompt" class="btn-primary">保存</el-button>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- Prompt 版本历史对话框 -->
    <el-dialog v-model="promptVersionDialogVisible" title="版本历史" width="850px" class="config-dialog">
      <div v-if="promptVersions.length > 0" class="version-list">
        <div v-for="v in promptVersions" :key="v.id" class="version-item">
          <div class="version-header">
            <div class="version-info">
              <span class="version-badge">v{{ v.version }}</span>
              <span class="version-meta">
                {{ v.created_by || 'admin' }} · {{ formatTime(v.created_at) }}
              </span>
              <el-tag v-if="v.version === promptDetail?.version" size="small" type="success">当前版本</el-tag>
            </div>
            <div class="version-actions">
              <el-button
                v-if="v.version !== promptDetail?.version"
                link
                class="action-btn"
                @click="rollbackPromptVersion(promptDetail.id, v.version)"
              >
                回滚此版本
              </el-button>
            </div>
          </div>
          <div class="version-content">
            <pre class="version-text">{{ v.prompt_text }}</pre>
          </div>
          <div v-if="v.change_reason" class="version-reason">
            <span class="reason-label">变更原因：</span>{{ v.change_reason }}
          </div>
        </div>
      </div>
      <div v-else-if="promptVersionLoading" class="version-loading">
        <el-icon class="is-loading" style="font-size: 24px"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
      <div v-else class="version-empty">
        <p>暂无版本历史</p>
      </div>
    </el-dialog>

    <!-- 槽位编辑对话框 -->
    <el-dialog v-model="slotDialogVisible" :title="slotDialogTitle" width="700px" class="config-dialog">
      <el-form :model="slotEditForm" label-width="100px" class="config-form">
        <el-form-item label="槽位名称" required>
          <el-input v-model="slotEditForm.slot_name" :disabled="!!slotEditForm.id" placeholder="如：metric, time_range" />
        </el-form-item>
        <el-form-item label="显示名称" required>
          <el-input v-model="slotEditForm.display_name" placeholder="如：指标、时间范围" />
        </el-form-item>
        <el-form-item label="槽位类型" required>
          <el-select v-model="slotEditForm.slot_type" style="width: 100%">
            <el-option label="必选" value="required" />
            <el-option label="可选" value="optional" />
            <el-option label="条件" value="conditional" />
          </el-select>
        </el-form-item>
        <el-form-item label="值类型" required>
          <el-select v-model="slotEditForm.value_type" style="width: 100%">
            <el-option label="静态枚举" value="static" />
            <el-option label="动态数据" value="dynamic" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="slotEditForm.priority" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="最大追问轮次">
          <el-input-number v-model="slotEditForm.max_clarify_turns" :min="1" :max="10" />
        </el-form-item>
        <el-form-item label="默认值">
          <el-input v-model="slotEditForm.default_value" placeholder="可选的默认值" />
        </el-form-item>
        <el-form-item label="可选值" v-if="slotEditForm.value_type === 'static'">
          <el-input v-model="slotEditForm.allowed_values" type="textarea" :rows="3" placeholder='JSON数组，如：["亚马逊","TikTok","Temu"]' />
        </el-form-item>
        <el-form-item label="动态数据源" v-if="slotEditForm.value_type === 'dynamic'">
          <el-select v-model="slotEditForm.dynamic_source" style="width: 100%">
            <el-option label="维度配置" value="dimension_config" />
            <el-option label="指标分类" value="metric_category" />
          </el-select>
        </el-form-item>
        <el-form-item label="维度名称" v-if="slotEditForm.value_type === 'dynamic'">
          <el-input v-model="slotEditForm.dimension_name" placeholder="如：平台、站点" />
        </el-form-item>
        <el-form-item label="追问话术" required>
          <el-input v-model="slotEditForm.question_templates" type="textarea" :rows="2" placeholder='JSON数组，如：["请问想查询哪个平台？","是亚马逊还是TikTok呢？"]' />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch
            v-model="slotEditForm.status"
            :active-value="1"
            :inactive-value="0"
            active-text="启用"
            inactive-text="停用"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="large" @click="slotDialogVisible = false">取消</el-button>
        <el-button type="primary" size="large" @click="saveSlot" class="btn-primary">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox, ElIcon } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { metricAPI, slotConfigAPI } from '../api'

const activeTab = ref('intents')
const intentTemplates = ref([])
const sqlTemplates = ref([])
const businessTerms = ref([])
const metricsList = ref([])
const intentFeedbacks = ref([])
const feedbackLoading = ref(false)

// 槽位配置
const slotDefinitions = ref([])
const slotLoading = ref(false)
const slotDialogVisible = ref(false)
const slotDialogTitle = ref('添加槽位')
const slotEditForm = ref({
  id: null,
  slot_name: '',
  display_name: '',
  slot_type: 'required',
  priority: 0,
  max_clarify_turns: 3,
  default_value: '',
  value_type: 'static',
  allowed_values: '',
  question_templates: '',
  dynamic_source: '',
  dimension_name: '',
  column_name: '',
  status: 1
})

// 分页状态
const intentPage = ref({ current: 1, size: 10, total: 0 })
const sqlPage = ref({ current: 1, size: 10, total: 0 })
const formulaPage = ref({ current: 1, size: 10, total: 0 })
const termPage = ref({ current: 1, size: 10, total: 0 })
const feedbackPage = ref({ current: 1, size: 10, total: 0 })
const promptPage = ref({ current: 1, size: 10, total: 0 })

// Prompt 配置
const promptConfigs = ref([])
const promptLoading = ref(false)
const promptDialogVisible = ref(false)
const promptDialogTitle = ref('Prompt 详情')
const promptDetail = ref(null)
const promptFullscreen = ref(false)
const promptFontSize = ref(13)
const promptSearch = ref('')
const promptCategoryFilter = ref('')
const promptStatusFilter = ref('')

const filteredPromptConfigs = computed(() => {
  let list = promptConfigs.value
  // 名称/描述搜索
  if (promptSearch.value) {
    const q = promptSearch.value.toLowerCase()
    list = list.filter(cfg =>
      cfg.name?.toLowerCase().includes(q) ||
      cfg.description?.toLowerCase().includes(q)
    )
  }
  // 分类筛选
  if (promptCategoryFilter.value) {
    list = list.filter(cfg => cfg.category === promptCategoryFilter.value)
  }
  // 状态筛选
  if (promptStatusFilter.value !== '') {
    list = list.filter(cfg => cfg.status === promptStatusFilter.value)
  }
  return list
})

const paginatedPromptConfigs = computed(() => {
  const start = (promptPage.value.current - 1) * promptPage.value.size
  const end = start + promptPage.value.size
  return filteredPromptConfigs.value.slice(start, end)
})

// Prompt 编辑
const promptEditDialogVisible = ref(false)
const promptEditForm = ref({
  id: null,
  name: '',
  description: '',
  category: '',
  prompt_text: '',
  variables: [],
  variables_text: '',
  status: 1
})

// Prompt 版本历史
const promptVersionDialogVisible = ref(false)
const promptVersions = ref([])
const promptVersionLoading = ref(false)

// Prompt 上一版本内容
const promptPrevText = ref('')

// 左右对比滚动ref
const compareCurrentTextareaRef = ref(null)  // 原生textarea
const comparePrevContentRef = ref(null)      // 右边内容div
let isScrolling = false

function onCompareCurrentScroll(e) {
  if (isScrolling) return
  isScrolling = true
  // 同步右边面板
  if (comparePrevContentRef.value) {
    comparePrevContentRef.value.scrollTop = e.target.scrollTop
  }
  isScrolling = false
}

function onComparePrevScroll(e) {
  if (isScrolling) return
  isScrolling = true
  // 同步左边面板的滚动位置
  if (compareCurrentTextareaRef.value) {
    compareCurrentTextareaRef.value.scrollTop = e.target.scrollTop
  }
  isScrolling = false
}

// 公式语法搜索
const formulaSearch = ref('')
const filteredFormulaConfigs = computed(() => {
  if (!formulaSearch.value) return formulaConfigs.value
  const q = formulaSearch.value.toLowerCase()
  return formulaConfigs.value.filter(cfg =>
    cfg.name?.toLowerCase().includes(q) ||
    cfg.keywords?.toLowerCase().includes(q) ||
    cfg.category?.toLowerCase().includes(q)
  )
})

// 业务术语搜索
const termSearch = ref('')
const filteredBusinessTerms = computed(() => {
  if (!termSearch.value) return businessTerms.value
  const q = termSearch.value.toLowerCase()
  return businessTerms.value.filter(term =>
    term.term?.toLowerCase().includes(q) ||
    term.synonyms?.some(s => s.toLowerCase().includes(q)) ||
    term.dimension_field?.toLowerCase().includes(q) ||
    term.dimension_value?.toLowerCase().includes(q)
  )
})

// 分页数据
const paginatedIntents = computed(() => {
  const start = (intentPage.value.current - 1) * intentPage.value.size
  const end = start + intentPage.value.size
  return intentTemplates.value.slice(start, end)
})

const paginatedSqlTemplates = computed(() => {
  const start = (sqlPage.value.current - 1) * sqlPage.value.size
  const end = start + sqlPage.value.size
  return sqlTemplates.value.slice(start, end)
})

const paginatedFormulaConfigs = computed(() => {
  const start = (formulaPage.value.current - 1) * formulaPage.value.size
  const end = start + formulaPage.value.size
  return filteredFormulaConfigs.value.slice(start, end)
})

const paginatedBusinessTerms = computed(() => {
  const start = (termPage.value.current - 1) * termPage.value.size
  const end = start + termPage.value.size
  return filteredBusinessTerms.value.slice(start, end)
})

const paginatedFeedbacks = computed(() => {
  const start = (feedbackPage.value.current - 1) * feedbackPage.value.size
  const end = start + feedbackPage.value.size
  return intentFeedbacks.value.slice(start, end)
})

// Intent Dialog
const intentDialogVisible = ref(false)
const intentDialogTitle = ref('添加意图模板')
const intentForm = ref({
  name: '',
  intent: 'query_value',
  patterns: '',
  priority: 0,
  response: '',
  few_shot_examples: '',
  status: 1
})
const editingIntentId = ref(null)

// SQL Dialog
const sqlDialogVisible = ref(false)
const sqlDialogTitle = ref('添加 SQL 模板')
const sqlForm = ref({
  name: '',
  metric_code: '',
  intent: 'query_value',
  sql_template: '',
  description: '',
  status: 1
})
const editingSQLId = ref(null)

// Formula Dialog
const formulaDialogVisible = ref(false)
const formulaDialogTitle = ref('添加公式语法配置')
const formulaConfigs = ref([])
const formulaForm = ref({
  name: '',
  category: '业务指标',
  intent_type: 'query_value',
  keywords: '',
  sql_pattern: '',
  description: '',
  priority: 0,
  status: 1
})
const editingFormulaId = ref(null)

// Term Dialog
const termDialogVisible = ref(false)
const termDialogTitle = ref('添加术语映射')
const termForm = ref({
  term: '',
  synonyms: [],
  description: '',
  dimension_field: '',
  dimension_value: ''
})
const editingTermId = ref(null)
const dimensionFieldOptions = ref([])
const dimensionValueOptions = ref([])

async function loadDimensionFields() {
  try {
    const res = await fetch('/api/v1/dimension-type-mappings').then(r => r.json())
    const fields = [...new Set(res.data.map(m => m.dimension_type || m.dimension_field).filter(f => f))]
    dimensionFieldOptions.value = fields
  } catch (e) {
    console.error('加载维度字段失败:', e)
  }
}

function loadDimensionValues(dimField) {
  if (!dimField) {
    termForm.value.dimension_value = ''
    dimensionValueOptions.value = []
    return
  }
  const values = [...new Set(
    businessTerms.value
      .filter(t => t.dimension_field === dimField && t.dimension_value)
      .map(t => t.dimension_value)
  )]
  dimensionValueOptions.value = values
}

async function loadData() {
  try {
    const [intentsRes, sqlRes, termsRes, metricsRes, formulaRes, promptsRes] = await Promise.all([
      fetch('/api/v1/nlp/intents').then(r => r.json()),
      fetch('/api/v1/nlp/sql-templates').then(r => r.json()),
      fetch('/api/v1/metadata/terms').then(r => r.json()),
      metricAPI.list({ page: 1, page_size: 500 }),
      fetch('/api/v1/nlp/formula-syntax').then(r => r.json()),
      fetch('/api/v1/prompt-configs').then(r => r.json())
    ])

    intentTemplates.value = intentsRes.data || []
    sqlTemplates.value = sqlRes.data || []
    businessTerms.value = termsRes.data || []
    metricsList.value = metricsRes.data?.list || []
    formulaConfigs.value = formulaRes.data || []
    promptConfigs.value = promptsRes.data || []
  } catch (e) {
    console.error('加载数据失败:', e)
  }
  // 加载维度字段选项
  loadDimensionFields()
}

// Intent
function showIntentDialog(mode, tpl = null) {
  if (mode === 'create') {
    intentDialogTitle.value = '添加意图模板'
    intentForm.value = { name: '', intent: 'query_value', patterns: '', priority: 0, response: '', few_shot_examples: '', status: 1 }
    editingIntentId.value = null
  } else {
    intentDialogTitle.value = '编辑意图模板'
    intentForm.value = { ...tpl }
    editingIntentId.value = tpl.id
  }
  intentDialogVisible.value = true
}

async function saveIntent() {
  try {
    if (editingIntentId.value) {
      await fetch(`/api/v1/nlp/intents/${editingIntentId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(intentForm.value)
      })
      ElMessage.success('更新成功')
    } else {
      await fetch('/api/v1/nlp/intents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(intentForm.value)
      })
      ElMessage.success('创建成功')
    }
    intentDialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function updateIntentStatus(tpl) {
  try {
    await fetch(`/api/v1/nlp/intents/${tpl.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: tpl.status })
    })
    ElMessage.success('状态更新成功')
  } catch (e) {
    ElMessage.error('更新失败')
    loadData()
  }
}

async function deleteIntent(id) {
  await ElMessageBox.confirm('确定删除这个模板吗？', '提示', { type: 'warning' })
  try {
    await fetch(`/api/v1/nlp/intents/${id}`, { method: 'DELETE' })
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// SQL
function showSQLDialog(mode, tpl = null) {
  if (mode === 'create') {
    sqlDialogTitle.value = '添加 SQL 模板'
    sqlForm.value = { name: '', metric_code: '', intent: 'query_value', sql_template: '', description: '', status: 1 }
    editingSQLId.value = null
  } else {
    sqlDialogTitle.value = '编辑 SQL 模板'
    sqlForm.value = { ...tpl }
    editingSQLId.value = tpl.id
  }
  sqlDialogVisible.value = true
}

async function saveSQL() {
  try {
    if (editingSQLId.value) {
      await fetch(`/api/v1/nlp/sql-templates/${editingSQLId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(sqlForm.value)
      })
      ElMessage.success('更新成功')
    } else {
      await fetch('/api/v1/nlp/sql-templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(sqlForm.value)
      })
      ElMessage.success('创建成功')
    }
    sqlDialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function updateSQLStatus(tpl) {
  try {
    await fetch(`/api/v1/nlp/sql-templates/${tpl.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: tpl.status })
    })
    ElMessage.success('状态更新成功')
  } catch (e) {
    ElMessage.error('更新失败')
    loadData()
  }
}

async function deleteSQL(id) {
  await ElMessageBox.confirm('确定删除这个模板吗？', '提示', { type: 'warning' })
  try {
    await fetch(`/api/v1/nlp/sql-templates/${id}`, { method: 'DELETE' })
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// Formula Syntax
function showFormulaDialog(mode, cfg = null) {
  if (mode === 'create') {
    formulaDialogTitle.value = '添加公式语法配置'
    formulaForm.value = { name: '', category: '业务指标', intent_type: 'query_value', keywords: '', sql_pattern: '', description: '', priority: 0, status: 1 }
    editingFormulaId.value = null
  } else {
    formulaDialogTitle.value = '编辑公式语法配置'
    formulaForm.value = { ...cfg }
    editingFormulaId.value = cfg.id
  }
  formulaDialogVisible.value = true
}

async function saveFormula() {
  try {
    if (editingFormulaId.value) {
      await fetch(`/api/v1/nlp/formula-syntax/${editingFormulaId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formulaForm.value)
      })
      ElMessage.success('更新成功')
    } else {
      await fetch('/api/v1/nlp/formula-syntax', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formulaForm.value)
      })
      ElMessage.success('创建成功')
    }
    formulaDialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function updateFormulaStatus(cfg) {
  try {
    await fetch(`/api/v1/nlp/formula-syntax/${cfg.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: cfg.status })
    })
    ElMessage.success('状态更新成功')
  } catch (e) {
    ElMessage.error('更新失败')
    loadData()
  }
}

async function deleteFormula(id) {
  await ElMessageBox.confirm('确定删除这个配置吗？', '提示', { type: 'warning' })
  try {
    await fetch(`/api/v1/nlp/formula-syntax/${id}`, { method: 'DELETE' })
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// Term
function showTermDialog(mode, term = null) {
  if (mode === 'create') {
    termDialogTitle.value = '添加术语映射'
    termForm.value = { term: '', synonyms: [], metric_ids: [], dimension_field: '', dimension_value: '', description: '' }
    editingTermId.value = null
  } else {
    termDialogTitle.value = '编辑术语映射'
    termForm.value = {
      term: term.term,
      synonyms: term.synonyms || [],
      metric_ids: term.metric_ids || [],
      dimension_field: term.dimension_field || '',
      dimension_value: term.dimension_value || '',
      description: term.description
    }
    editingTermId.value = term.id
  }
  termDialogVisible.value = true
}

async function saveTerm() {
  try {
    if (editingTermId.value) {
      await fetch(`/api/v1/metadata/terms/${editingTermId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(termForm.value)
      })
      ElMessage.success('更新成功')
    } else {
      await fetch('/api/v1/metadata/terms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(termForm.value)
      })
      ElMessage.success('创建成功')
    }
    termDialogVisible.value = false
    loadData()
    // 热更新 AI 服务缓存
    try {
      await fetch('http://localhost:8081/api/v1/admin/reload-config', { method: 'POST' })
      ElMessage.success('AI 服务缓存已刷新')
    } catch (e) {
      console.warn('热更新失败:', e)
    }
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function removeSynonym(termId, synonymIndex) {
  const term = businessTerms.value.find(t => t.id === termId)
  if (!term) return
  const newSynonyms = [...(term.synonyms || [])]
  newSynonyms.splice(synonymIndex, 1)
  try {
    await fetch(`/api/v1/metadata/terms/${termId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...term, synonyms: newSynonyms })
    })
    ElMessage.success('同义词已删除')
    loadData()
    // 热更新 AI 服务缓存
    try {
      await fetch('http://localhost:8081/api/v1/admin/reload-config', { method: 'POST' })
    } catch (e) {
      console.warn('热更新失败:', e)
    }
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

async function deleteTerm(id) {
  await ElMessageBox.confirm('确定删除这个映射吗？', '提示', { type: 'warning' })
  try {
    await fetch(`/api/v1/metadata/terms/${id}`, { method: 'DELETE' })
    ElMessage.success('删除成功')
    loadData()
    // 热更新 AI 服务缓存
    try {
      await fetch('http://localhost:8081/api/v1/admin/reload-config', { method: 'POST' })
      ElMessage.success('AI 服务缓存已刷新')
    } catch (e) {
      console.warn('热更新失败:', e)
    }
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// Intent Feedback
async function loadFeedback() {
  feedbackLoading.value = true
  try {
    const res = await fetch('/api/v1/feedback/intent')
    const data = await res.json()
    intentFeedbacks.value = data.data || []
  } catch (e) {
    console.error('加载反馈失败:', e)
  } finally {
    feedbackLoading.value = false
  }
}

async function reviewFeedback(feedback, status) {
  try {
    await fetch(`/api/v1/feedback/intent/${feedback.id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    })
    ElMessage.success(status === 1 ? '已通过' : '已拒绝')
    loadFeedback()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

// Prompt 配置
async function loadPrompts() {
  promptLoading.value = true
  try {
    const res = await fetch('/api/v1/prompt-configs')
    const data = await res.json()
    promptConfigs.value = data.data || []
  } catch (e) {
    console.error('加载 Prompt 配置失败:', e)
  } finally {
    promptLoading.value = false
  }
}

function clearPromptFilters() {
  promptSearch.value = ''
  promptCategoryFilter.value = ''
  promptStatusFilter.value = ''
}

function viewPromptDetail(cfg) {
  promptDetail.value = cfg
  promptDialogTitle.value = `Prompt 详情 - ${cfg.name}`
  promptDialogVisible.value = true
}

// 槽位配置
async function loadSlotDefinitions() {
  slotLoading.value = true
  try {
    const res = await slotConfigAPI.list()
    slotDefinitions.value = res.data || []
  } catch (e) {
    console.error('加载槽位配置失败:', e)
  } finally {
    slotLoading.value = false
  }
}

function showSlotDialog(mode, slot = null) {
  if (mode === 'create') {
    slotEditForm.value = {
      id: null,
      slot_name: '',
      display_name: '',
      slot_type: 'required',
      priority: 0,
      max_clarify_turns: 3,
      default_value: '',
      value_type: 'static',
      allowed_values: '',
      question_templates: '',
      dynamic_source: '',
      dimension_name: '',
      column_name: '',
      status: 1
    }
    slotDialogTitle.value = '添加槽位'
  } else {
    slotEditForm.value = { ...slot }
    slotDialogTitle.value = '编辑槽位'
  }
  slotDialogVisible.value = true
}

async function saveSlot() {
  const form = slotEditForm.value
  try {
    if (form.id) {
      await slotConfigAPI.update(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await slotConfigAPI.create(form)
      ElMessage.success('创建成功')
    }
    slotDialogVisible.value = false
    loadSlotDefinitions()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function deleteSlot(id) {
  try {
    await ElMessageBox.confirm('确定要删除这个槽位吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await slotConfigAPI.delete(id)
    ElMessage.success('删除成功')
    loadSlotDefinitions()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

async function saveSlotStatus(slot) {
  try {
    await slotConfigAPI.update(slot.id, slot)
    ElMessage.success('状态更新成功')
  } catch (e) {
    ElMessage.error('状态更新失败')
  }
}

function getValueTypeText(vt) {
  const map = { 'static': '静态', 'dynamic': '动态', 'enum': '枚举', 'range': '范围', 'free_text': '自由文本' }
  return map[vt] || vt
}

function getSlotTypeText(st) {
  const map = { 'required': '必选', 'optional': '可选', 'conditional': '条件' }
  return map[st] || st
}

function showPromptDialog(mode, cfg = null) {
  promptDialogTitle.value = mode === 'create' ? '新增 Prompt' : '编辑 Prompt'
  promptPrevText.value = '' // 清空上一版本
  if (mode === 'create') {
    promptEditForm.value = {
      id: null,
      name: '',
      description: '',
      category: 'general',
      prompt_text: '',
      variables: [],
      variables_text: '',
      status: 1
    }
  } else {
    // 将 variables 对象转成可编辑的 JSON 字符串
    let variablesText = ''
    if (cfg.variables) {
      if (typeof cfg.variables === 'string') {
        variablesText = cfg.variables
      } else {
        variablesText = JSON.stringify(cfg.variables, null, 2)
      }
    }
    promptEditForm.value = {
      id: cfg.id,
      name: cfg.name,
      description: cfg.description || '',
      category: cfg.category,
      prompt_text: cfg.prompt_text || '',
      variables: cfg.variables || [],
      variables_text: variablesText,
      status: cfg.status
    }
  }
  promptEditDialogVisible.value = true
}

// 兼容旧的 editPrompt 调用
async function editPrompt(cfg) {
  promptDetail.value = cfg
  showPromptDialog('edit', cfg)
  // 获取上一版本内容
  if (cfg.version > 1) {
    try {
      const res = await fetch(`/api/v1/prompt-configs/${cfg.id}/versions`)
      const data = await res.json()
      const versions = data.data || []
      const prevVersion = versions.find(v => v.version === cfg.version - 1)
      if (prevVersion) {
        promptPrevText.value = prevVersion.prompt_text || ''
      } else {
        promptPrevText.value = ''
      }
    } catch (e) {
      console.error('获取上一版本失败:', e)
      promptPrevText.value = ''
    }
  } else {
    promptPrevText.value = ''
  }
}

async function deletePrompt(id) {
  await ElMessageBox.confirm('确定删除这个 Prompt 配置吗？删除后不可恢复。', '提示', { type: 'warning' })
  try {
    const res = await fetch(`/api/v1/prompt-configs/${id}`, { method: 'DELETE' })
    const data = await res.json()
    if (data.code === 0) {
      ElMessage.success('删除成功')
      loadPrompts()
    } else {
      ElMessage.error('删除失败: ' + (data.message || '未知错误'))
    }
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

async function savePrompt() {
  if (!promptEditForm.value.name.trim()) {
    ElMessage.warning('名称不能为空')
    return
  }
  if (!promptEditForm.value.prompt_text.trim()) {
    ElMessage.warning('Prompt 内容不能为空')
    return
  }
  try {
    // 验证 variables_text 是有效的 JSON（如果有内容）
    let variables = null
    if (promptEditForm.value.variables_text && promptEditForm.value.variables_text.trim()) {
      try {
        JSON.parse(promptEditForm.value.variables_text) // 验证 JSON 格式
        variables = promptEditForm.value.variables_text // 直接传递字符串
      } catch (e) {
        ElMessage.error('变量格式错误，请输入正确的 JSON 格式')
        return
      }
    }

    const isEdit = !!promptEditForm.value.id
    const url = isEdit ? `/api/v1/prompt-configs/${promptEditForm.value.id}` : '/api/v1/prompt-configs'
    const method = isEdit ? 'PUT' : 'POST'
    const body = isEdit ? {
      description: promptEditForm.value.description,
      prompt_text: promptEditForm.value.prompt_text,
      variables: variables,
      status: promptEditForm.value.status
    } : {
      name: promptEditForm.value.name,
      description: promptEditForm.value.description,
      category: promptEditForm.value.category,
      prompt_text: promptEditForm.value.prompt_text,
      variables: variables,
      status: promptEditForm.value.status
    }

    const res = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    const data = await res.json()
    if (data.code === 0) {
      ElMessage.success(isEdit ? '更新成功' : '创建成功')
      promptEditDialogVisible.value = false
      loadPrompts()
      // 热更新 Prompt 缓存
      try {
        await fetch('http://localhost:8081/api/v1/admin/reload-config', { method: 'POST' })
      } catch (e) {
        console.warn('热更新失败:', e)
      }
    } else {
      ElMessage.error(data.message || '保存失败')
    }
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function loadPromptVersions(cfgId) {
  promptVersionLoading.value = true
  try {
    const res = await fetch(`/api/v1/prompt-configs/${cfgId}/versions`)
    const data = await res.json()
    promptVersions.value = data.data || []
  } catch (e) {
    ElMessage.error('加载版本历史失败')
  } finally {
    promptVersionLoading.value = false
  }
}

function viewPromptVersions(cfg) {
  loadPromptVersions(cfg.id)
  promptVersionDialogVisible.value = true
}

async function rollbackPromptVersion(cfgId, version) {
  try {
    await fetch(`/api/v1/prompt-configs/${cfgId}/rollback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version })
    })
    ElMessage.success('回滚成功')
    loadPromptVersions(cfgId)
    loadPrompts()
  } catch (e) {
    ElMessage.error('回滚失败')
  }
}

function parseVariables(variables) {
  if (!variables) return []
  if (typeof variables === 'string') {
    try {
      // 尝试解析 JSON 对象，如 {"indicators": [...]} 或 [{"name": "ROAS", ...}]
      const parsed = JSON.parse(variables)
      if (Array.isArray(parsed)) return parsed
      if (typeof parsed === 'object' && parsed !== null) {
        // 如果是 {"indicators": [...]} 格式，返回 indicators 数组
        if (parsed.indicators) return parsed.indicators
        return [parsed]
      }
    } catch {
      // 不是 JSON，按逗号分隔处理
      return variables.split(',').map(v => v.trim()).filter(v => v)
    }
  }
  if (Array.isArray(variables)) {
    return variables
  }
  return []
}

function truncatePrompt(text) {
  if (!text) return '-'
  const maxLen = 40
  if (text.length <= maxLen) return text
  return text.substring(0, maxLen) + '...'
}

function getVarCount(variables) {
  if (!variables) return 0
  if (typeof variables === 'string') {
    try {
      const parsed = JSON.parse(variables)
      if (Array.isArray(parsed)) return parsed.length
      if (typeof parsed === 'object' && parsed !== null) {
        if (parsed.indicators) return parsed.indicators.length
        return 1
      }
    } catch {
      return variables.split(',').filter(v => v.trim()).length
    }
  }
  if (Array.isArray(variables)) {
    return variables.length
  }
  return 0
}

function formatChars(text) {
  if (!text) return '0'
  if (text.length >= 1000) {
    return (text.length / 1000).toFixed(1) + 'k'
  }
  return text.length.toString()
}

function getLineNumbers(text) {
  if (!text) return [1]
  const lines = text.split('\n').length
  return Array.from({ length: lines }, (_, i) => i + 1)
}

function highlightVariables(text) {
  if (!text) return ''
  // 转义 HTML 特殊字符
  let escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // 高亮 {variable} 格式的变量
  escaped = escaped.replace(/\{([^}]+)\}/g, '<span class="hl-var">{<span class="hl-var-name">$1</span>}</span>')
  // 高亮 JSON key
  escaped = escaped.replace(/"([^"]+)":/g, '<span class="hl-key">"$1"</span>:')
  // 高亮 JSON 字符串值
  escaped = escaped.replace(/: "([^"]*)"/g, ': <span class="hl-string">"$1"</span>')
  return escaped
}

function copyPromptContent() {
  if (!promptDetail.value?.prompt_text) return
  navigator.clipboard.writeText(promptDetail.value.prompt_text).then(() => {
    ElMessage.success('已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

function togglePromptFullscreen() {
  promptFullscreen.value = !promptFullscreen.value
}

function formatTime(timeStr) {
  if (!timeStr) return '-'
  const d = new Date(timeStr)
  return `${d.getMonth()+1}/${d.getDate()} ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
}

// Vector
async function rebuildIntentEmbeddings() {
  try {
    const response = await fetch('/api/v1/nlp/intents/rebuild-embeddings', { method: 'POST' })
    const data = await response.json()
    if (data.code === 0) {
      ElMessage.success(`成功重建 ${data.data.count} 条意图向量`)
    }
  } catch (error) {
    ElMessage.error('重建失败')
  }
}

async function rebuildMetricEmbeddings() {
  try {
    const response = await fetch('/api/v1/nlp/metrics/rebuild-embeddings', { method: 'POST' })
    const data = await response.json()
    if (data.code === 0) {
      ElMessage.success(`成功重建 ${data.data.count} 条指标向量`)
    }
  } catch (error) {
    ElMessage.error('重建失败')
  }
}

onMounted(() => {
  loadData()
})

// 切换到反馈标签时懒加载数据
watch(activeTab, (tab) => {
  if (tab === 'feedback' && intentFeedbacks.value.length === 0) {
    loadFeedback()
  }
  if (tab === 'prompts' && promptConfigs.value.length === 0) {
    loadPrompts()
  }
  if (tab === 'slots' && slotDefinitions.value.length === 0) {
    loadSlotDefinitions()
  }
})
</script>

<style scoped>
.nlp-config-page {
  padding: 28px 32px;
  max-width: 1440px;
  margin: 0 auto;
  background: var(--bg-primary);
  min-height: 100vh;
}

/* Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-icon {
  width: 44px;
  height: 44px;
  background: var(--primary-glow);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
}

.header-text h1 {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px 0;
  letter-spacing: -0.3px;
}

.header-text p {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

/* Vector Bar */
.vector-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 14px 20px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-sm);
}

.vector-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.vector-actions {
  display: flex;
  gap: 10px;
}

.vector-actions .el-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}

/* Tabs Wrapper */
.config-tabs-wrapper {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);
}

/* Tabs */
.config-tabs :deep(.el-tabs__header) {
  margin: 0 0 20px 0;
  padding: 0;
}

.config-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.config-tabs :deep(.el-tabs__item) {
  font-weight: 600;
  color: var(--text-secondary);
  font-size: 14px;
}

.config-tabs :deep(.el-tabs__item.is-active) {
  color: var(--primary);
}

.config-tabs :deep(.el-tabs__active-bar) {
  height: 2px;
  background: var(--primary);
}

/* Section */
.section {
  margin-bottom: 24px;
}

.section:last-child {
  margin-bottom: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-right {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input {
  width: 220px;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.section-header .header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-header .header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.data-count {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-primary);
  padding: 2px 8px;
  border-radius: 10px;
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--primary);
  color: #ffffff;
  border: none;
  border-radius: var(--radius-lg);
  font-weight: 600;
  font-size: 14px;
  padding: 12px 24px;
  transition: all 0.25s ease;
  box-shadow: var(--shadow-card);
}

.btn-primary:hover {
  background: var(--primary-dark);
  transform: translateY(-2px) scale(1.01);
  box-shadow: var(--shadow-card-hover);
}

/* Table */
.table-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.config-table {
  width: 100%;
  border-collapse: collapse;
}

.config-table th {
  text-align: left;
  padding: 12px 14px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
}

.config-table td {
  padding: 12px 14px;
  border-bottom: 1px solid #f4f4f5;
  font-size: 13px;
  color: var(--text-primary);
}

.config-table tr:last-child td {
  border-bottom: none;
}

.config-table tr:hover td {
  background: var(--bg-primary);
}

.name-cell {
  font-weight: 600;
}

.intent-badge {
  display: inline-block;
  padding: 3px 8px;
  background: var(--primary-glow);
  color: var(--primary);
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.category-badge {
  display: inline-block;
  padding: 3px 8px;
  background: #f0f9ff;
  color: #0369a1;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.patterns-cell {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
}

.priority-cell {
  font-family: 'SF Mono', Monaco, monospace;
  color: var(--text-secondary);
}

.metric-code {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  background: var(--bg-primary);
  padding: 2px 6px;
  border-radius: 4px;
}

.sql-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  color: var(--text-secondary);
}

.desc-cell {
  color: var(--text-secondary);
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.synonym-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  max-width: 280px;
}

.no-synonym {
  font-size: 12px;
  color: var(--text-secondary);
  opacity: 0.6;
}

.action-group {
  display: flex;
  gap: 2px;
}

.action-btn {
  padding: 4px 8px;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--text-secondary);
  border-radius: 4px;
}

.action-btn:hover {
  background: var(--bg-primary);
  color: var(--text-primary);
}

.action-btn.delete:hover {
  color: #ef4444;
  background: #fef2f2;
}

.action-btn.approve:hover {
  color: #22c55e;
  background: #f0fdf4;
}

.intent-badge.error {
  background: #fef2f2;
  color: #ef4444;
}

.intent-badge.success {
  background: #f0fdf4;
  color: #22c55e;
}

.mono-cell {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 11px;
  color: var(--text-secondary);
}

.time-cell {
  font-size: 12px;
  color: var(--text-secondary);
}

.reviewed-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.empty-state {
  padding: 48px;
  text-align: center;
  color: var(--text-secondary);
}

.empty-state svg {
  margin-bottom: 12px;
  opacity: 0.4;
}

.empty-state p {
  margin: 0;
  font-size: 13px;
}

.clear-filter-btn {
  margin-top: 8px;
  cursor: pointer;
}

.btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}

:deep(.el-switch.is-checked .el-switch__core) {
  background-color: var(--primary);
  border-color: var(--primary);
}

/* Dialog */
.config-dialog :deep(.el-dialog__header) {
  padding: 20px 24px;
  border-bottom: 1px solid var(--border);
}

.config-dialog :deep(.el-dialog__title) {
  font-weight: 700;
  color: var(--text-primary);
}

.config-form :deep(.el-form-item__label) {
  font-weight: 600;
  color: var(--text-primary);
}

.config-form :deep(.el-input__wrapper),
.config-form :deep(.el-textarea__inner) {
  border-radius: var(--radius-sm);
  box-shadow: none !important;
  border: 1px solid var(--border);
}

.config-form :deep(.el-input__wrapper:hover),
.config-form :deep(.el-input__wrapper.is-focus) {
  border-color: var(--primary);
}

.form-tip {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
  line-height: 1.4;
}

/* Prompt 详情对话框 */
.prompt-detail {
  padding: 8px 0;
}

.prompt-meta {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.prompt-description {
  padding: 12px;
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
  margin-bottom: 16px;
}

.prompt-description p {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.prompt-variables {
  margin-bottom: 16px;
}

.prompt-variables h4 {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 10px 0;
}

.variable-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.prompt-text h4 {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 10px 0;
}

.prompt-content {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 16px;
  font-family: 'SF Mono', Monaco, 'Courier New', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
  margin: 0;
}

/* Prompt 表格列宽 */
.prompt-config-table {
  table-layout: fixed;
}

.prompt-config-table .col-name {
  width: 160px;
}

.prompt-config-table .col-category {
  width: 110px;
}

.prompt-config-table .col-desc {
  width: 140px;
}

.prompt-config-table .col-preview {
  width: 180px;
}

.prompt-config-table .col-vars {
  width: 60px;
}

.prompt-config-table .col-chars {
  width: 60px;
}

.prompt-config-table .col-version {
  width: 60px;
}

.prompt-config-table .col-status {
  width: 70px;
}

.prompt-config-table .col-actions {
  width: 160px;
  white-space: nowrap;
}

.prompt-name {
  font-weight: 600;
  color: var(--text-primary);
}

.desc-cell {
  color: var(--text-secondary);
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-cell {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 11px;
  color: var(--text-secondary);
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.vars-cell {
  text-align: center;
}

.chars-cell {
  text-align: center;
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  color: var(--text-secondary);
}

/* Prompt 详情对话框优化 */
.prompt-detail-dialog :deep(.el-dialog__body) {
  padding: 0;
}

/* Prompt 详情对话框优化 */
.prompt-detail-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.prompt-detail {
  padding: 0;
}

/* Meta 信息栏 */
.prompt-meta-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.meta-left {
  display: flex;
  gap: 20px;
  align-items: center;
}

.meta-right {
  display: flex;
  gap: 16px;
  align-items: center;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.meta-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.meta-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.meta-unit {
  font-size: 11px;
  color: var(--text-secondary);
}

.copy-btn,
.history-btn,
.fullscreen-btn {
  display: inline-flex;
  align-items: center;
}

.font-size-selector {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
}

.font-size-selector :deep(.el-slider) {
  width: 80px;
}

.font-size-label {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 35px;
}

/* 描述区域 */
.prompt-desc-section {
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.section-content {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
}

/* 变量区域 */
.prompt-vars-section {
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
}

.variable-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.var-tag {
  font-family: 'SF Mono', Monaco, monospace;
  background: var(--primary-glow);
  color: var(--primary);
  border: none;
}

/* 内容区域 */
.prompt-content-section {
  padding: 14px 20px;
}

.code-container {
  display: flex;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: auto;
}

.code-line-numbers {
  padding: 12px 0;
  background: #f8f9fa;
  border-right: 1px solid var(--border);
  user-select: none;
  min-width: 40px;
  text-align: right;
}

.line-number {
  padding: 0 12px;
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #999;
}

.code-content {
  flex: 1;
  padding: 12px 16px;
  margin: 0;
  font-family: 'SF Mono', Monaco, 'Courier New', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
  overflow-x: auto;
}

/* 语法高亮 */
.hl-var {
  color: var(--primary);
  font-weight: 600;
}

.hl-var-name {
  color: var(--primary);
  background: var(--primary-glow);
  padding: 0 2px;
  border-radius: 2px;
}

.hl-key {
  color: #690;
  font-weight: 600;
}

.hl-string {
  color: #c05;
}

/* Prompt 编辑对话框 */
.el-dialog.is-fullscreen.prompt-edit-dialog .el-dialog__body {
  padding: 20px !important;
  max-height: calc(100vh - 40px) !important;
  overflow: hidden !important;
}

.prompt-edit-dialog :deep(.el-dialog__body) {
  padding: 20px !important;
  max-height: calc(100vh - 40px) !important;
  overflow: hidden !important;
}

.prompt-edit-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
  overflow: hidden;
}

/* 顶部一行 */
.edit-top-row {
  display: flex;
  gap: 16px;
  flex-shrink: 0;
}

.form-item-inline {
  flex: 0 0 auto;
}

.form-item-inline .el-input,
.form-item-inline .el-select {
  width: 140px;
}

.form-item-desc {
  flex: 1;
  min-width: 0;
}

.form-item-desc .el-input {
  width: 100%;
}

/* 左右对比布局 */
.compare-container {
  flex: 0 0 750px;
  display: flex;
  gap: 12px;
  overflow: hidden;
}

.compare-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  min-width: 0;
}

.compare-panel.compare-current {
  background: var(--bg-card);
}

.compare-panel.compare-prev {
  background: #fafafa;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  height: 42px;
  box-sizing: border-box;
}

.panel-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.panel-badge {
  font-size: 11px;
  font-weight: 600;
  color: var(--primary);
  background: var(--primary-glow);
  padding: 2px 8px;
  border-radius: 4px;
}

.compare-divider {
  width: 1px;
  background: var(--border);
}

.compare-current {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.compare-textarea {
  flex: 1;
  resize: none;
  border: none;
  border-radius: 0;
  font-family: 'SF Mono', Monaco, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  padding: 12px 16px;
  overflow-y: auto;
  background: var(--bg-card);
  color: var(--text-primary);
  box-sizing: border-box;
}

.compare-textarea:focus {
  outline: none;
}

.prev-content {
  flex: 1;
  padding: 12px 16px;
  font-family: 'SF Mono', Monaco, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
  overflow-y: auto;
  background: #fafafa;
}

.prev-content:empty::before {
  content: '暂无上一版本';
  color: var(--text-secondary);
  font-style: italic;
}

/* 底部区 */
.edit-bottom-row {
  display: flex;
  gap: 16px;
  flex-shrink: 0;
}

.edit-vars {
  flex: 1;
}

.vars-input :deep(.el-textarea__inner) {
  resize: none;
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
}

.edit-actions {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

/* Prompt 版本历史 */

/* Prompt 版本历史 */
.version-list {
  max-height: 500px;
  overflow-y: auto;
}

.version-item {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  margin-bottom: 12px;
  overflow: hidden;
}

.version-item:last-child {
  margin-bottom: 0;
}

.version-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
}

.version-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.version-badge {
  font-weight: 700;
  font-size: 13px;
  color: var(--primary);
  background: var(--primary-glow);
  padding: 2px 8px;
  border-radius: 4px;
}

.version-meta {
  font-size: 12px;
  color: var(--text-secondary);
}

.version-actions {
  display: flex;
  gap: 8px;
}

.version-content {
  padding: 12px;
  background: #fafafa;
}

.version-text {
  margin: 0;
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 150px;
  overflow-y: auto;
}

.version-reason {
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text-secondary);
  border-top: 1px solid var(--border);
  background: var(--bg-primary);
}

.reason-label {
  font-weight: 600;
}

.version-loading,
.version-empty {
  padding: 40px;
  text-align: center;
  color: var(--text-secondary);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.version-loading .el-icon {
  color: var(--primary);
}

/* Table Pagination */
.table-pagination {
  display: flex;
  justify-content: center;
  padding: 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-primary);
}

.table-pagination .el-pagination {
  font-size: 12px;
}
</style>
