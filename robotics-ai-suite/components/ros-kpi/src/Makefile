# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
#
# src/Makefile  —  Simulation-level targets for wandering and pick-n-place runs
#                  with integrated rosbag recording and trigger-latency analysis.
#
# Run from the repo root:   make -f src/Makefile <target>
# Or from src/:             make <target>
#
# ── Parameters (override on command line) ────────────────────────────────────
#   GOALS      Navigation goals to stop at (0 = ignore, default: 3)
#   TIMEOUT    Hard-stop timeout in seconds (default: 120)
#   REPEAT     Number of back-to-back simulation runs (default: 3)
#   PAUSE      Seconds between repeated runs (default: 30)
#   RUNS       Number of benchmark runs (default: 25)
#   BENCH      Path to bench_* directory for analyze-benchmark
#   NODE       Node name substring to filter trigger-latency analysis output
#   BAG        Path to an existing rosbag2 dir to analyse (no sim launched)
#
# Example:
#   make -f src/Makefile wandering-benchmark          # 25 × 120s runs, then aggregate
#   make -f src/Makefile wandering-benchmark RUNS=5   # quick test
#   make -f src/Makefile analyze-benchmark BENCH=monitoring_sessions/wandering/bench_20260318_120000

GOALS   ?= 3
TIMEOUT ?= 120
PN_TIMEOUT ?= 300   # picknplace: demo completes ~157s; 300s = 2× safety margin
REPEAT  ?= 3
PAUSE   ?= 30
RUNS    ?= 25
NODE    ?=
BAG     ?=
BENCH   ?=

# Resolve repo root whether we are invoked from src/ or from the repo root.
MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
ifeq ($(notdir $(MAKEFILE_DIR:/=)),src)
  ROOT := $(abspath $(MAKEFILE_DIR)/..)
else
  ROOT := $(abspath $(MAKEFILE_DIR))
endif

SRC           := $(ROOT)/src
SESSIONS      := $(ROOT)/monitoring_sessions
WANDERING     := $(SESSIONS)/wandering
PICKNPLACE    := $(SESSIONS)/picknplace
ANALYZE_PY    := python3 $(SRC)/analyze_trigger_latency.py
AGGREGATE_PY  := python3 $(SRC)/aggregate_kpi.py
WANDERING_SH  := bash $(SRC)/wandering_run.sh
PICKNPLACE_SH := bash $(SRC)/picknplace_run.sh

.PHONY: help \
        wandering wandering-record wandering-plot wandering-record-plot \
        wandering-benchmark analyze-benchmark \
        picknplace-run picknplace-record picknplace-plot picknplace-record-plot \
        picknplace-benchmark \
        analyze-bag analyze-last-wandering analyze-last-picknplace \
        clean-wandering-bags

