package handler

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"dev_metric/internal/model"
	"dev_metric/internal/repository/postgres"

	"github.com/gin-gonic/gin"
	gormpostgres "gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

type semanticAPIResponse struct {
	Code    int             `json:"code"`
	Message string          `json:"message"`
	Data    json.RawMessage `json:"data"`
}

func setupSemanticHandlerPGTest(t *testing.T) (*gorm.DB, func()) {
	t.Helper()

	dsn := os.Getenv("SEMANTIC_TEST_DSN")
	if dsn == "" {
		t.Skip("SEMANTIC_TEST_DSN not set; skipping PostgreSQL integration test")
	}

	baseDB, err := gorm.Open(gormpostgres.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Silent),
	})
	if err != nil {
		t.Fatalf("open base postgres failed: %v", err)
	}

	schema := fmt.Sprintf("itest_semantic_%d", time.Now().UnixNano())
	if err := baseDB.Exec(fmt.Sprintf(`CREATE SCHEMA %s`, schema)).Error; err != nil {
		t.Fatalf("create schema failed: %v", err)
	}

	scopedDSN := fmt.Sprintf("%s search_path=%s", dsn, schema)
	testDB, err := gorm.Open(gormpostgres.Open(scopedDSN), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Silent),
	})
	if err != nil {
		t.Fatalf("open scoped postgres failed: %v", err)
	}
	if err := testDB.AutoMigrate(&model.SemanticSnapshot{}, &model.SemanticSnapshotAudit{}); err != nil {
		t.Fatalf("automigrate semantic governance tables failed: %v", err)
	}

	restore := postgres.SetForTest(testDB)

	cleanup := func() {
		restore()
		_ = baseDB.Exec(fmt.Sprintf(`DROP SCHEMA IF EXISTS %s CASCADE`, schema)).Error
		if sqlDB, err := testDB.DB(); err == nil {
			_ = sqlDB.Close()
		}
		if sqlDB, err := baseDB.DB(); err == nil {
			_ = sqlDB.Close()
		}
	}

	return testDB, cleanup
}

func decodeSemanticResponse(t *testing.T, recorder *httptest.ResponseRecorder) semanticAPIResponse {
	t.Helper()
	var resp semanticAPIResponse
	if err := json.Unmarshal(recorder.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode response failed: %v", err)
	}
	return resp
}

