import requests
import logging
from utils.config_loader import config
from utils.topic_faiss_indexer import parse_transcript_lines, build_topic_text

logger = logging.getLogger(__name__)

# Explicitly bypass any system/corporate proxy for localhost calls.
# The content-search service runs on 127.0.0.1; going through a proxy
# causes 403 Forbidden responses from the proxy itself.
_NO_PROXY = {"http": None, "https": None}


class ContentSearchClient:
    """Thin synchronous client for the content-search microservice.

    Ingest endpoint:  POST /api/v1/object/ingest-text
    Search endpoint:  POST /api/v1/object/search
    """

    def __init__(self):
        host = config.content_search.host_addr
        port = config.content_search.port
        self.base_url = f"http://{host}:{port}"
        self.ingest_url = f"{self.base_url}/api/v1/object/ingest-text"
        self.search_url = f"{self.base_url}/api/v1/object/search"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_results(raw_results: list) -> list:
        results = []
        for item in raw_results:
            meta = item.get("meta", {})
            if item.get("score") is not None:
                score = float(item["score"]) / 100.0
            else:
                score = 1.0 - float(item.get("distance", 1.0))
            results.append({
                "score": score,
                "session_id": meta.get("session_id", ""),
                "topic": meta.get("topic", ""),
                "start_time": meta.get("start_time"),
                "end_time": meta.get("end_time"),
                "text": meta.get("text", ""),
            })
        return results

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_topics(self, session_id: str, topics: list, transcript_text: str) -> int:
        """Ingest LLM-generated topics into the content-search service.

        The LLM segmentation is the chunking step.  Each topic is sent as a
        single document (``ingest-text`` embeds it as one vector, no further
        splitting).  ``source: topic-search`` is the tag that later scopes
        retrieval to timestamped transcriptions only, excluding other
        content-search artifacts (video frames, PDFs, etc.).

        Returns the number of topics successfully ingested.
        """
        transcript_lines = parse_transcript_lines(transcript_text)
        ingested = 0

        for topic in topics:
            raw_text = build_topic_text(topic, transcript_lines)
            if not raw_text.strip():
                continue

            payload = {
                "text": f"Topic: {topic['topic']}. {raw_text}",
                "meta": {
                    "source": "topic-search",
                    "session_id": session_id,
                    "topic": topic["topic"],
                    "start_time": topic["start_time"],
                    "end_time": topic["end_time"],
                    "text": raw_text,
                },
            }

            try:
                response = requests.post(self.ingest_url, json=payload, timeout=30.0, proxies=_NO_PROXY)
                response.raise_for_status()
                ingested += 1
            except Exception as e:
                logger.warning(
                    "Content-search ingest failed for topic '%s': %s",
                    topic.get("topic", ""), e,
                )

        logger.info(
            "Content-search ingest: %d/%d topics ingested for session %s",
            ingested, len(topics), session_id,
        )
        return ingested

    def search_topics(self, query: str, top_k: int = 5) -> list | None:
        """Search for topics relevant to *query* across all ingested sessions."""
        payload = {
            "query": query,
            "max_num_results": top_k,
            "filter": {
                "source": "topic-search",
            },
        }

        try:
            response = requests.post(self.search_url, json=payload, timeout=15.0, proxies=_NO_PROXY)
            response.raise_for_status()
            data = response.json()
            raw_results = data.get("data", {}).get("results", [])
            return self._map_results(raw_results)
        except Exception as e:
            logger.warning("Content-search search failed, will fall back to FAISS: %s", e)
            return None
