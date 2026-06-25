.PHONY: run-mvp test-mvp run down run-without-dlsps setup convert-rppg run-cpu run-gpu run-npu run-mixed

# Default device profile (mixed-optimized: detection=GPU, rPPG=CPU, action=NPU)
DEVICE_ENV ?= configs/res/mixed-optimized.env
REGISTRY ?= true
TAG ?= 2026.1.0
export TAG

RPPG_CONVERTER_IMAGE ?= nicu-rppg-converter:local

setup:
	@echo "Downloading models + video (first-time setup)..."
	python3 scripts/download_models.py --config configs/model-config.yaml --output .
	@echo ""
	@if ls models_rppg/*.hdf5 >/dev/null 2>&1 && { [ ! -f models_rppg/mtts_can.xml ] || [ ! -f models_rppg/mtts_can.bin ]; }; then \
		echo "HDF5 model found - converting to OpenVINO IR (TensorFlow + OpenVINO in container)..."; \
		$(MAKE) convert-rppg; \
	fi
	@echo "Setup complete. Run 'make run' to start all services."

convert-rppg:
	@echo "Converting models_rppg/*.hdf5 -> models_rppg/mtts_can.{xml,bin}..."
	@if ! ls models_rppg/*.hdf5 >/dev/null 2>&1; then \
		echo "ERROR: no .hdf5 model found in models_rppg/. Place the rPPG HDF5 file there first."; \
		exit 1; \
	fi
	@echo "Building converter image: $(RPPG_CONVERTER_IMAGE)"
	docker build --no-cache -f assets.Dockerfile -t $(RPPG_CONVERTER_IMAGE) .
	@echo "Running converter container..."
	docker run --rm \
		-e HTTP_PROXY="$(HTTP_PROXY)" \
		-e HTTPS_PROXY="$(HTTPS_PROXY)" \
		-e NO_PROXY="$(NO_PROXY)" \
		-v "$(CURDIR)/configs/model-config.yaml:/app/configs/model-config.yaml:ro" \
		-v "$(CURDIR)/models_rppg:/models/rppg" \
		$(RPPG_CONVERTER_IMAGE)
	@echo "Conversion complete: models_rppg/mtts_can.xml and models_rppg/mtts_can.bin"

run-mvp:
	python run_mvp_backend.py --config configs/mvp-backend.yaml --host 0.0.0.0 --port 5001

test-mvp:
	venv/bin/python -m pytest -q tests/backend_mvp

run:
	@echo "Using device profile: $(DEVICE_ENV)"
	@if [ ! -f models_rppg/mtts_can.xml ] || [ ! -f models_rppg/mtts_can.bin ]; then \
		echo "rPPG IR artifacts are missing. Attempting conversion..."; \
		$(MAKE) convert-rppg; \
	fi
	@echo "Clearing stale metrics data..."
	@rm -rf metrics/*.csv metrics/*.log metrics/*.json 2>/dev/null || true
	@if [ "$(REGISTRY)" = "true" ]; then \
		echo "Using prebuilt registry images (TAG=$(TAG))..."; \
		DEVICE_ENV=$(DEVICE_ENV) ./run_compose.sh --profile dlsps up --remove-orphans -d; \
	else \
		echo "Building local images from source..."; \
		DEVICE_ENV=$(DEVICE_ENV) ./run_compose.sh --profile dlsps up --build --remove-orphans -d; \
	fi
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
	@if [ ! -f models_rppg/mtts_can.xml ] || [ ! -f models_rppg/mtts_can.bin ]; then \
		echo "rPPG IR artifacts are missing. Attempting conversion..."; \
		$(MAKE) convert-rppg; \
	fi
	@echo "Clearing stale metrics data..."
	@rm -rf metrics/*.csv metrics/*.log metrics/*.json 2>/dev/null || true
	@if [ "$(REGISTRY)" = "true" ]; then \
		echo "Using prebuilt registry images (TAG=$(TAG))..."; \
		DEVICE_ENV=$(DEVICE_ENV) ./run_compose.sh up --remove-orphans -d nicu-metrics-collector nicu-backend nicu-ui; \
	else \
		echo "Building local images from source..."; \
		DEVICE_ENV=$(DEVICE_ENV) ./run_compose.sh up --build --remove-orphans -d nicu-metrics-collector nicu-backend nicu-ui; \
	fi

down:
	docker compose -f docker-compose.yaml --profile dlsps down
