# Instrumental Maker convenience Makefile
# Usage: make <target>
# Override variables at call time, e.g.:
#   make logs SERVICE=instrumental-worker

SHELL := /bin/bash

# Core variables (override if needed)
PROJECT_NAME ?= instrumental-maker
COMPOSE ?= docker compose
SERVICE ?= ingest-watcher
ENV_FILE ?= .env

# Colors
Y := $(shell tput setaf 3 2>/dev/null || true)
G := $(shell tput setaf 2 2>/dev/null || true)
R := $(shell tput setaf 1 2>/dev/null || true)
Z := $(shell tput sgr0 2>/dev/null || true)

.PHONY: help build up down restart logs tail ps watcher-rebuild worker-rebuild mirror-rebuild rebuild service-shell clean nuke db-shell test lint fmt env show-env archive-dir rescan wipe-data wipe-data-all restart-after-wipe restart-after-full-wipe nuke-and-rebuild fresh-start show-dirs archive-du test-data-init seed-incoming-from-test show-test-data clean-incoming sudo-validate

help: ## Show this help message
	@echo "$(G)Available targets:$(Z)"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS=":.*?## "}; {printf "  $(Y)%-20s$(Z) %s\n", $$1, $$2}'

show-env: ## Display key environment / variable values
	@echo Project: $(PROJECT_NAME)
	@echo Compose Cmd: $(COMPOSE)
	@echo Default SERVICE: $(SERVICE)
	@echo ENV_FILE: $(ENV_FILE)
	@[ -f $(ENV_FILE) ] && echo "--- Contents of $(ENV_FILE) ---" && sed 's/^/  /' $(ENV_FILE) || echo "(No $(ENV_FILE) present)"

build: ## Build all images
	$(COMPOSE) build

up: ## Start (detached)
	$(COMPOSE) up -d

down: ## Stop containers (preserving volumes)
	$(COMPOSE) down

restart: ## Restart stack
	$(COMPOSE) down && $(COMPOSE) up -d

logs: ## Follow logs for SERVICE (SERVICE=<name>)
	$(COMPOSE) logs -f $(SERVICE)

tail: logs ## Alias for logs

ps: ## Show container status
	$(COMPOSE) ps

watcher-rebuild: ## Rebuild only ingest-watcher (no deps)
	$(COMPOSE) up -d --no-deps --build ingest-watcher

worker-rebuild: ## Rebuild only instrumental-worker (no deps)
	$(COMPOSE) up -d --no-deps --build instrumental-worker

mirror-rebuild: ## Rebuild only minio-mirror (no deps)
	$(COMPOSE) up -d --no-deps --build minio-mirror

rebuild: ## Rebuild all images (no cache) & recreate
	$(COMPOSE) build --no-cache && $(COMPOSE) up -d --force-recreate

service-shell: ## Open bash shell inside SERVICE (SERVICE=<name>)
	$(COMPOSE) exec $(SERVICE) bash || $(COMPOSE) run --rm $(SERVICE) bash

clean: ## Stop and remove containers + anonymous networks (keep volumes)
	$(COMPOSE) down

nuke: ## Full teardown INCLUDING named volumes (DANGEROUS)
	$(COMPOSE) down -v --remove-orphans

db-shell: ## Open sqlite3 shell for jobs DB
	@DB_PATH=$$(find pipeline-data/db volumes/db -maxdepth 1 -name 'jobs.sqlite' 2>/dev/null | head -n1); \
	 if [ -z "$$DB_PATH" ]; then echo "$(R)jobs.sqlite not found$(Z)"; exit 1; fi; \
	 echo "Opening $$DB_PATH"; \
	 sqlite3 $$DB_PATH

archive-dir: ## Show archive directory contents (if configured)
	@ARCH=$${ARCHIVE_DIR:-$$(grep '^ARCHIVE_DIR=' $(ENV_FILE) 2>/dev/null | cut -d= -f2)}; \
	 if [ -z "$$ARCH" ]; then echo "(ARCHIVE_DIR not set)"; exit 0; fi; \
	 echo "Archive: $$ARCH"; \
	 find "$$ARCH" -maxdepth 3 -type f 2>/dev/null | sed 's/^/  /' || true

