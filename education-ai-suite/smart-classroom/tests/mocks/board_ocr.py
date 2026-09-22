from unittest.mock import MagicMock


def make_board_ocr_mocks(start_raises=None, stop_raises=None):
    """Return (start_mock, stop_mock) standing in for board OCR functions.

    start_raises / stop_raises: exceptions those calls should raise.
    """
    start = MagicMock(name="start_board_ocr")
    stop = MagicMock(name="stop_board_ocr")
    if start_raises is not None:
        start.side_effect = start_raises
    if stop_raises is not None:
        stop.side_effect = stop_raises
    return start, stop