# ─────────────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "src/Makefile — Simulation targets with rosbag recording & trigger analysis"
	@echo ""
	@echo "WANDERING (TurtleBot3 nav2 wandering sim):"
	@echo "  wandering              Run sim + graph monitor + trigger-latency (goals=$(GOALS))"
	@echo "  wandering-record       + record KPI topics to a rosbag"
	@echo "  wandering-plot         + save trigger-timeline PNGs"
	@echo "  wandering-record-plot  + record + plots"
	@echo "  wandering-benchmark    $(RUNS) runs × $(TIMEOUT)s, then aggregate KPIs (no goals)"
	@echo "                         Override: RUNS=10 TIMEOUT=120 PAUSE=30"
	@echo ""
	@echo "PICK-N-PLACE (AMR warehouse sim):"
	@echo "  picknplace-run           Run sim + graph monitor + trigger-latency"
	@echo "  picknplace-record        + record KPI topics to a rosbag"
	@echo "  picknplace-plot          + save trigger-timeline PNGs"
	@echo "  picknplace-record-plot   + record + plots"
	@echo "  picknplace-benchmark     $(RUNS) runs × up to $(PN_TIMEOUT)s, then aggregate KPIs"
	@echo "                           (stops early on 'Demo complete', override: PN_TIMEOUT=300)"
	@echo ""
	@echo "TRIGGER-LATENCY ANALYSIS:"
	@echo "  analyze-bag                  Analyse timestamps from BAG=<path> dir"
	@echo "                               (bag must contain graph_topology.json)"
	@echo "  analyze-last-wandering       Re-run analysis on most recent wandering session"
	@echo "  analyze-last-picknplace      Re-run analysis on most recent picknplace session"
	@echo "  analyze-benchmark            Aggregate KPIs from BENCH=<bench_dir> (25+ runs)"
	@echo ""
	@echo "UTILITIES:"
	@echo "  clean-wandering-bags         Remove rosbag dirs from monitoring_sessions/wandering/"
	@echo "  clean-picknplace-bags        Remove rosbag dirs from monitoring_sessions/picknplace/"
	@echo ""
	@echo "Parameters (all overridable):"
	@echo "  GOALS=$(GOALS)  TIMEOUT=$(TIMEOUT)  PN_TIMEOUT=$(PN_TIMEOUT)  RUNS=$(RUNS)  PAUSE=$(PAUSE)"
	@if [ -n "$(NODE)" ]; then echo "  NODE=$(NODE)"; fi
	@if [ -n "$(BAG)" ];  then echo "  BAG=$(BAG)"; fi
	@if [ -n "$(BENCH)" ]; then echo "  BENCH=$(BENCH)"; fi
	@echo ""

# ─────────────────────────────────────────────────────────────────────────────
# WANDERING
# ─────────────────────────────────────────────────────────────────────────────

wandering:
	@echo "▶ Wandering sim, trigger-latency analysis (goals=$(GOALS), timeout=$(TIMEOUT)s)"
	$(WANDERING_SH) --goals $(GOALS) --timeout $(TIMEOUT)

