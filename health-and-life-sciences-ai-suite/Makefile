# Copyright © 2026 Intel Corporation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


update-submodules-mdpnp:
	@echo "Updating mdpnp submodule only"
	git submodule update --init \
	  services/mdpnp-service/mdpnp

update-mdpnp-remote:
	@echo "Updating mdpnp submodule from remote"
	git submodule update --remote \
	  services/mdpnp-service/mdpnp


build-mdpnp-runtime:
	@echo "Building mdpnp flat runtime"
	cd services/mdpnp-service/mdpnp && \
	  ./gradlew :interop-lab:demo-apps:makeFlatRuntime


run: update-submodules-mdpnp build-mdpnp-runtime
	docker compose -f docker-compose.yaml up --build