#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""WHEP signalling proxy and stream readiness."""

import requests
from flask import Response, jsonify, request

from config import MEDIAMTX_URL, app

_WHEP_METHODS = ["OPTIONS", "GET", "POST", "PATCH", "DELETE"]




def _proxy_whep(upstream_url, peer_id):
    excluded = {"host", "content-length"}
    headers = {k: v for k, v in request.headers.items() if k.lower() not in excluded}
    try:
        resp = requests.request(
            request.method,
            upstream_url,
            headers=headers,
            data=request.get_data(),
            timeout=15,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502

    out_headers = [("Access-Control-Expose-Headers", "Link, Location")]
    # The Link header carries the ICE server list; without it the browser
    # gathers only host candidates and video never starts remotely.
    link_val = resp.headers.get("Link")
    if link_val:
        out_headers.append(("Link", link_val))

    location = resp.headers.get("Location")
    if location:
        # The upstream Location names the session resource used for ICE
        # trickle (PATCH) and teardown (DELETE), typically
        # "/<peer_id>/whep/<session>". Rewrite it onto this proxy's own
        # route while preserving the session identifier: take the segment
        # following "/whep/" and emit "whep/<peer_id>/<session>". Dropping
        # the session breaks every subsequent PATCH/DELETE.
        session_seg = location.rsplit("/whep/", 1)[-1]
        out_headers.append(("Location", "whep/%s/%s" % (peer_id, session_seg)))

    content_type = resp.headers.get("Content-Type")
    if content_type:
        out_headers.append(("Content-Type", content_type))

    return Response(resp.content, status=resp.status_code, headers=out_headers)


@app.route("/whep/<peer_id>", methods=_WHEP_METHODS)
def whep_proxy(peer_id):
    return _proxy_whep(f"{MEDIAMTX_URL}/{peer_id}/whep", peer_id)


@app.route("/whep/<peer_id>/<session>", methods=_WHEP_METHODS)
def whep_session_proxy(peer_id, session):
    return _proxy_whep(f"{MEDIAMTX_URL}/{peer_id}/whep/{session}", peer_id)


@app.route("/api/stream/ready/<peer_id>")
def api_stream_ready(peer_id):
    url = f"{MEDIAMTX_URL}/{peer_id}/whep"
    try:
        r = requests.options(url, timeout=5)
        return jsonify({"ready": r.status_code != 404, "status": r.status_code})
    except requests.RequestException:
        return jsonify({"ready": False, "status": 0})


# --------------------------------------------------------------------------
# 9. Entry point
# --------------------------------------------------------------------------