wandering-record:
	@echo "▶ Wandering sim + rosbag record (goals=$(GOALS), timeout=$(TIMEOUT)s)"
	$(WANDERING_SH) --goals $(GOALS) --timeout $(TIMEOUT) --record
	@SESS=$$(ls -td $(WANDERING)/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'); \
	[ -n "$$SESS" ] && echo "" && echo "  make -f src/Makefile analyze-bag BAG=$$SESS/bag" || true

wandering-plot:
	@echo "▶ Wandering sim + trigger-timeline plots (goals=$(GOALS), timeout=$(TIMEOUT)s)"
	$(WANDERING_SH) --goals $(GOALS) --timeout $(TIMEOUT) --plot

wandering-record-plot:
	@echo "▶ Wandering sim + rosbag record + plots (goals=$(GOALS), timeout=$(TIMEOUT)s)"
	$(WANDERING_SH) --goals $(GOALS) --timeout $(TIMEOUT) --record --plot
	@SESS=$$(ls -td $(WANDERING)/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'); \
	[ -n "$$SESS" ] && echo "" && echo "  make -f src/Makefile analyze-bag BAG=$$SESS/bag" || true

# ─────────────────────────────────────────────────────────────────────────────
# BENCHMARK  (time-based, goals ignored, 25 runs → aggregate KPIs)
# ─────────────────────────────────────────────────────────────────────────────

wandering-benchmark:
	@RUNS=$(RUNS); TIMEOUT=$(TIMEOUT); PAUSE=$(PAUSE); \
	BENCH_DIR="$(WANDERING)/bench_$$(date '+%Y%m%d_%H%M%S')"; \
	mkdir -p "$$BENCH_DIR"; \
	echo ""; \
	echo "╔══════════════════════════════════════════════════════════════╗"; \
	echo "║  Wandering Benchmark                                         ║"; \
	echo "║  Runs     : $$RUNS                                              ║"; \
	echo "║  Duration : $${TIMEOUT}s per run (goals ignored)              ║"; \
	echo "║  Pause    : $${PAUSE}s between runs                           ║"; \
	echo "║  Output   : $$BENCH_DIR"; \
	echo "╚══════════════════════════════════════════════════════════════╝"; \
	echo ""; \
	for i in $$(seq 1 $$RUNS); do \
		echo ""; \
		echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
		echo "  Run $$i / $$RUNS  ($(TIMEOUT)s)"; \
		echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
		$(WANDERING_SH) --goals 0 --timeout $${TIMEOUT} --record \
			--output-parent "$$BENCH_DIR" || true; \
		if [ $$i -lt $$RUNS ]; then \
			echo ""; \
			echo "  ⏳ Pausing $${PAUSE}s for system to settle..."; \
			sleep $$PAUSE; \
		fi; \
	done; \
	echo ""; \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	echo "  All $$RUNS runs complete.  Aggregating KPIs..."; \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	$(AGGREGATE_PY) "$$BENCH_DIR" \
		--csv-out "$$BENCH_DIR/benchmark_results.csv"; \
	echo ""; \
	echo "  Results CSV: $$BENCH_DIR/benchmark_results.csv"; \
	echo "  Re-analyze:  make -f src/Makefile analyze-benchmark BENCH=$$BENCH_DIR"

analyze-benchmark:
	@[ -n "$(BENCH)" ] || { \
		echo "ERROR: specify BENCH=path/to/bench_YYYYMMDD_HHMMSS"; \
		echo "       Example: make -f src/Makefile analyze-benchmark BENCH=$(WANDERING)/bench_20260318_120000"; \
		exit 1; \
	}
	$(AGGREGATE_PY) "$(BENCH)" \
		$(if $(NODE),--node $(NODE),) \
		--csv-out "$(BENCH)/benchmark_results.csv"

# ─────────────────────────────────────────────────────────────────────────────
# PICK-N-PLACE
# ─────────────────────────────────────────────────────────────────────────────

picknplace-run:
	@echo "▶ PicknPlace sim + graph monitor + trigger-latency"
	$(PICKNPLACE_SH) --timeout $(PN_TIMEOUT)

picknplace-record:
	@echo "▶ PicknPlace sim + rosbag record (timeout=$(PN_TIMEOUT)s)"
	$(PICKNPLACE_SH) --timeout $(PN_TIMEOUT) --record
	@SESS=$$(ls -td $(PICKNPLACE)/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'); \
	[ -n "$$SESS" ] && echo "" && echo "  make -f src/Makefile analyze-bag BAG=$$SESS/bag" || true

picknplace-plot:
	@echo "▶ PicknPlace sim + trigger-timeline plots (timeout=$(PN_TIMEOUT)s)"
	$(PICKNPLACE_SH) --timeout $(PN_TIMEOUT) --plot

picknplace-record-plot:
	@echo "▶ PicknPlace sim + rosbag record + plots (timeout=$(PN_TIMEOUT)s)"
	$(PICKNPLACE_SH) --timeout $(PN_TIMEOUT) --record --plot
	@SESS=$$(ls -td $(PICKNPLACE)/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'); \
	[ -n "$$SESS" ] && echo "" && echo "  make -f src/Makefile analyze-bag BAG=$$SESS/bag" || true

# ─────────────────────────────────────────────────────────────────────────────
# PICK-N-PLACE BENCHMARK  (N runs → aggregate KPIs)
# ─────────────────────────────────────────────────────────────────────────────

picknplace-benchmark:
	@RUNS=$(RUNS); TIMEOUT=$(PN_TIMEOUT); PAUSE=$(PAUSE); \
	BENCH_DIR="$(PICKNPLACE)/bench_$$(date '+%Y%m%d_%H%M%S')"; \
	mkdir -p "$$BENCH_DIR"; \
	echo ""; \
	echo "╔══════════════════════════════════════════════════════════════╗"; \
	echo "║  PicknPlace Benchmark                                        ║"; \
	echo "║  Runs     : $$RUNS                                              ║"; \
	echo "║  Timeout  : $${TIMEOUT}s per run (or 'Demo complete')          ║"; \
	echo "║  Pause    : $${PAUSE}s between runs                           ║"; \
	echo "║  Output   : $$BENCH_DIR"; \
	echo "╚══════════════════════════════════════════════════════════════╝"; \
	echo ""; \
	for i in $$(seq 1 $$RUNS); do \
		echo ""; \
		echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
		echo "  Run $$i / $$RUNS  (up to $${TIMEOUT}s)"; \
		echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
		$(PICKNPLACE_SH) --timeout $${TIMEOUT} --record \
			--output-parent "$$BENCH_DIR" || true; \
		if [ $$i -lt $$RUNS ]; then \
			echo ""; \
			echo "  ⏳ Pausing $${PAUSE}s for system to settle..."; \
			sleep $$PAUSE; \
		fi; \
	done; \
	echo ""; \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	echo "  All $$RUNS runs complete.  Aggregating KPIs..."; \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	$(AGGREGATE_PY) "$$BENCH_DIR" \
		--csv-out "$$BENCH_DIR/benchmark_results.csv"; \
	echo ""; \
	echo "  Results CSV: $$BENCH_DIR/benchmark_results.csv"; \
	echo "  Re-analyze:  make -f src/Makefile analyze-benchmark BENCH=$$BENCH_DIR"

# ─────────────────────────────────────────────────────────────────────────────
# TRIGGER-LATENCY ANALYSIS — standalone targets
# ─────────────────────────────────────────────────────────────────────────────

analyze-bag:
	@if [ -z "$(BAG)" ]; then \
		echo "Error: specify BAG=<path-to-rosbag2-dir-or-mcap-file>"; \
		echo "  Example: make -f src/Makefile analyze-bag BAG=monitoring_sessions/wandering/20260318_150945"; \
		echo "  With separate topology: make -f src/Makefile analyze-bag BAG=... TOPO=monitoring_sessions/wandering/20260318_142328_analysis/graph_topology.json"; \
		exit 1; \
	fi
	@echo "▶ Trigger-latency analysis from rosbag: $(BAG)"
	$(ANALYZE_PY) --bag $(BAG) \
		$(if $(TOPO),--topology $(TOPO),) \
		$(if $(NODE),--node $(NODE),) \
		--plot --no-show

analyze-last-wandering:
	@SESS=$$(ls -td $(WANDERING)/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'); \
	if [ -z "$$SESS" ]; then \
		echo "No wandering session found under $(WANDERING)"; \
		exit 1; \
	fi; \
	echo "▶ Trigger-latency analysis — $$SESS"; \
	$(ANALYZE_PY) --session "$$SESS" \
		$(if $(NODE),--node $(NODE),) \
		--plot --no-show

analyze-last-picknplace:
	@SESS=$$(ls -td $(PICKNPLACE)/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'); \
	if [ -z "$$SESS" ]; then \
		echo "No picknplace session found under $(PICKNPLACE)"; \
		exit 1; \
	fi; \
	echo "▶ Trigger-latency analysis — $$SESS"; \
	$(ANALYZE_PY) --session "$$SESS" \
		$(if $(NODE),--node $(NODE),) \
		--plot --no-show

# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

clean-wandering-bags:
	@echo "Removing bag subdirs from $(WANDERING) ..."
	@find $(WANDERING) -maxdepth 2 -name "*.mcap" -printf "%h\n" \
		| sort -u \
		| while read d; do echo "  rm -rf $$d"; rm -rf "$$d"; done
	@echo "Done."

clean-picknplace-bags:
	@echo "Removing bag subdirs from $(PICKNPLACE) ..."
	@find $(PICKNPLACE) -maxdepth 2 -name "*.mcap" -printf "%h\n" \
		| sort -u \
		| while read d; do echo "  rm -rf $$d"; rm -rf "$$d"; done
	@echo "Done."