func TestSemanticSnapshotGovernanceHandlers_WithPostgres(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db, cleanup := setupSemanticHandlerPGTest(t)
	defer cleanup()

	active := model.SemanticSnapshot{
		SnapshotID:  "snap-active",
		Version:     "v1",
		CompiledAt:  time.Now().UTC().Add(-time.Hour),
		CompiledBy:  "tester",
		Payload:     model.JSONBlob([]byte(`{"metrics":{"M1":{"display_name":"sales"}},"dimensions":{"FSITE":{"display_name":"site"}}}`)),
		Status:      "active",
		ReleaseNote: "active snapshot",
	}
	target := model.SemanticSnapshot{
		SnapshotID:  "snap-target",
		Version:     "v2",
		CompiledAt:  time.Now().UTC(),
		CompiledBy:  "tester",
		Payload:     model.JSONBlob([]byte(`{"metrics":{"M1":{"display_name":"sales-new"},"M2":{"display_name":"profit"}},"dimensions":{}}`)),
		Status:      "archived",
		ReleaseNote: "target snapshot",
	}
	if err := db.Create(&active).Error; err != nil {
		t.Fatalf("create active snapshot failed: %v", err)
	}
	if err := db.Create(&target).Error; err != nil {
		t.Fatalf("create target snapshot failed: %v", err)
	}

	{
		recorder := httptest.NewRecorder()
		ctx, _ := gin.CreateTestContext(recorder)
		req := httptest.NewRequest("GET", "/api/v1/semantic/snapshots/snap-target/diff?base_snapshot_id=snap-active", nil)
		ctx.Request = req
		ctx.Params = gin.Params{{Key: "snapshot_id", Value: "snap-target"}}

		GetSemanticSnapshotDiff(ctx)

		resp := decodeSemanticResponse(t, recorder)
		if resp.Code != 0 {
			t.Fatalf("expected diff success, got %+v", resp)
		}
		var data map[string]any
		if err := json.Unmarshal(resp.Data, &data); err != nil {
			t.Fatalf("decode diff data failed: %v", err)
		}
		summary := data["summary"].(map[string]any)
		if int(summary["added"].(float64)) < 1 || int(summary["changed"].(float64)) < 1 {
			t.Fatalf("unexpected diff summary: %+v", summary)
		}
	}

	{
		recorder := httptest.NewRecorder()
		ctx, _ := gin.CreateTestContext(recorder)
		body := bytes.NewBufferString(`{"operator":"itest","note":"publish target"}`)
		req := httptest.NewRequest("POST", "/api/v1/semantic/snapshots/snap-target/publish", body)
		req.Header.Set("Content-Type", "application/json")
		ctx.Request = req
		ctx.Params = gin.Params{{Key: "snapshot_id", Value: "snap-target"}}

		PublishSemanticSnapshot(ctx)

		resp := decodeSemanticResponse(t, recorder)
		if resp.Code != 0 {
			t.Fatalf("expected publish success, got %+v", resp)
		}
	}

	var refreshedActive model.SemanticSnapshot
	if err := db.Where("snapshot_id = ?", "snap-active").First(&refreshedActive).Error; err != nil {
		t.Fatalf("reload active snapshot failed: %v", err)
	}
	if refreshedActive.Status != "archived" {
		t.Fatalf("expected snap-active archived after publish, got %s", refreshedActive.Status)
	}

	var refreshedTarget model.SemanticSnapshot
	if err := db.Where("snapshot_id = ?", "snap-target").First(&refreshedTarget).Error; err != nil {
		t.Fatalf("reload target snapshot failed: %v", err)
	}
	if refreshedTarget.Status != "active" {
		t.Fatalf("expected snap-target active after publish, got %s", refreshedTarget.Status)
	}

	{
		recorder := httptest.NewRecorder()
		ctx, _ := gin.CreateTestContext(recorder)
		body := bytes.NewBufferString(`{"operator":"itest","note":"rollback active"}`)
		req := httptest.NewRequest("POST", "/api/v1/semantic/snapshots/snap-active/rollback", body)
		req.Header.Set("Content-Type", "application/json")
		ctx.Request = req
		ctx.Params = gin.Params{{Key: "snapshot_id", Value: "snap-active"}}

		RollbackSemanticSnapshot(ctx)

		resp := decodeSemanticResponse(t, recorder)
		if resp.Code != 0 {
			t.Fatalf("expected rollback success, got %+v", resp)
		}
	}

	if err := db.Where("snapshot_id = ?", "snap-active").First(&refreshedActive).Error; err != nil {
		t.Fatalf("reload active snapshot after rollback failed: %v", err)
	}
	if refreshedActive.Status != "active" {
		t.Fatalf("expected snap-active active after rollback, got %s", refreshedActive.Status)
	}
	if err := db.Where("snapshot_id = ?", "snap-target").First(&refreshedTarget).Error; err != nil {
		t.Fatalf("reload target snapshot after rollback failed: %v", err)
	}
	if refreshedTarget.Status != "archived" {
		t.Fatalf("expected snap-target archived after rollback, got %s", refreshedTarget.Status)
	}

	{
		recorder := httptest.NewRecorder()
		ctx, _ := gin.CreateTestContext(recorder)
		req := httptest.NewRequest("GET", "/api/v1/semantic/snapshots/audit", nil)
		ctx.Request = req

		ListSemanticSnapshotAudits(ctx)

		resp := decodeSemanticResponse(t, recorder)
		if resp.Code != 0 {
			t.Fatalf("expected audit success, got %+v", resp)
		}
		var audits []map[string]any
		if err := json.Unmarshal(resp.Data, &audits); err != nil {
			t.Fatalf("decode audits failed: %v", err)
		}
		if len(audits) < 4 {
			t.Fatalf("expected at least 4 audit events, got %d", len(audits))
		}
	}
}
