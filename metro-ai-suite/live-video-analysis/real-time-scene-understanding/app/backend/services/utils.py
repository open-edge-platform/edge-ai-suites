import logging
from typing import Optional

import openvino_genai as ov_genai

logger = logging.getLogger(__name__)


def _extract_perf_metrics(result: ov_genai.py_openvino_genai.VLMDecodedResults) -> dict[str, Optional[float]]:
    """Read ttft/tpot/throughput straight off GenAI's ``perf_metrics``.

    ``VLMPipeline.generate()`` already returns a result whose
    ``.perf_metrics`` exposes well-defined accessors — ``get_ttft()``,
    ``get_tpot()``, ``get_throughput()`` — each a mean/std pair (ms for
    ttft/tpot, tokens/sec for throughput). No need to guess field names
    or walk the object graph.
    """
    perf_metrics = getattr(result, "perf_metrics", None)
    if perf_metrics is None:
        return {
            "ttft_ms": None,
            "tpot_ms": None,
            "throughput_tps": None,
            "total_tokens_generated": None,
        }

    try:
        logger.debug({
            "load_time": perf_metrics.get_load_time(),
            "num_generated_tokens": perf_metrics.get_num_generated_tokens(),
            "num_input_tokens ": perf_metrics.get_num_input_tokens(),
            "ttft_mean": perf_metrics.get_ttft().mean,
            "ttft_std": perf_metrics.get_ttft().std,
            "tpot_mean": perf_metrics.get_tpot().mean,
            "tpot_std": perf_metrics.get_tpot().std,
            "throughput_mean": perf_metrics.get_throughput().mean,
            "throughput_std": perf_metrics.get_throughput().std,
            "inference_duration_mean": perf_metrics.get_inference_duration().mean,
            "inference_duration_std": perf_metrics.get_inference_duration().std,
            "generation_duration_mean": perf_metrics.get_generate_duration().mean,
            "generation_duration_std": perf_metrics.get_generate_duration().std,
        })

        return {
            "ttft_ms": float(perf_metrics.get_ttft().mean),
            "tpot_ms": float(perf_metrics.get_tpot().mean),
            "throughput_tps": float(perf_metrics.get_throughput().mean),
            "total_tokens_generated": float(perf_metrics.get_num_generated_tokens()),
        }
    except Exception as exc:  # noqa: BLE001 - defend against API/version drift
        logger.warning("VLM perf_metrics accessors unavailable: %s", exc)
        return {
            "ttft_ms": None,
            "tpot_ms": None,
            "throughput_tps": None,
            "total_tokens_generated": None,
        }