rescan: ## Trigger watcher container to send USR1 (if implemented) else restart it
	@cid=$$(docker ps --filter name=$(PROJECT_NAME)-ingest-watcher -q); \
	 if [ -n "$$cid" ]; then docker kill -s USR1 $$cid 2>/dev/null || docker restart $$cid; else echo "Watcher not running"; fi

# Basic test hooks (placeholder) -------------------------------------------------
test: ## Run tests (if/when added)
	@echo "No tests defined for this project yet. Add pytest and update Makefile."

lint: ## Placeholder linter target
	@echo "Add flake8/ruff config then implement lint target."

fmt: ## Placeholder formatter target
	@echo "Add black/isort config then implement fmt target."

# -----------------------------------------------------------------------------
# Destructive data wipe helpers
# -----------------------------------------------------------------------------
wipe-data: ## Wipe pipeline-data except models (DESTROYS jobs/output/db) add CONFIRM=yes (use SUDO=sudo if root-owned files)
wipe-data: sudo-validate
	@if [ "$(CONFIRM)" != "yes" ]; then \
	  echo "$(R)Refusing to proceed. This will DELETE pipeline-data (except models).$(Z)"; \
	  echo "Re-run: make wipe-data CONFIRM=yes"; \
	  exit 1; \
	fi
	@echo "$(R)Stopping stack...$(Z)" && $(COMPOSE) down || true
	@echo "$(R)Deleting job-related subdirs in pipeline-data ...$(Z)"; \
	 if [ -n "$(SUDO)" ]; then echo "Using elevated removal via $(SUDO)"; fi; \
	 for d in incoming incoming_queued working output db logs minio-data archive test; do \
	  if [ -d pipeline-data/$$d ]; then $(SUDO) rm -rf pipeline-data/$$d; fi; \
	 done
	@echo "Recreating base directory structure with current user ownership"
	@for d in incoming incoming_queued working output db logs minio-data archive test; do \
	  mkdir -p pipeline-data/$$d; \
	done
	@echo "$(G)Done. Models preserved in pipeline-data/models.$(Z)"

wipe-data-all: ## Wipe ENTIRE pipeline-data including models (requires CONFIRM=ALL) (use SUDO=sudo if permission errors)
wipe-data-all: sudo-validate
	@if [ "$(CONFIRM)" != "ALL" ]; then \
	  echo "$(R)Refusing to proceed. This will DELETE *everything* under pipeline-data.$(Z)"; \
	  echo "Re-run: make wipe-data-all CONFIRM=ALL"; \
	  exit 1; \
	fi
	@echo "$(R)Stopping stack...$(Z)" && $(COMPOSE) down || true
	@echo "$(R)Removing pipeline-data directory$(Z)"; \
	 if [ -n "$(SUDO)" ]; then echo "Using elevated removal via $(SUDO)"; fi; \
	 $(SUDO) rm -rf pipeline-data || { echo "$(R)Removal failed (permissions?). Try: make wipe-data-all CONFIRM=ALL SUDO=sudo$(Z)"; exit 1; }
	@echo "Recreating base directory structure"
	@for d in incoming incoming_queued working output db logs models minio-data archive test; do \
	  mkdir -p pipeline-data/$$d; \
	done
	@echo "$(G)pipeline-data reset complete (empty fresh tree).$(Z)"

restart-after-wipe: ## Wipe (keeps models), then start stack
	$(MAKE) wipe-data CONFIRM=yes SUDO=$(SUDO)
	$(MAKE) up

restart-after-full-wipe: ## Full wipe (DESTROYS models), then start stack
	$(MAKE) wipe-data-all CONFIRM=ALL SUDO=$(SUDO)
	$(MAKE) up

nuke-and-rebuild: ## Nuke named volumes then rebuild all images & start fresh
	$(MAKE) nuke
	$(MAKE) rebuild

fresh-start: ## Full data reset (including models) + rebuild images + start (DANGEROUS)
	$(MAKE) wipe-data-all CONFIRM=ALL SUDO=$(SUDO)
	$(MAKE) rebuild


