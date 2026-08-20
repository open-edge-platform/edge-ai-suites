# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

.PHONY: help install test clean dev run

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies with uv
	uv pip install -e .

clean:  ## Clean build artifacts and old venv
	rm -rf __pycache__
	rm -rf providers/__pycache__
	rm -rf providers/telemetry/__pycache__
	rm -rf .pytest_cache
	rm -rf *.pyc
	rm -rf .venv
	@echo "Note: Old .venv removed. Now using uv (no venv needed)"

dev:  ## Set up development environment
	@echo "Setting up development environment..."
	@command -v uv >/dev/null 2>&1 || (echo "Installing uv..." && curl -LsSf https://astral.sh/uv/install.sh | sh)
	uv pip install -e .
	@echo "Done! Run 'make run' to start the server."

run:  ## Run the MCP server
	uv run server.py

verify:  ## Verify tool discovery
	@echo "Discovering tools from tool_configs/..."
	@uv run python -c "import yaml; from pathlib import Path; tools = [(f.stem, len(yaml.safe_load(f.read_text()).get('tools', []))) for f in Path('tool_configs').glob('*.yaml')]; [print(f'  {name}: {count} tools') for name, count in tools]; print(f'\n  Total: {sum(c for _, c in tools)} tools')"

.DEFAULT_GOAL := help
