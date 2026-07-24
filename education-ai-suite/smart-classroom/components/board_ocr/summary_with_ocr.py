from components.board_ocr.feature_base import Capability, FeatureModule
from api.board_ocr import board_ocr_router

"""Summary with OCR feature module. Placeholder for future feature based design"""
class SummaryWithOcrFeature(FeatureModule):
    id = "summary_with_ocr"
    requires = [Capability.OCR, Capability.TEXT_GEN]
    depends_on = ["summary"]
    router = board_ocr_router

    def build(self) -> None:
        # The board OCR pipeline is owned by the module-level controller in
        # components.board_ocr.board_ocr_pipeline. It runs as a twin of the
        # VA content pipeline: endpoints.py starts it when the content pipeline
        # starts and stops it when the content pipeline stops or reaches EOS.
        # This feature therefore does not own the pipeline lifecycle.
        pass

    def teardown(self) -> None:
        pass

    def ui_descriptor(self) -> dict:
        return {"panel": "board-ocr", "tab": "post-class"}
