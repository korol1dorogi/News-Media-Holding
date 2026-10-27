# Targets for Linux, macOS and WSL. See START_HERE.md.
SHELL := bash

VENV := .venv
ifeq ($(OS),Windows_NT)
PYTHON ?= python
BIN := $(VENV)/Scripts
else
PYTHON ?= python3.12
BIN := $(VENV)/bin
endif
PY := $(BIN)/python

-include .env
DB_PATH := $(or $(DB_PATH),var/radar.sqlite3)

.PHONY: setup check fmt run gen-data eval reset clean-clone

setup:
	test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"
	cd frontend && npm ci

check:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	$(PY) -m pytest
	cd frontend && npx tsc --noEmit && npm run build

fmt:
	$(PY) -m ruff format . && $(PY) -m ruff check --fix .

# API on :8000 and Vite on :5173; Ctrl+C stops both.
run:
	@trap 'kill 0' INT TERM; \
	$(PY) -m uvicorn radar.api.app:app --port 8000 --reload --reload-dir radar & \
	(cd frontend && npm run dev) & \
	wait

gen-data:
	$(PY) scripts/gen_synthetic.py

eval:
	$(PY) scripts/eval.py

reset:
	rm -f $(DB_PATH)
	$(PY) -m radar.pipeline

clean-clone:
	bash scripts/check_clean_clone.sh
