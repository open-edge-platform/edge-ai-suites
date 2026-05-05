.PHONY: run-mvp test-mvp run down run-without-dlsps setup run-cpu run-gpu run-npu run-mixed

# Default device profile (mixed-optimized: detection=GPU, rPPG=CPU, action=NPU)
DEVICE_ENV ?= configs/res/mixed-optimized.env

setup:
	@echo "Downloading models + video (first-time setup)..."
	python3 scripts/download_models.py --config configs/model-config.yaml --output .
	@echo ""
	@echo "Setup complete. Models downloaded. Run 'make run' to start all services."

run-mvp:
	python run_mvp_backend.py --config configs/mvp-backend.yaml --host 0.0.0.0 --port 5001

test-mvp:
	venv/bin/python -m pytest -q tests/backend_mvp

run:
	@echo "Using device profile: $(DEVICE_ENV)"
	@echo "Clearing stale metrics data..."
	rm -rf metrics/*.csv metrics/*.log metrics/*.json 2>/dev/null || true
	DEVICE_ENV=$(DEVICE_ENV) docker compose -f docker-compose.yaml --profile dlsps up --build --remove-orphans -d
	@echo ""
	@echo "All services starting. Open http://localhost:3001 once ready."
	@echo "Run 'make down' to stop."

run-cpu:
	@echo "Starting with ALL-CPU device profile..."
	$(MAKE) run DEVICE_ENV=configs/res/all-cpu.env

run-gpu:
	@echo "Starting with ALL-GPU device profile..."
	$(MAKE) run DEVICE_ENV=configs/res/all-gpu.env

run-npu:
	@echo "Starting with ALL-NPU device profile..."
	$(MAKE) run DEVICE_ENV=configs/res/all-npu.env

run-mixed:
	@echo "Starting with MIXED-OPTIMIZED device profile (detection=GPU, rPPG=CPU, action=NPU)..."
	$(MAKE) run DEVICE_ENV=configs/res/mixed-optimized.env

run-without-dlsps:
	@echo "Clearing stale metrics data..."
	rm -rf metrics/*.csv metrics/*.log metrics/*.json 2>/dev/null || true
	docker compose -f docker-compose.yaml up --build --remove-orphans -d nicu-metrics-collector nicu-backend nicu-ui

down:
	docker compose -f docker-compose.yaml --profile dlsps down
