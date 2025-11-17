"""Extra tests for VmsService covering success and failure paths."""
import pytest
from unittest.mock import patch, MagicMock
from service.vms_service import VmsService

class DummyAsyncStream:
    def __init__(self, chunks):
        async def gen():
            for c in chunks:
                yield c
        # body_iterator is an async iterable object directly (accessed without call)
        self.body_iterator = gen()

@pytest.mark.asyncio
async def test_upload_video_to_summarizer_success(monkeypatch):
    vs = VmsService(frigate_service=MagicMock(), summarization_service=MagicMock())
    vs.vss_summary_url = "http://dummy-summary"
    vs.vss_search_url = "http://dummy-search"
    dummy_stream = DummyAsyncStream([b"x" * 200])
    vs.frigate_service.get_clip_from_timestamps.return_value = dummy_stream
    vs.summarization_service.video_upload.return_value = {"videoId": "vid123"}
    resp = await vs.upload_video_to_summarizer("cam1", 1.0, 2.0, False)
    assert resp["status"] == 200
    assert resp["message"] == "vid123"

@pytest.mark.asyncio
async def test_upload_video_to_summarizer_small_file(monkeypatch):
    vs = VmsService(frigate_service=MagicMock(), summarization_service=MagicMock())
    vs.vss_summary_url = "http://dummy-summary"
    dummy_stream = DummyAsyncStream([b"x" * 10])  # too small triggers 404
    vs.frigate_service.get_clip_from_timestamps.return_value = dummy_stream
    resp = await vs.upload_video_to_summarizer("cam1", 1.0, 2.0, False)
    assert resp["status"] == 404

@pytest.mark.asyncio
async def test_summarize_pipeline_failure(monkeypatch):
    vs = VmsService(frigate_service=MagicMock(), summarization_service=MagicMock())
    vs.vss_summary_url = "http://dummy-summary"
    # upload succeeds
    dummy_stream = DummyAsyncStream([b"x" * 200])
    vs.frigate_service.get_clip_from_timestamps.return_value = dummy_stream
    vs.summarization_service.video_upload.return_value = {"videoId": "vid999"}
    vs.summarization_service.create_summary.return_value = {}  # missing pipeline id
    resp = await vs.summarize("cam1", 1.0, 2.0)
    assert resp["status"] == 500

def test_summary_empty_result(monkeypatch):
    vs = VmsService(frigate_service=MagicMock(), summarization_service=MagicMock())
    vs.vss_summary_url = "http://dummy-summary"
    # The VmsService.summary method calls the module-level summarization_service, not the instance attribute.
    # Patch the global to avoid an HTTP request and return a controlled empty summary result.
    monkeypatch.setattr(
        "service.vms_service.summarization_service.get_summary_result",
        lambda pipeline_id, base_url: {
            "frameSummaries": [
                {
                    "startFrame": 0,
                    "endFrame": 10,
                    "status": "ok",
                    "summary": None,
                }
            ],
            "summary": None,
        },
    )
    out = vs.summary("sum123")
    assert "Final summary is being generated" in out["summary"]
    assert out["frameSummaries"][0]["status"] == "ok"

@pytest.mark.asyncio
async def test_search_embeddings_success(monkeypatch):
    vs = VmsService(frigate_service=MagicMock(), summarization_service=MagicMock())
    vs.vss_search_url = "http://dummy-search"
    vs.vss_summary_url = "http://dummy-summary"
    dummy_stream = DummyAsyncStream([b"x" * 200])
    vs.frigate_service.get_clip_from_timestamps.return_value = dummy_stream
    vs.summarization_service.video_upload.return_value = {"videoId": "vidAB"}
    # Patch requests.post inside module
    with patch("service.vms_service.requests.post", return_value=MagicMock(json=lambda: {"message": "ok"}, raise_for_status=lambda: None)):
        resp = await vs.search_embeddings("cam1", 1.0, 2.0)
        assert resp["status"] == 200
        assert resp["video_id"] == "vidAB"
