# BugPilot Makefile
# PYTHONPATH=. is required for all Python processes

PYTHONPATH := $(shell pwd)
export PYTHONPATH

GOOS ?= $(shell go env GOOS 2>/dev/null || echo linux)
GOARCH ?= $(shell go env GOARCH 2>/dev/null || echo amd64)
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo dev)
LDFLAGS := -X github.com/skonlabs/bugpilot/cmd.Version=$(VERSION) -s -w

CLI_DIR  := ./cli
DIST_DIR := ./dist

.PHONY: all build build-all test test-backend test-connectors test-cli \
        lint dev-backend dev-worker migrate migrate-reset clean install-deps help

# ── Default ───────────────────────────────────────────────────────────────────
all: build test

# ── Build ─────────────────────────────────────────────────────────────────────
build:
	@echo "Building CLI for $(GOOS)/$(GOARCH)..."
	@mkdir -p $(DIST_DIR)
	cd $(CLI_DIR) && go build \
		-ldflags "$(LDFLAGS)" \
		-o ../$(DIST_DIR)/bugpilot-$(GOOS)-$(GOARCH) \
		./main.go
	@echo "Built: $(DIST_DIR)/bugpilot-$(GOOS)-$(GOARCH)"

build-all:
	GOOS=linux   GOARCH=amd64 $(MAKE) build
	@command -v upx > /dev/null && upx --best $(DIST_DIR)/bugpilot-linux-amd64 || true
	GOOS=linux   GOARCH=arm64 $(MAKE) build
	@command -v upx > /dev/null && upx --best $(DIST_DIR)/bugpilot-linux-arm64 || true
	GOOS=darwin  GOARCH=amd64 $(MAKE) build
	GOOS=darwin  GOARCH=arm64 $(MAKE) build
	GOOS=windows GOARCH=amd64 $(MAKE) build
	@mv $(DIST_DIR)/bugpilot-windows-amd64 $(DIST_DIR)/bugpilot-windows-amd64.exe 2>/dev/null || true
	@command -v upx > /dev/null && upx --best $(DIST_DIR)/bugpilot-windows-amd64.exe || true

# ── Tests ─────────────────────────────────────────────────────────────────────
test: test-backend test-connectors

test-backend:
	@echo "Running backend tests..."
	PYTHONPATH=$(PYTHONPATH) python -m pytest backend/tests/ -v --tb=short -q

test-connectors:
	@echo "Running connector tests..."
	@for dir in connectors/sentry connectors/jira connectors/freshdesk \
	             connectors/email_imap connectors/github connectors/database \
	             connectors/log_files; do \
	  if [ -d "$$dir/tests" ]; then \
	    echo "  Testing $$dir..."; \
	    PYTHONPATH=$(PYTHONPATH) python -m pytest $$dir/tests/ -v --tb=short -q; \
	  fi; \
	done

test-cli:
	@echo "Running CLI tests..."
	cd $(CLI_DIR) && go test ./... -v

test-all: test test-cli

coverage:
	PYTHONPATH=$(PYTHONPATH) python -m pytest backend/tests/ connectors/*/tests/ \
	  --cov=backend --cov=connectors --cov-report=term-missing \
	  --cov-report=html:htmlcov --cov-fail-under=80

# ── Lint ──────────────────────────────────────────────────────────────────────
lint:
	@echo "Linting Python..."
	PYTHONPATH=$(PYTHONPATH) python -m ruff check backend/ connectors/ worker/ || true
	@echo "Linting Go..."
	cd $(CLI_DIR) && go vet ./... || true

# ── Dev servers ───────────────────────────────────────────────────────────────
dev-backend:
	@echo "Starting backend dev server on :8000..."
	PYTHONPATH=$(PYTHONPATH) uvicorn backend.app.main:app \
	  --reload --host 0.0.0.0 --port 8000 --log-level debug

dev-worker:
	@echo "Starting worker..."
	PYTHONPATH=$(PYTHONPATH) python worker/main.py

dev:
	@echo "Starting Supabase, Redis, backend, and worker..."
	supabase start

# ── Migrations ────────────────────────────────────────────────────────────────
migrate:
	@echo "Applying Supabase migrations..."
	supabase db push

migrate-reset:
	@echo "Resetting database and re-applying migrations..."
	supabase db reset

# ── Dependencies ──────────────────────────────────────────────────────────────
install-deps:
	pip install -r backend/requirements.txt
	pip install -r worker/requirements.txt
	pip install -r connectors/_base/requirements.txt
	@for dir in connectors/sentry connectors/jira connectors/freshdesk \
	             connectors/email_imap connectors/github connectors/database \
	             connectors/log_files; do \
	  if [ -f "$$dir/requirements.txt" ]; then \
	    pip install -r $$dir/requirements.txt; \
	  fi; \
	done
	pip install pytest pytest-cov ruff mypy
	cd $(CLI_DIR) && go mod download

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	rm -rf $(DIST_DIR)
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true

help:
	@echo "BugPilot Makefile targets:"
	@echo "  build        Build CLI binary"
	@echo "  build-all    Build for all 5 platforms (UPX on linux+windows)"
	@echo "  test         Run Python tests"
	@echo "  test-cli     Run Go CLI tests"
	@echo "  test-all     Run all tests"
	@echo "  coverage     Run tests with ≥80% coverage check"
	@echo "  lint         Lint Python + Go"
	@echo "  dev-backend  Start FastAPI dev server"
	@echo "  dev-worker   Start SQS worker"
	@echo "  migrate      Apply Supabase migrations"
	@echo "  install-deps Install all dependencies"
	@echo "  clean        Remove build artifacts"
