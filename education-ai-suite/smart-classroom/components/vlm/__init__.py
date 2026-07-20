# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Intentionally light: importing this package must not pull in the heavy VLM
# runtime (openvino_genai). ``TextGenHandler`` imports ``VLMTextGen`` lazily on
# warmup, so callers should import the submodules directly, e.g.
#   from components.vlm.text_gen_handle import TextGenHandler
