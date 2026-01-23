# Copyright © 2026 Intel Corporation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0



update-submodules:
	@echo "Cloning performance tool repositories"
	git submodule deinit -f .
	git submodule update --init --recursive
	@echo "Submodules updated (if any present)."

run: update-submodules
	docker-compose -f docker-compose.yaml build