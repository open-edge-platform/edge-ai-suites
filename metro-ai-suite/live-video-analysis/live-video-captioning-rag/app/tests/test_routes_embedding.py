# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.routes.embedding."""

from unittest.mock import AsyncMock, patch
from fastapi import HTTPException


class TestEmbeddingEndpoint:
    """POST /api/embeddings endpoint."""

    def test_success_response(self, client):
        with patch(
            "backend.routes.embedding.process_embeddings",
            AsyncMock(return_value="embedding-id-1"),
        ):
            resp = client.post(
                "/api/embeddings",
                json={
                    "image_data": "base64data",
                    "metadata": {"result": "A busy intersection"},
                },
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "status": "success",
            "message": "Embedding processed and stored successfully.",
            "id": "embedding-id-1",
        }

    def test_rejects_empty_image_data(self, client):
        resp = client.post(
            "/api/embeddings",
            json={"image_data": "   ", "metadata": {"result": "caption"}},
        )

        assert resp.status_code == 422
        assert "cannot be empty" in resp.json()["detail"].lower()

    def test_maps_value_error_to_422(self, client):
        with patch(
            "backend.routes.embedding.process_embeddings",
            AsyncMock(side_effect=ValueError("bad metadata")),
        ):
            resp = client.post(
                "/api/embeddings",
                json={"image_data": "abc", "metadata": {"result": ""}},
            )

        assert resp.status_code == 422
        assert resp.json()["detail"] == "bad metadata"

    def test_maps_unexpected_error_to_500(self, client):
        with patch(
            "backend.routes.embedding.process_embeddings",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            resp = client.post(
                "/api/embeddings",
                json={"image_data": "abc", "metadata": {"result": "caption"}},
            )

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to process embedding."

    def test_reraises_http_exception_from_service(self, client):
        with patch(
            "backend.routes.embedding.process_embeddings",
            AsyncMock(side_effect=HTTPException(status_code=418, detail="teapot")),
        ):
            resp = client.post(
                "/api/embeddings",
                json={"image_data": "abc", "metadata": {"result": "caption"}},
            )

        assert resp.status_code == 418
        assert resp.json()["detail"] == "teapot"


class TestEmbeddingValidation:
    """Unit tests for internal payload validation helper."""

    def test_rejects_non_dict_metadata(self, client):
        from backend.routes.embedding import _validate_request_payload

        class _Req:
            image_data = "abc"
            metadata = ["not", "a", "dict"]

        try:
            _validate_request_payload(_Req())
            assert False, "Expected HTTPException for non-dict metadata"
        except HTTPException as exc:
            assert exc.status_code == 422
            assert "valid json object" in exc.detail.lower()
