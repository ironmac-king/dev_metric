package handler

import (
	"encoding/json"
	"net/http/httptest"
	"testing"

	"dev_metric/pkg/response"

	"github.com/gin-gonic/gin"
)

func TestGetSemanticSnapshotDiffValidatesParams(t *testing.T) {
	gin.SetMode(gin.TestMode)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "snapshot_id", Value: "snap-target"}}
	c.Request = httptest.NewRequest("GET", "/api/v1/semantic/snapshots/snap-target/diff", nil)

	GetSemanticSnapshotDiff(c)

	var resp response.Response
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal response failed: %v", err)
	}
	if resp.Code != response.CodeBadRequest {
		t.Fatalf("expected bad request, got %+v", resp)
	}
}

func TestPublishSemanticSnapshotReturnsInternalErrorWithoutDB(t *testing.T) {
	gin.SetMode(gin.TestMode)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "snapshot_id", Value: "snap-target"}}
	c.Request = httptest.NewRequest("POST", "/api/v1/semantic/snapshots/snap-target/publish", nil)

	PublishSemanticSnapshot(c)

	var resp response.Response
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal response failed: %v", err)
	}
	if resp.Code != response.CodeInternalError {
		t.Fatalf("expected internal error, got %+v", resp)
	}
}

func TestRollbackSemanticSnapshotReturnsInternalErrorWithoutDB(t *testing.T) {
	gin.SetMode(gin.TestMode)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "snapshot_id", Value: "snap-target"}}
	c.Request = httptest.NewRequest("POST", "/api/v1/semantic/snapshots/snap-target/rollback", nil)

	RollbackSemanticSnapshot(c)

	var resp response.Response
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal response failed: %v", err)
	}
	if resp.Code != response.CodeInternalError {
		t.Fatalf("expected internal error, got %+v", resp)
	}
}