show-dirs: ## Show size summary of pipeline-data subdirectories
	@echo "Directory sizes (pipeline-data):"; \
	for d in pipeline-data/*; do \
	  [ -d "$$d" ] || continue; \
	  du -sh "$$d" 2>/dev/null; \
	done | sort -h

archive-du: ## Show size & top 15 largest files in archive dir (if exists)
	@ARCH=$${ARCHIVE_DIR:-pipeline-data/archive}; \
	if [ ! -d "$$ARCH" ]; then echo "Archive dir $$ARCH not found"; exit 0; fi; \
	echo "Archive total size:"; du -sh "$$ARCH"; \
	echo "Top 15 largest files:"; \
	find "$$ARCH" -type f -printf '%s\t%p\n' 2>/dev/null | sort -nr | head -15 | awk '{sz=$$1;sub($$1"\t",""); printf "%10.1f MB  %s\n", sz/1024/1024, $$0}'

# -----------------------------------------------------------------------------
# Test data helpers (root folder: test-data)
# -----------------------------------------------------------------------------
test-data-init: ## Create test-data folder structure (albums, singles, fixtures, misc)
		@mkdir -p test-data/albums test-data/singles test-data/fixtures test-data/misc; \
		 touch test-data/.gitkeep test-data/albums/.gitkeep test-data/singles/.gitkeep test-data/fixtures/.gitkeep test-data/misc/.gitkeep; \
		 echo "Created test-data structure. Place sample inputs under test-data/albums or singles."

show-test-data: ## List contents of test-data (top 3 levels)
		@if [ ! -d test-data ]; then echo "No test-data directory yet. Run: make test-data-init"; exit 0; fi; \
		 echo "test-data tree (top):"; \
		 find test-data -maxdepth 3 -mindepth 1 -print | sed 's/^/  /'

seed-incoming-from-test: ## Copy test-data/albums/* into pipeline-data/incoming (preserve structure)
		@if [ ! -d test-data/albums ]; then echo "test-data/albums not found. Run: make test-data-init and add files."; exit 1; fi; \
		 mkdir -p pipeline-data/incoming; \
		 shopt -s nullglob; \
		 for d in test-data/albums/*; do \
			 base=$$(basename "$$d"); \
			 echo "Seeding $$base -> pipeline-data/incoming/$$base"; \
			 cp -a "$$d" "pipeline-data/incoming/"; \
		 done; \
		 echo "Done seeding incoming from test-data/albums."

clean-incoming: ## Remove all files from pipeline-data/incoming (use SUDO=sudo if needed)
clean-incoming: sudo-validate
		@echo "Cleaning pipeline-data/incoming ..."; \
		 if [ -n "$(SUDO)" ]; then echo "Using elevated removal via $(SUDO)"; fi; \
		 $(SUDO) rm -rf pipeline-data/incoming/* 2>/dev/null || true; \
		 echo "Incoming cleaned."

# Self-documentation: keep help comments (##) concise.

# -----------------------------------------------------------------------------
# Sudo credential caching helper (optional)
# -----------------------------------------------------------------------------
# Usage:
#   make wipe-data SUDO=sudo SUDO_PASSWORD='yourpass'
# or set SUDO_ASKPASS=/path/to/askpass_script and run with SUDO=sudo.
# If neither SUDO_PASSWORD nor SUDO_ASKPASS are set, a single interactive
# prompt will occur (sudo -v) and persist for the sudo timestamp_timeout.

sudo-validate:
	@if [ -n "$(SUDO)" ]; then \
	  if [ -n "$(SUDO_PASSWORD)" ]; then \
	    echo "Validating sudo with SUDO_PASSWORD (insecure: env var)"; \
	    echo "$(SUDO_PASSWORD)" | $(SUDO) -S -v; \
	  elif [ -n "$(SUDO_ASKPASS)" ]; then \
	    echo "Validating sudo via SUDO_ASKPASS helper"; \
	    SUDO_ASKPASS="$(SUDO_ASKPASS)" $(SUDO) -A -v; \
	  else \
	    $(SUDO) -v; \
	  fi; \
	fi
