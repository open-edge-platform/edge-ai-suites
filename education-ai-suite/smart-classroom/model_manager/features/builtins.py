import logging

from utils.pipeline_catalog import FEATURE_IDS

from .asr_feature import ASRFeature
from .board_ocr_feature import BoardOCRFeature
from .content_search_feature import ContentSearchFeature
from .grading_feature import GradingFeature
from .mindmap_feature import MindmapFeature
from .qa_feature import QAFeature
from .registry import REGISTRY, register
from .report_feature import ReportFeature
from .segmentation_feature import SegmentationFeature
from .summary_feature import SummaryFeature
from .va_feature import VideoAnalyticsFeature

logger = logging.getLogger(__name__)

# Which class implements which catalog id. Registration order comes from the
# catalog, so this is a lookup and not a second ordered list.
_IMPLEMENTATIONS = {
    "asr": ASRFeature,
    "summary": SummaryFeature,
    "mindmap": MindmapFeature,
    "topic_segmentation": SegmentationFeature,
    "video_analytics": VideoAnalyticsFeature,
    "board_ocr": BoardOCRFeature,
    "content_search": ContentSearchFeature,
    "qa": QAFeature,
    "grading": GradingFeature,
    "report": ReportFeature,
}


def register_builtin_features() -> None:
    missing = [fid for fid in FEATURE_IDS if fid not in _IMPLEMENTATIONS]
    if missing:
        raise ValueError(
            f"Catalog features with no implementation: {missing}. Add the class "
            "to model_manager/features/builtins.py::_IMPLEMENTATIONS."
        )
    for fid in FEATURE_IDS:
        if fid not in REGISTRY:
            register(_IMPLEMENTATIONS[fid]())
    logger.info("Registered built-in features: %s", sorted(REGISTRY))
