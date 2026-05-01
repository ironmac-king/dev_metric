# Semantic Layer Governance

## Purpose

语义层不是单纯的配置表集合，而是智能问数主链的独立解释层。主链逐步退化为执行链，业务含义解释权集中到 active semantic snapshot。

## Runtime Model

- 维护层：`semantic_metrics / semantic_dimensions / semantic_analysis_capabilities / semantic_interaction_policies / semantic_actions`
- 运行层：`semantic_snapshots`
- 治理层：`semantic_snapshot_audits`

运行时只读当前 `active` snapshot。

## Governance Flow

1. 编辑语义实体
2. `compile` 生成 draft snapshot
3. `diff` 对比基线快照
4. `publish` 激活新快照
5. 如有需要，`rollback` 到旧快照
6. 全过程写入 `audit`

## APIs

### Snapshot

- `GET /api/v1/semantic/snapshots`
- `GET /api/v1/semantic/snapshots/active`
- `POST /api/v1/semantic/snapshots/compile`
- `GET /api/v1/semantic/snapshots/:snapshot_id/diff?base_snapshot_id=...`
- `POST /api/v1/semantic/snapshots/:snapshot_id/publish`
- `POST /api/v1/semantic/snapshots/:snapshot_id/rollback`
- `GET /api/v1/semantic/snapshots/audit`

### Frontend

快照治理入口：

- `web/src/views/config/SemanticConfigPanel.vue`

## Migration

正式 SQL 迁移：

- `migrations/016_semantic_layer.sql`

迁移命令：

- `cmd/migrate/main.go`

迁移登记表：

- `schema_migration_registry`

每个步骤以 `step_key + checksum` 记录。重复执行会跳过，checksum 漂移会阻断，避免环境漂移被静默吞掉。

## PG Integration Test

测试文件：

- `internal/api/handler/semantic_handler_pg_integration_test.go`

环境变量：

- `SEMANTIC_TEST_DSN`

要求：

- 必须指向专用测试库
- 测试会创建临时 schema 并自动清理
- 不要复用共享开发库
