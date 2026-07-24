import logging

from .asr_feature import ASRFeature
from .content_search_feature import ContentSearchFeature
from .mindmap_feature import MindmapFeature
from .qa_feature import QAFeature
from .report_feature import ReportFeature
from .registry import REGISTRY, register
from .segmentation_feature import SegmentationFeature
from .summary_feature import SummaryFeature
from .va_feature import VideoAnalyticsFeature

logger = logging.getLogger(__name__)

_BUILTIN_FEATURES = [
    ASRFeature,
    SummaryFeature,
    MindmapFeature,
    SegmentationFeature,
    VideoAnalyticsFeature,
    ContentSearchFeature,
    QAFeature,
    ReportFeature,
]


def register_builtin_features() -> None:
    for feature_cls in _BUILTIN_FEATURES:
        if feature_cls.id not in REGISTRY:
            register(feature_cls())
    logger.info("Registered built-in features: %s", sorted(REGISTRY))
