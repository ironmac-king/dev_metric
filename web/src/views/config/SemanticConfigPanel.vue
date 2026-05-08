<template>
  <div class="semantic-config">
    <div class="semantic-toolbar">
      <div class="toolbar-left">
        <el-button @click="loadAll" class="btn-refresh">刷新</el-button>
        <el-button @click="handleBootstrap" :loading="bootstrapping">初始化语义数据</el-button>
        <el-button type="primary" @click="handleCompile" :loading="compiling">编译快照</el-button>
      </div>
      <div class="toolbar-right">
        <span v-if="activeSnapshot" class="active-version">
          当前版本: {{ activeSnapshot.version }}
        </span>
        <span v-else class="active-version muted">当前版本: 未发布</span>
      </div>
    </div>

    <div class="summary-grid">
      <div class="summary-card">
        <div class="summary-label">语义指标</div>
        <div class="summary-value">{{ metrics.length }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">语义维度</div>
        <div class="summary-value">{{ dimensions.length }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">能力矩阵</div>
        <div class="summary-value">{{ capabilities.length }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">交互策略</div>
        <div class="summary-value">{{ policies.length }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">语义动作</div>
        <div class="summary-value">{{ actions.length }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">快照版本</div>
        <div class="summary-value">{{ snapshots.length }}</div>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="semantic-tabs">
      <el-tab-pane label="语义指标" name="metrics">
        <div class="tab-toolbar">
          <el-button type="primary" @click="openMetricDialog()">新增指标语义</el-button>
        </div>
        <div class="table-card">
          <table class="config-table">
            <thead>
              <tr>
                <th>指标编码</th>
                <th>显示名</th>
                <th>默认聚合</th>
                <th>默认粒度</th>
                <th>默认图表</th>
                <th>推荐维度</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in metrics" :key="item.id">
                <td class="mono">{{ item.metric_code }}</td>
                <td>{{ item.display_name }}</td>
                <td>{{ item.default_aggregation || '-' }}</td>
                <td>{{ item.default_time_grain || '-' }}</td>
                <td>{{ item.default_chart_type || '-' }}</td>
                <td>{{ formatArray(item.recommended_dimension_codes) }}</td>
                <td>
                  <div class="action-row">
                    <el-button link type="primary" @click="openMetricDialog(item)">编辑</el-button>
                    <el-button link type="danger" @click="removeMetric(item)">删除</el-button>
                  </div>
                </td>
              </tr>
              <tr v-if="metrics.length === 0">
                <td colspan="7" class="empty-cell">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="语义维度" name="dimensions">
        <div class="tab-toolbar">
          <el-button type="primary" @click="openDimensionDialog()">新增维度语义</el-button>
        </div>
        <div class="table-card">
          <table class="config-table">
            <thead>
              <tr>
                <th>维度编码</th>
                <th>显示名</th>
                <th>层级</th>
                <th>支持能力</th>
                <th>下钻目标</th>
                <th>允许指标</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in dimensions" :key="item.id">
                <td class="mono">{{ item.dimension_code }}</td>
                <td>{{ item.display_name }}</td>
                <td>{{ item.hierarchy_level }}</td>
                <td>
                  <div class="tag-row">
                    <span class="mini-tag" :class="{ enabled: item.supports_group_by }">group</span>
                    <span class="mini-tag" :class="{ enabled: item.supports_filter }">filter</span>
                    <span class="mini-tag" :class="{ enabled: item.supports_drilldown }">drilldown</span>
                  </div>
                </td>
                <td>{{ formatArray(item.drilldown_targets) }}</td>
                <td>{{ formatArray(item.allowed_metric_codes) }}</td>
                <td>
                  <div class="action-row">
                    <el-button link type="primary" @click="openDimensionDialog(item)">编辑</el-button>
                    <el-button link type="danger" @click="removeDimension(item)">删除</el-button>
                  </div>
                </td>
              </tr>
              <tr v-if="dimensions.length === 0">
                <td colspan="7" class="empty-cell">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="分析能力" name="capabilities">
        <div class="tab-toolbar">
          <el-button type="primary" @click="openCapabilityDialog()">新增能力规则</el-button>
        </div>
        <div class="table-card">
          <table class="config-table">
            <thead>
              <tr>
                <th>主体</th>
                <th>趋势</th>
                <th>对比</th>
                <th>同比</th>
                <th>环比</th>
                <th>排名</th>
                <th>占比</th>
                <th>归因</th>
                <th>下钻</th>
                <th>模式</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in capabilities" :key="item.id">
                <td class="mono">{{ item.subject_type }}:{{ item.subject_key }}</td>
                <td>{{ yesNo(item.supports_trend) }}</td>
                <td>{{ yesNo(item.supports_comparison) }}</td>
                <td>{{ yesNo(item.supports_yoy) }}</td>
                <td>{{ yesNo(item.supports_mom) }}</td>
                <td>{{ yesNo(item.supports_ranking) }}</td>
                <td>{{ yesNo(item.supports_ratio) }}</td>
                <td>{{ yesNo(item.supports_attribution) }}</td>
                <td>{{ yesNo(item.supports_drilldown) }}</td>
                <td>{{ formatArray(item.allowed_modes) }}</td>
                <td>
                  <div class="action-row">
                    <el-button link type="primary" @click="openCapabilityDialog(item)">编辑</el-button>
                    <el-button link type="danger" @click="removeCapability(item)">删除</el-button>
                  </div>
                </td>
              </tr>
              <tr v-if="capabilities.length === 0">
                <td colspan="11" class="empty-cell">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="交互策略" name="policies">
        <div class="tab-toolbar">
          <el-button type="primary" @click="openPolicyDialog()">新增交互策略</el-button>
        </div>
        <div class="table-card">
          <table class="config-table">
            <thead>
              <tr>
                <th>策略键</th>
                <th>场景</th>
                <th>回答模式</th>
                <th>澄清优先级</th>
                <th>推荐上限</th>
                <th>回退策略</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in policies" :key="item.id">
                <td class="mono">{{ item.policy_key }}</td>
                <td>{{ item.scene_type }}</td>
                <td>{{ item.answer_mode }}</td>
                <td>{{ item.clarify_priority }}</td>
                <td>{{ item.max_suggestions }}</td>
                <td>{{ item.fallback_strategy || '-' }}</td>
                <td>
                  <div class="action-row">
                    <el-button link type="primary" @click="openPolicyDialog(item)">编辑</el-button>
                    <el-button link type="danger" @click="removePolicy(item)">删除</el-button>
                  </div>
                </td>
              </tr>
              <tr v-if="policies.length === 0">
                <td colspan="7" class="empty-cell">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="下钻动作" name="actions">
        <div class="tab-toolbar">
          <el-button type="primary" @click="openActionDialog()">新增语义动作</el-button>
        </div>
        <div class="table-card">
          <table class="config-table">
            <thead>
              <tr>
                <th>动作编码</th>
                <th>标签</th>
                <th>来源场景</th>
                <th>目标场景</th>
                <th>约束</th>
                <th>目标载荷</th>
                <th>优先级</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in actions" :key="item.id">
                <td class="mono">{{ item.action_code }}</td>
                <td>{{ item.label }}</td>
                <td>{{ item.source_scene_type }}</td>
                <td>{{ item.target_scene_type }}</td>
                <td>{{ compactJson(item.source_constraints_json) }}</td>
                <td>{{ compactJson(item.target_payload_template) }}</td>
                <td>{{ item.priority }}</td>
                <td>
                  <div class="action-row">
                    <el-button link type="primary" @click="openActionDialog(item)">编辑</el-button>
                    <el-button link type="danger" @click="removeAction(item)">删除</el-button>
                  </div>
                </td>
              </tr>
              <tr v-if="actions.length === 0">
                <td colspan="8" class="empty-cell">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="快照发布" name="snapshots">
        <div class="tab-toolbar snapshot-toolbar">
          <div class="snapshot-controls">
            <span class="control-label">Diff 基线</span>
            <el-select v-model="diffBaseSnapshotId" placeholder="选择基线快照" style="width: 320px">
              <el-option
                v-for="item in snapshots"
                :key="item.snapshot_id"
                :label="`${item.version} (${item.snapshot_id})`"
                :value="item.snapshot_id"
              />
            </el-select>
          </div>
        </div>
        <div class="table-card">
          <table class="config-table">
            <thead>
              <tr>
                <th>快照ID</th>
                <th>版本</th>
                <th>状态</th>
                <th>编译人</th>
                <th>编译时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in snapshots" :key="item.id">
                <td class="mono">{{ item.snapshot_id }}</td>
                <td>{{ item.version }}</td>
                <td><span class="status-pill" :class="item.status">{{ item.status }}</span></td>
                <td>{{ item.compiled_by }}</td>
                <td>{{ formatDate(item.compiled_at) }}</td>
                <td>
                  <el-button
                    v-if="item.status !== 'active'"
                    size="small"
                    type="primary"
                    @click="handlePublish(item)"
                    :loading="publishingId === item.snapshot_id"
                  >
                    发布
                  </el-button>
                  <el-button
                    v-if="item.status === 'archived'"
                    size="small"
                    type="warning"
                    @click="handleRollback(item)"
                    :loading="rollbackingId === item.snapshot_id"
                  >
                    回滚
                  </el-button>
                  <el-button
                    size="small"
                    @click="handleDiff(item)"
                    :loading="diffLoadingId === item.snapshot_id"
                  >
                    Diff
                  </el-button>
                  <span v-if="item.status === 'active'" class="active-text">当前生效</span>
                </td>
              </tr>
              <tr v-if="snapshots.length === 0">
                <td colspan="6" class="empty-cell">暂无快照</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="activeSnapshot" class="snapshot-preview">
          <div class="preview-title">当前快照预览</div>
          <pre>{{ prettyPayload(activeSnapshot.payload) }}</pre>
        </div>

        <div v-if="snapshotDiff" class="snapshot-preview">
          <div class="preview-title">快照 Diff</div>
          <div class="diff-summary-grid">
            <div class="summary-card diff-card">
              <div class="summary-label">新增</div>
              <div class="summary-value">{{ snapshotDiff.summary?.added || 0 }}</div>
            </div>
            <div class="summary-card diff-card">
              <div class="summary-label">删除</div>
              <div class="summary-value">{{ snapshotDiff.summary?.removed || 0 }}</div>
            </div>
            <div class="summary-card diff-card">
              <div class="summary-label">变更</div>
              <div class="summary-value">{{ snapshotDiff.summary?.changed || 0 }}</div>
            </div>
          </div>
          <div class="diff-meta mono">
            {{ snapshotDiff.from_snapshot_id }} -> {{ snapshotDiff.to_snapshot_id }}
          </div>
          <div class="diff-sections">
            <div
              v-for="section in formatDiffSections(snapshotDiff)"
              :key="section.name"
              class="diff-section"
            >
              <div class="diff-section-title">{{ section.name }}</div>
              <div class="diff-section-grid">
                <div class="diff-column">
                  <div class="diff-column-title added">新增</div>
                  <div v-if="section.added.length === 0" class="diff-empty">-</div>
                  <div v-for="item in section.added" :key="`a-${section.name}-${item}`" class="diff-item mono">
                    {{ item }}
                  </div>
                </div>
                <div class="diff-column">
                  <div class="diff-column-title removed">删除</div>
                  <div v-if="section.removed.length === 0" class="diff-empty">-</div>
                  <div v-for="item in section.removed" :key="`r-${section.name}-${item}`" class="diff-item mono">
                    {{ item }}
                  </div>
                </div>
                <div class="diff-column">
                  <div class="diff-column-title changed">变更</div>
                  <div v-if="section.changed.length === 0" class="diff-empty">-</div>
                  <div v-for="item in section.changed" :key="`c-${section.name}-${item}`" class="diff-item mono">
                    {{ item }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="table-card audit-card">
          <div class="preview-title">发布审计</div>
          <table class="config-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>事件</th>
                <th>快照ID</th>
                <th>状态变化</th>
                <th>操作人</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in snapshotAudits" :key="item.id">
                <td>{{ formatDate(item.created_at) }}</td>
                <td>{{ item.event_type }}</td>
                <td class="mono">{{ item.snapshot_id }}</td>
                <td>{{ `${item.before_status || '-'} -> ${item.after_status || '-'}` }}</td>
                <td>{{ item.operator || '-' }}</td>
                <td>{{ item.note || '-' }}</td>
              </tr>
              <tr v-if="snapshotAudits.length === 0">
                <td colspan="6" class="empty-cell">暂无审计记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="metricDialogVisible" :title="metricDialogTitle" width="720px">
      <el-form :model="metricForm" label-width="120px" class="config-form">
        <el-form-item label="指标编码"><el-input v-model="metricForm.metric_code" :disabled="!!metricForm.id" /></el-form-item>
        <el-form-item label="显示名称"><el-input v-model="metricForm.display_name" /></el-form-item>
        <el-form-item label="业务摘要"><el-input v-model="metricForm.business_summary" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="默认聚合"><el-input v-model="metricForm.default_aggregation" /></el-form-item>
        <el-form-item label="默认粒度"><el-input v-model="metricForm.default_time_grain" /></el-form-item>
        <el-form-item label="默认图表"><el-input v-model="metricForm.default_chart_type" /></el-form-item>
        <el-form-item label="推荐维度"><el-input v-model="metricForm.recommended_dimension_codes_text" placeholder="逗号分隔，如 FSITE,GROUP_2" /></el-form-item>
        <el-form-item label="推荐追问"><el-input v-model="metricForm.preferred_followups_text" type="textarea" :rows="2" placeholder="每行一条或逗号分隔" /></el-form-item>
        <el-form-item label="标签"><el-input v-model="metricForm.tags_text" placeholder="逗号分隔" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="metricDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveMetric" :loading="savingMetric">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="dimensionDialogVisible" :title="dimensionDialogTitle" width="760px">
      <el-form :model="dimensionForm" label-width="120px" class="config-form">
        <el-form-item label="维度编码"><el-input v-model="dimensionForm.dimension_code" :disabled="!!dimensionForm.id" /></el-form-item>
        <el-form-item label="显示名称"><el-input v-model="dimensionForm.display_name" /></el-form-item>
        <el-form-item label="层级"><el-input-number v-model="dimensionForm.hierarchy_level" :min="0" :max="10" /></el-form-item>
        <el-form-item label="父维度编码"><el-input v-model="dimensionForm.parent_dimension_code" /></el-form-item>
        <el-form-item label="默认排序"><el-input-number v-model="dimensionForm.default_sort_priority" :min="0" :max="1000" /></el-form-item>
        <el-form-item label="下钻目标"><el-input v-model="dimensionForm.drilldown_targets_text" placeholder="逗号分隔" /></el-form-item>
        <el-form-item label="允许指标"><el-input v-model="dimensionForm.allowed_metric_codes_text" type="textarea" :rows="2" placeholder="逗号分隔" /></el-form-item>
        <el-form-item label="标签"><el-input v-model="dimensionForm.tags_text" placeholder="逗号分隔" /></el-form-item>
        <el-form-item label="能力">
          <div class="checkbox-row">
            <el-checkbox v-model="dimensionForm.supports_group_by">group</el-checkbox>
            <el-checkbox v-model="dimensionForm.supports_filter">filter</el-checkbox>
            <el-checkbox v-model="dimensionForm.supports_drilldown">drilldown</el-checkbox>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dimensionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDimension" :loading="savingDimension">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="capabilityDialogVisible" :title="capabilityDialogTitle" width="820px">
      <el-form :model="capabilityForm" label-width="140px" class="config-form">
        <el-form-item label="主体类型"><el-input v-model="capabilityForm.subject_type" /></el-form-item>
        <el-form-item label="主体标识"><el-input v-model="capabilityForm.subject_key" /></el-form-item>
        <el-form-item label="支持模式"><el-input v-model="capabilityForm.allowed_modes_text" placeholder="逗号分隔，如 direct,analyze,drilldown" /></el-form-item>
        <el-form-item label="约束JSON"><el-input v-model="capabilityForm.constraints_json_text" type="textarea" :rows="4" placeholder='{"query_frequency":"daily"}' /></el-form-item>
        <el-form-item label="能力开关">
          <div class="checkbox-grid">
            <el-checkbox v-model="capabilityForm.supports_value">value</el-checkbox>
            <el-checkbox v-model="capabilityForm.supports_trend">trend</el-checkbox>
            <el-checkbox v-model="capabilityForm.supports_comparison">comparison</el-checkbox>
            <el-checkbox v-model="capabilityForm.supports_yoy">yoy</el-checkbox>
            <el-checkbox v-model="capabilityForm.supports_mom">mom</el-checkbox>
            <el-checkbox v-model="capabilityForm.supports_ranking">ranking</el-checkbox>
            <el-checkbox v-model="capabilityForm.supports_ratio">ratio</el-checkbox>
            <el-checkbox v-model="capabilityForm.supports_attribution">attribution</el-checkbox>
            <el-checkbox v-model="capabilityForm.supports_drilldown">drilldown</el-checkbox>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="capabilityDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCapability" :loading="savingCapability">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="policyDialogVisible" :title="policyDialogTitle" width="760px">
      <el-form :model="policyForm" label-width="130px" class="config-form">
        <el-form-item label="策略键"><el-input v-model="policyForm.policy_key" :disabled="!!policyForm.id" /></el-form-item>
        <el-form-item label="场景类型"><el-input v-model="policyForm.scene_type" /></el-form-item>
        <el-form-item label="回答模式"><el-input v-model="policyForm.answer_mode" /></el-form-item>
        <el-form-item label="澄清优先级"><el-input-number v-model="policyForm.clarify_priority" :min="0" :max="1000" /></el-form-item>
        <el-form-item label="推荐上限"><el-input-number v-model="policyForm.max_suggestions" :min="0" :max="20" /></el-form-item>
        <el-form-item label="回退策略"><el-input v-model="policyForm.fallback_strategy" /></el-form-item>
        <el-form-item label="阈值JSON"><el-input v-model="policyForm.confidence_thresholds_text" type="textarea" :rows="3" placeholder='{"direct":0.85,"clarify":0.6}' /></el-form-item>
        <el-form-item label="策略JSON"><el-input v-model="policyForm.policy_json_text" type="textarea" :rows="4" placeholder='{"prefer_context_task":true}' /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="policyDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePolicy" :loading="savingPolicy">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="actionDialogVisible" :title="actionDialogTitle" width="760px">
      <el-form :model="actionForm" label-width="140px" class="config-form">
        <el-form-item label="动作编码"><el-input v-model="actionForm.action_code" :disabled="!!actionForm.id" /></el-form-item>
        <el-form-item label="显示标签"><el-input v-model="actionForm.label" /></el-form-item>
        <el-form-item label="来源场景"><el-input v-model="actionForm.source_scene_type" /></el-form-item>
        <el-form-item label="目标场景"><el-input v-model="actionForm.target_scene_type" /></el-form-item>
        <el-form-item label="优先级"><el-input-number v-model="actionForm.priority" :min="0" :max="1000" /></el-form-item>
        <el-form-item label="约束JSON"><el-input v-model="actionForm.source_constraints_json_text" type="textarea" :rows="4" placeholder='{"check":"sales"}' /></el-form-item>
        <el-form-item label="目标载荷JSON"><el-input v-model="actionForm.target_payload_template_text" type="textarea" :rows="4" placeholder='{"question":"__DRILLDOWN__:sales__"}' /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="actionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveAction" :loading="savingAction">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { semanticAPI } from '@/api'

const activeTab = ref('metrics')
const bootstrapping = ref(false)
const compiling = ref(false)
const publishingId = ref('')
const rollbackingId = ref('')
const diffLoadingId = ref('')

const metrics = ref([])
const dimensions = ref([])
const capabilities = ref([])
const policies = ref([])
const actions = ref([])
const snapshots = ref([])
const activeSnapshot = ref(null)
const snapshotAudits = ref([])
const snapshotDiff = ref(null)
const diffBaseSnapshotId = ref('')

const metricDialogVisible = ref(false)
const dimensionDialogVisible = ref(false)
const capabilityDialogVisible = ref(false)
const policyDialogVisible = ref(false)
const actionDialogVisible = ref(false)

const metricDialogTitle = ref('新增指标语义')
const dimensionDialogTitle = ref('新增维度语义')
const capabilityDialogTitle = ref('新增能力规则')
const policyDialogTitle = ref('新增交互策略')
const actionDialogTitle = ref('新增语义动作')

const savingMetric = ref(false)
const savingDimension = ref(false)
const savingCapability = ref(false)
const savingPolicy = ref(false)
const savingAction = ref(false)

const metricForm = reactive(createMetricForm())
const dimensionForm = reactive(createDimensionForm())
const capabilityForm = reactive(createCapabilityForm())
const policyForm = reactive(createPolicyForm())
const actionForm = reactive(createActionForm())

function createMetricForm() {
  return {
    id: null,
    metric_code: '',
    display_name: '',
    business_summary: '',
    default_aggregation: 'SUM',
    default_time_grain: 'day',
    default_chart_type: 'line',
    recommended_dimension_codes_text: '',
    preferred_followups_text: '',
    tags_text: '',
    status: 1,
    version: 1,
  }
}

function createDimensionForm() {
  return {
    id: null,
    dimension_code: '',
    display_name: '',
    hierarchy_level: 0,
    parent_dimension_code: '',
    supports_group_by: true,
    supports_filter: true,
    supports_drilldown: false,
    drilldown_targets_text: '',
    allowed_metric_codes_text: '',
    default_sort_priority: 0,
    tags_text: '',
    status: 1,
    version: 1,
  }
}

function createCapabilityForm() {
  return {
    id: null,
    subject_type: 'metric',
    subject_key: '',
    supports_value: true,
    supports_trend: false,
    supports_comparison: false,
    supports_yoy: false,
    supports_mom: false,
    supports_ranking: false,
    supports_ratio: false,
    supports_attribution: false,
    supports_drilldown: false,
    allowed_modes_text: '',
    constraints_json_text: '{}',
    status: 1,
    version: 1,
  }
}

function createPolicyForm() {
  return {
    id: null,
    policy_key: '',
    scene_type: '',
    answer_mode: 'direct',
    clarify_priority: 0,
    max_suggestions: 3,
    confidence_thresholds_text: '{}',
    fallback_strategy: '',
    policy_json_text: '{}',
    status: 1,
    version: 1,
  }
}

function createActionForm() {
  return {
    id: null,
    action_code: '',
    label: '',
    source_scene_type: '',
    target_scene_type: '',
    source_constraints_json_text: '{}',
    target_payload_template_text: '{}',
    priority: 0,
    status: 1,
    version: 1,
  }
}

function resetForm(target, factory) {
  Object.assign(target, factory())
}

function splitTextList(value) {
  if (!value) return []
  return String(value)
    .split(/[\n,，、]+/)
    .map(item => item.trim())
    .filter(Boolean)
}

function parseJsonText(text, fallback = {}) {
  try {
    const value = JSON.parse(text || '{}')
    return value && typeof value === 'object' ? value : fallback
  } catch {
    return fallback
  }
}

function formatArray(value) {
  if (!value || value.length === 0) return '-'
  return Array.isArray(value) ? value.join(', ') : String(value)
}

function formatDate(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 19)
}

function yesNo(value) {
  return value ? '是' : '否'
}

function compactJson(value) {
  if (!value || (typeof value === 'object' && Object.keys(value).length === 0)) return '-'
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function prettyPayload(payload) {
  if (!payload) return '{}'
  try {
    return JSON.stringify(typeof payload === 'string' ? JSON.parse(payload) : payload, null, 2)
  } catch {
    return String(payload)
  }
}

function formatDiffSections(diff) {
  if (!diff?.sections || typeof diff.sections !== 'object') return []
  return Object.entries(diff.sections).map(([name, section]) => ({
    name,
    added: Array.isArray(section?.added) ? section.added : [],
    removed: Array.isArray(section?.removed) ? section.removed : [],
    changed: Array.isArray(section?.changed) ? section.changed : [],
  }))
}

async function loadAll() {
  try {
    const [
      metricsRes,
      dimensionsRes,
      capabilitiesRes,
      policiesRes,
      actionsRes,
      snapshotsRes,
      activeRes,
      auditsRes,
    ] = await Promise.all([
      semanticAPI.listMetrics(),
      semanticAPI.listDimensions(),
      semanticAPI.listCapabilities(),
      semanticAPI.listPolicies(),
      semanticAPI.listActions(),
      semanticAPI.listSnapshots(),
      semanticAPI.getActiveSnapshot().catch(() => ({ data: null })),
      semanticAPI.listSnapshotAudits().catch(() => ({ data: [] })),
    ])

    metrics.value = metricsRes.data || []
    dimensions.value = dimensionsRes.data || []
    capabilities.value = capabilitiesRes.data || []
    policies.value = policiesRes.data || []
    actions.value = actionsRes.data || []
    snapshots.value = snapshotsRes.data || []
    activeSnapshot.value = activeRes.data || null
    snapshotAudits.value = auditsRes.data || []
    if (!diffBaseSnapshotId.value && snapshots.value.length > 0) {
      diffBaseSnapshotId.value = activeSnapshot.value?.snapshot_id || snapshots.value[0].snapshot_id
    }
  } catch {
    ElMessage.error('加载语义层数据失败')
  }
}

async function handleBootstrap() {
  bootstrapping.value = true
  try {
    await semanticAPI.bootstrap()
    ElMessage.success('语义初始化完成')
    await loadAll()
  } catch {
    ElMessage.error('语义初始化失败')
  } finally {
    bootstrapping.value = false
  }
}

async function handleCompile() {
  compiling.value = true
  try {
    await semanticAPI.compileSnapshot({ compiled_by: 'semantic-ui', release_note: 'manual compile from config center' })
    ElMessage.success('快照编译成功')
    await loadAll()
  } catch {
    ElMessage.error('快照编译失败')
  } finally {
    compiling.value = false
  }
}

async function handlePublish(snapshot) {
  publishingId.value = snapshot.snapshot_id
  try {
    await semanticAPI.publishSnapshot(snapshot.snapshot_id)
    ElMessage.success('快照发布成功')
    await loadAll()
  } catch {
    ElMessage.error('快照发布失败')
  } finally {
    publishingId.value = ''
  }
}

async function handleRollback(snapshot) {
  rollbackingId.value = snapshot.snapshot_id
  try {
    await semanticAPI.rollbackSnapshot(snapshot.snapshot_id, {
      operator: 'semantic-ui',
      note: 'manual rollback from config center',
    })
    ElMessage.success('快照回滚成功')
    await loadAll()
  } catch {
    ElMessage.error('快照回滚失败')
  } finally {
    rollbackingId.value = ''
  }
}

async function handleDiff(snapshot) {
  const baseSnapshotId = diffBaseSnapshotId.value || activeSnapshot.value?.snapshot_id
  if (!baseSnapshotId) {
    ElMessage.warning('请选择 Diff 基线快照')
    return
  }
  if (baseSnapshotId === snapshot.snapshot_id) {
    ElMessage.warning('基线快照不能与目标快照相同')
    return
  }

  diffLoadingId.value = snapshot.snapshot_id
  try {
    const res = await semanticAPI.diffSnapshot(snapshot.snapshot_id, baseSnapshotId)
    snapshotDiff.value = res.data || null
    ElMessage.success('快照 Diff 生成成功')
  } catch {
    ElMessage.error('快照 Diff 生成失败')
  } finally {
    diffLoadingId.value = ''
  }
}

function openMetricDialog(item = null) {
  resetForm(metricForm, createMetricForm)
  if (item) {
    Object.assign(metricForm, {
      ...item,
      recommended_dimension_codes_text: (item.recommended_dimension_codes || []).join(','),
      preferred_followups_text: (item.preferred_followups || []).join('\n'),
      tags_text: (item.tags || []).join(','),
    })
    metricDialogTitle.value = '编辑指标语义'
  } else {
    metricDialogTitle.value = '新增指标语义'
  }
  metricDialogVisible.value = true
}

async function saveMetric() {
  if (!metricForm.metric_code || !metricForm.display_name) {
    ElMessage.warning('请填写指标编码和显示名称')
    return
  }
  savingMetric.value = true
  const payload = {
    metric_code: metricForm.metric_code,
    display_name: metricForm.display_name,
    business_summary: metricForm.business_summary,
    default_aggregation: metricForm.default_aggregation,
    default_time_grain: metricForm.default_time_grain,
    default_chart_type: metricForm.default_chart_type,
    recommended_dimension_codes: splitTextList(metricForm.recommended_dimension_codes_text),
    preferred_followups: splitTextList(metricForm.preferred_followups_text),
    tags: splitTextList(metricForm.tags_text),
    status: metricForm.status,
    version: metricForm.version || 1,
  }
  try {
    if (metricForm.id) {
      await semanticAPI.updateMetric(metricForm.id, payload)
      ElMessage.success('指标语义更新成功')
    } else {
      await semanticAPI.createMetric(payload)
      ElMessage.success('指标语义创建成功')
    }
    metricDialogVisible.value = false
    await loadAll()
  } catch {
    ElMessage.error(metricForm.id ? '指标语义更新失败' : '指标语义创建失败')
  } finally {
    savingMetric.value = false
  }
}

async function removeMetric(item) {
  try {
    await ElMessageBox.confirm(`确定删除指标语义 [${item.display_name}] 吗？`, '删除确认', { type: 'warning' })
    await semanticAPI.deleteMetric(item.id)
    ElMessage.success('删除成功')
    await loadAll()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

function openDimensionDialog(item = null) {
  resetForm(dimensionForm, createDimensionForm)
  if (item) {
    Object.assign(dimensionForm, {
      ...item,
      drilldown_targets_text: (item.drilldown_targets || []).join(','),
      allowed_metric_codes_text: (item.allowed_metric_codes || []).join(','),
      tags_text: (item.tags || []).join(','),
    })
    dimensionDialogTitle.value = '编辑维度语义'
  } else {
    dimensionDialogTitle.value = '新增维度语义'
  }
  dimensionDialogVisible.value = true
}

async function saveDimension() {
  if (!dimensionForm.dimension_code || !dimensionForm.display_name) {
    ElMessage.warning('请填写维度编码和显示名称')
    return
  }
  savingDimension.value = true
  const payload = {
    dimension_code: dimensionForm.dimension_code,
    display_name: dimensionForm.display_name,
    hierarchy_level: dimensionForm.hierarchy_level,
    parent_dimension_code: dimensionForm.parent_dimension_code,
    supports_group_by: dimensionForm.supports_group_by,
    supports_filter: dimensionForm.supports_filter,
    supports_drilldown: dimensionForm.supports_drilldown,
    drilldown_targets: splitTextList(dimensionForm.drilldown_targets_text),
    allowed_metric_codes: splitTextList(dimensionForm.allowed_metric_codes_text),
    default_sort_priority: dimensionForm.default_sort_priority,
    tags: splitTextList(dimensionForm.tags_text),
    status: dimensionForm.status,
    version: dimensionForm.version || 1,
  }
  try {
    if (dimensionForm.id) {
      await semanticAPI.updateDimension(dimensionForm.id, payload)
      ElMessage.success('维度语义更新成功')
    } else {
      await semanticAPI.createDimension(payload)
      ElMessage.success('维度语义创建成功')
    }
    dimensionDialogVisible.value = false
    await loadAll()
  } catch {
    ElMessage.error(dimensionForm.id ? '维度语义更新失败' : '维度语义创建失败')
  } finally {
    savingDimension.value = false
  }
}

async function removeDimension(item) {
  try {
    await ElMessageBox.confirm(`确定删除维度语义 [${item.display_name}] 吗？`, '删除确认', { type: 'warning' })
    await semanticAPI.deleteDimension(item.id)
    ElMessage.success('删除成功')
    await loadAll()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

function openCapabilityDialog(item = null) {
  resetForm(capabilityForm, createCapabilityForm)
  if (item) {
    Object.assign(capabilityForm, {
      ...item,
      allowed_modes_text: (item.allowed_modes || []).join(','),
      constraints_json_text: JSON.stringify(item.constraints_json || {}, null, 2),
      supports_yoy: item.supports_yoy ?? item.supports_yo_y ?? false,
      supports_mom: item.supports_mom ?? item.supports_mo_m ?? false,
    })
    capabilityDialogTitle.value = '编辑能力规则'
  } else {
    capabilityDialogTitle.value = '新增能力规则'
  }
  capabilityDialogVisible.value = true
}

async function saveCapability() {
  if (!capabilityForm.subject_type || !capabilityForm.subject_key) {
    ElMessage.warning('请填写主体类型和主体标识')
    return
  }
  savingCapability.value = true
  const payload = {
    subject_type: capabilityForm.subject_type,
    subject_key: capabilityForm.subject_key,
    supports_value: capabilityForm.supports_value,
    supports_trend: capabilityForm.supports_trend,
    supports_comparison: capabilityForm.supports_comparison,
    supports_yoy: capabilityForm.supports_yoy,
    supports_mom: capabilityForm.supports_mom,
    supports_ranking: capabilityForm.supports_ranking,
    supports_ratio: capabilityForm.supports_ratio,
    supports_attribution: capabilityForm.supports_attribution,
    supports_drilldown: capabilityForm.supports_drilldown,
    allowed_modes: splitTextList(capabilityForm.allowed_modes_text),
    constraints_json: parseJsonText(capabilityForm.constraints_json_text),
    status: capabilityForm.status,
    version: capabilityForm.version || 1,
  }
  try {
    if (capabilityForm.id) {
      await semanticAPI.updateCapability(capabilityForm.id, payload)
      ElMessage.success('能力规则更新成功')
    } else {
      await semanticAPI.createCapability(payload)
      ElMessage.success('能力规则创建成功')
    }
    capabilityDialogVisible.value = false
    await loadAll()
  } catch {
    ElMessage.error(capabilityForm.id ? '能力规则更新失败' : '能力规则创建失败')
  } finally {
    savingCapability.value = false
  }
}

async function removeCapability(item) {
  try {
    await ElMessageBox.confirm(`确定删除能力规则 [${item.subject_type}:${item.subject_key}] 吗？`, '删除确认', { type: 'warning' })
    await semanticAPI.deleteCapability(item.id)
    ElMessage.success('删除成功')
    await loadAll()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

function openPolicyDialog(item = null) {
  resetForm(policyForm, createPolicyForm)
  if (item) {
    Object.assign(policyForm, {
      ...item,
      confidence_thresholds_text: JSON.stringify(item.confidence_thresholds || {}, null, 2),
      policy_json_text: JSON.stringify(item.policy_json || {}, null, 2),
    })
    policyDialogTitle.value = '编辑交互策略'
  } else {
    policyDialogTitle.value = '新增交互策略'
  }
  policyDialogVisible.value = true
}

async function savePolicy() {
  if (!policyForm.policy_key || !policyForm.scene_type) {
    ElMessage.warning('请填写策略键和场景类型')
    return
  }
  savingPolicy.value = true
  const payload = {
    policy_key: policyForm.policy_key,
    scene_type: policyForm.scene_type,
    answer_mode: policyForm.answer_mode,
    clarify_priority: policyForm.clarify_priority,
    max_suggestions: policyForm.max_suggestions,
    confidence_thresholds: parseJsonText(policyForm.confidence_thresholds_text),
    fallback_strategy: policyForm.fallback_strategy,
    policy_json: parseJsonText(policyForm.policy_json_text),
    status: policyForm.status,
    version: policyForm.version || 1,
  }
  try {
    if (policyForm.id) {
      await semanticAPI.updatePolicy(policyForm.id, payload)
      ElMessage.success('交互策略更新成功')
    } else {
      await semanticAPI.createPolicy(payload)
      ElMessage.success('交互策略创建成功')
    }
    policyDialogVisible.value = false
    await loadAll()
  } catch {
    ElMessage.error(policyForm.id ? '交互策略更新失败' : '交互策略创建失败')
  } finally {
    savingPolicy.value = false
  }
}

async function removePolicy(item) {
  try {
    await ElMessageBox.confirm(`确定删除交互策略 [${item.policy_key}] 吗？`, '删除确认', { type: 'warning' })
    await semanticAPI.deletePolicy(item.id)
    ElMessage.success('删除成功')
    await loadAll()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

function openActionDialog(item = null) {
  resetForm(actionForm, createActionForm)
  if (item) {
    Object.assign(actionForm, {
      ...item,
      source_constraints_json_text: JSON.stringify(item.source_constraints_json || {}, null, 2),
      target_payload_template_text: JSON.stringify(item.target_payload_template || {}, null, 2),
    })
    actionDialogTitle.value = '编辑语义动作'
  } else {
    actionDialogTitle.value = '新增语义动作'
  }
  actionDialogVisible.value = true
}

async function saveAction() {
  if (!actionForm.action_code || !actionForm.label) {
    ElMessage.warning('请填写动作编码和显示标签')
    return
  }
  savingAction.value = true
  const payload = {
    action_code: actionForm.action_code,
    label: actionForm.label,
    source_scene_type: actionForm.source_scene_type,
    target_scene_type: actionForm.target_scene_type,
    source_constraints_json: parseJsonText(actionForm.source_constraints_json_text),
    target_payload_template: parseJsonText(actionForm.target_payload_template_text),
    priority: actionForm.priority,
    status: actionForm.status,
    version: actionForm.version || 1,
  }
  try {
    if (actionForm.id) {
      await semanticAPI.updateAction(actionForm.id, payload)
      ElMessage.success('语义动作更新成功')
    } else {
      await semanticAPI.createAction(payload)
      ElMessage.success('语义动作创建成功')
    }
    actionDialogVisible.value = false
    await loadAll()
  } catch {
    ElMessage.error(actionForm.id ? '语义动作更新失败' : '语义动作创建失败')
  } finally {
    savingAction.value = false
  }
}

async function removeAction(item) {
  try {
    await ElMessageBox.confirm(`确定删除语义动作 [${item.action_code}] 吗？`, '删除确认', { type: 'warning' })
    await semanticAPI.deleteAction(item.id)
    ElMessage.success('删除成功')
    await loadAll()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(loadAll)
</script>

<style scoped>
.semantic-config {
  padding: 0 4px;
}

.semantic-toolbar,
.tab-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.toolbar-left {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.active-version {
  font-size: 13px;
  color: #374151;
}

.active-version.muted {
  color: #9ca3af;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.summary-card {
  background: linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px 16px;
}

.summary-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
}

.summary-value {
  font-size: 24px;
  font-weight: 700;
  color: #111827;
}

.table-card,
.snapshot-preview {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 16px;
}

.snapshot-toolbar {
  align-items: center;
}

.snapshot-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.control-label {
  font-size: 13px;
  color: #4b5563;
  font-weight: 600;
}

.config-table {
  width: 100%;
  border-collapse: collapse;
}

.config-table th,
.config-table td {
  padding: 12px 10px;
  border-bottom: 1px solid #f3f4f6;
  text-align: left;
  font-size: 13px;
  color: #374151;
  vertical-align: top;
}

.config-table th {
  font-weight: 600;
  color: #111827;
  background: #f9fafb;
}

.mono {
  font-family: 'Fira Code', monospace;
  color: #4f46e5;
}

.empty-cell {
  text-align: center;
  color: #9ca3af;
  padding: 24px 0;
}

.tag-row,
.checkbox-row,
.action-row,
.checkbox-grid {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.checkbox-grid {
  row-gap: 10px;
}

.mini-tag {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  color: #9ca3af;
  background: #f3f4f6;
}

.mini-tag.enabled {
  color: #0f766e;
  background: #ccfbf1;
}

.status-pill {
  display: inline-flex;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.status-pill.active {
  background: #dcfce7;
  color: #166534;
}

.status-pill.draft {
  background: #fef3c7;
  color: #92400e;
}

.status-pill.archived {
  background: #e5e7eb;
  color: #4b5563;
}

.active-text {
  font-size: 12px;
  color: #16a34a;
  font-weight: 600;
}

.snapshot-preview {
  margin-top: 16px;
}

.audit-card {
  margin-top: 16px;
}

.diff-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.diff-card {
  border: 1px solid #eef2f7;
}

.diff-meta {
  margin-bottom: 12px;
  font-size: 12px;
}

.diff-sections {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.diff-section {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px;
}

.diff-section-title {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 10px;
}

.diff-section-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.diff-column {
  min-width: 0;
}

.diff-column-title {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
}

.diff-column-title.added {
  color: #166534;
}

.diff-column-title.removed {
  color: #b91c1c;
}

.diff-column-title.changed {
  color: #92400e;
}

.diff-item,
.diff-empty {
  font-size: 12px;
  line-height: 1.6;
  color: #374151;
}

.preview-title {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 10px;
}

.snapshot-preview pre {
  margin: 0;
  padding: 14px;
  border-radius: 12px;
  background: #111827;
  color: #e5e7eb;
  font-size: 12px;
  line-height: 1.5;
  overflow: auto;
  max-height: 320px;
}

.config-form :deep(.el-input),
.config-form :deep(.el-textarea),
.config-form :deep(.el-select) {
  width: 100%;
}

@media (max-width: 1280px) {
  .summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .semantic-toolbar,
  .tab-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .table-card {
    overflow-x: auto;
  }

  .config-table {
    min-width: 1120px;
  }
}
</style>
