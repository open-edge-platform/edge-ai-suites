#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# NOTE: this file is required, not optional. ``content_search/api`` is a regular
# package and gets onto ``sys.path`` once the content-search helpers are loaded.
# Without an ``__init__.py`` here, this directory is only a namespace portion and
# loses to that regular package, so ``api.endpoints`` stops resolving in any
# freshly started interpreter (e.g. a spawned model-conversion subprocess).
