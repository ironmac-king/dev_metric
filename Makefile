.PHONY: build run test clean migrate

# Go 服务
build:
	go build -o bin/server ./cmd/server

run:
	go run ./cmd/server/main.go

test:
	go test -v ./...

clean:
	rm -rf bin/

# Python AI 服务
ai-install:
	pip install -r requirements.txt

ai-run:
	python -m uvicorn ai.main:app --reload --port 8081

# 数据库迁移
migrate:
	go run ./cmd/migrate/main.go

# Excel 导入
import:
	go run ./cmd/importer/main.go --file 指标中心指标字典.xlsx

# 前端
web-install:
	cd web && npm install

web-dev:
	cd web && npm run dev

# 一键启动
dev: web-dev ai-run

# Docker (后期)
docker-build:
	docker build -t dev-metric .

# 依赖
deps:
	go mod tidy
	go mod download
