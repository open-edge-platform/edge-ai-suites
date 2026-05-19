# SPDX-FileCopyrightText: (C) 2024 - 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import json
import socket
import threading

import numpy as np
import vdms

from controller.reid import ReIDDatabase
from scene_common import log

DEFAULT_HOSTNAME = os.getenv("VDMS_HOSTNAME", "vdms.scenescape.intel.com")
DEFAULT_CONFIDENCE_THRESHOLD = float(os.getenv("VDMS_CONFIDENCE_THRESHOLD", "0.8"))
DIMENSIONS = int(os.getenv("VDMS_DIMENSIONS", "512"))
K_NEIGHBORS = 1
SCHEMA_NAME = "reid_vector"
SIMILARITY_METRIC = "L2"

class VDMSDatabase(ReIDDatabase):
  def __init__(self, set_name=SCHEMA_NAME,
               similarity_metric=SIMILARITY_METRIC, dimensions=DIMENSIONS,
               confidence_threshold=DEFAULT_CONFIDENCE_THRESHOLD):
    self.db = vdms.vdms(
      use_tls=True,
      ca_cert_file="/run/secrets/certs/scenescape-ca.pem",
      client_cert_file="/run/secrets/certs/scenescape-vdms-c.crt",
      client_key_file="/run/secrets/certs/scenescape-vdms-c.key"
    )
    self.set_name = set_name
    self.similarity_metric = similarity_metric
    self.dimensions = dimensions
    self.confidence_threshold = confidence_threshold
    self.lock = threading.Lock()
    return

  def sendQuery(self, query, blob=None):
    """
    Helper function for handling the responses from sending queries to VDMS. There are three
    possible responses from VDMS when sending the query.
      - "NOT CONNECTED", if the database connection is not active
      - None, if the response fails to receive a packet
      - (response, res_arr), if query gets a response from VDMS

    @param   query      The list of queries to send to VDMS
    @param   blob       Blobs of data to send with queries (optional)
    @return  responses  The response dict from VDMS
    """
    responses = []
    response_blob = []
    with self.lock:
      if blob:
        query_response = self.db.query(query, blob)
      else:
        query_response = self.db.query(query)
    if query_response and query_response != "NOT CONNECTED":
      response_blob = query_response[1]
      # Check for transaction-level failure
      if (len(query_response[0]) == 1
          and isinstance(query_response[0][0], dict)
          and 'FailedCommand' in query_response[0][0]):
        log.warning(f"VDMS transaction failed: {query_response[0][0]}")
        return responses, response_blob
      for (item, response) in zip(query, query_response[0]):
        query_type = next(iter(item))
        response_data = response.get(query_type, {})
        responses.append(response_data)
    else:
      log.warning(f"Failed to send query to VDMS container: {query}")
    return responses, response_blob

  def connect(self, hostname=DEFAULT_HOSTNAME):
    try:
      self.db.connect(hostname)
      if not self.findSchema(self.set_name):
        self.addSchema(self.set_name, self.similarity_metric, self.dimensions)
    except socket.error as e:
      log.warning(f"Failed to connect to VDMS container: {e}")
    return

  def addSchema(self, set_name, similarity_metric, dimensions):
    query = [{
      "AddDescriptorSet": {
        "name": f"{set_name}",
        "metric": f"{similarity_metric}",
        "dimensions": dimensions
      }
    }]
    response, _ = self.sendQuery(query)
    if response and response[0].get('status') != 0:
      log.warning(
        f"Failed to add the descriptor set to the database. Received response {response[0]}")
    return

  def addEntry(self, uuid, rvid, object_type, reid_vectors, set_name=SCHEMA_NAME, **metadata):
    """
    Add entries to database with visual embeddings and optional semantic metadata.
    Implements schema-less metadata storage for flexible attribute evolution.

    @param   uuid         Unique ID for the object
    @param   rvid         ID of the object from the motion tracker
    @param   object_type  Class of the object (Person, Vehicle, etc.)
    @param   reid_vectors Re-ID embeddings produced by a detection model
    @param   set_name     Name of the set to add the new entry to
    @param   metadata     Optional semantic attributes (age, gender, color, etc.)
    @return  None
    """
    # Build properties with standard fields
    properties = {
      "uuid": f"{uuid}",
      "rvid": f"{rvid}",
      "type": f"{object_type}"
    }

    # Add semantic metadata attributes (schema-less)
    # Metadata can include: age, gender, color, make, model, confidence_scores, etc.
    for key, value in metadata.items():
      if isinstance(value, dict):
        # For metadata dicts with 'label' and optional confidence, store ONLY the label
        # This ensures VDMS constraints can match properly (e.g., gender=['==', 'Male'])
        # Example: {'label': 'Male', 'confidence': 0.95} → store 'Male'
        if 'label' in value:
          properties[key] = str(value['label'])
          log.debug(f"[VDMS] addEntry: Extracted label '{value['label']}' from {key} metadata dict")
        else:
          # If no label, serialize as JSON
          properties[key] = json.dumps(value)
          log.debug(f"[VDMS] addEntry: Serialized {key} as JSON (no label field)")
      else:
        # Store as string
        properties[key] = str(value)

    query = {
      "AddDescriptor": {
        "set": f"{set_name}",
        "properties": properties
      }
    }
    # Convert vectors to JSON-serializable format (float32 -> float) and to bytes
    # VDMS API expects: query([q1, q2, ...], [blob1, blob2, ...])
    # Blobs are consumed sequentially, one per AddDescriptor query (flat list)
    descriptor_blobs = []
    add_query = []
    for reid_vector in reid_vectors:
      # Ensure vector is properly formatted as 1D array of float32
      # reid_vector might be shape (1, 256) from moving_object, need to flatten to (256,)
      vec_array = np.asarray(reid_vector, dtype="float32").flatten()
      if vec_array.shape[0] != self.dimensions:
        log.warning(f"addEntry: Expected vector shape ({self.dimensions},) but got {vec_array.shape}, skipping this vector")
        continue
      descriptor_blobs.append(vec_array.tobytes())
      # Create query dict for each vector
      add_query.append({
        "AddDescriptor": {
          "set": f"{set_name}",
          "properties": properties.copy()
        }
      })

    response, _ = self.sendQuery(add_query, descriptor_blobs)  # Flat list of blobs
    if response:
      success_count = 0
      for item in response:
        if item.get('status') == 0:
          success_count += 1
        else:
          log.warning(
            f"Failed to add the descriptor to the database. Received response {item}")
    else:
      log.error(f"addEntry: No response from VDMS when adding {len(add_query)} vectors")
    return

  def findSchema(self, set_name):
    query = [{
      "FindDescriptorSet": {
        "set": f"{set_name}"
      }
    }]
    response, _ = self.sendQuery(query)
    if response and response[0].get('status') == 0 and response[0].get('returned') > 0:
      return True
    return False

  def _build_query_constraints(self, object_type, **constraints):
    """
    Build query constraints for TIER 1 metadata filtering.

    VDMS constraint model: Only supports AND operations between property constraints.
    Constraint format for each property: [operator, value] for single constraint,
    or [op1, val1, op2, val2] for range constraint (e.g. ">=5" AND "<=10").

    Constraint routing logic:
    - Object type is always AND constraint (required field)
    - If value is dict with 'confidence' key (new metadata format):
      - confidence >= threshold (0.8): AND constraints (strict filtering in TIER 1)
      - confidence < threshold (0.8): IGNORED (relies on TIER 2 vector similarity for flexible matching)
      - Extract 'label' field for VDMS query value
    - If value is non-dict or dict without confidence (legacy format):
      - IGNORED (relies on TIER 2 vector similarity for matching)
    - Non-numeric values: IGNORED (relies on TIER 2 vector similarity)

    Note: Low-confidence and unspecified constraints are intentionally omitted from TIER 1
    filtering, allowing TIER 2 vector similarity search to provide flexible,
    confidence-aware matching. This simplification avoids VDMS limitations with complex
    OR constraint expressions across multiple properties.

    @param   object_type  Class of the object (Person, Vehicle, etc.)
    @param   constraints  Optional metadata filters (key-value pairs, may be dicts with label/confidence)
    @return  query_constraints  Dictionary with "type" and optional high-confidence AND fields
    """
    # TIER 1: Build dynamic constraints for metadata filtering
    # Object type is always filtered (AND constraint - required)
    query_constraints = {
      "type": ["==", f"{object_type}"]
    }

    log.debug(f"[VDMS] Building constraints for object_type={object_type}, threshold={self.confidence_threshold}")
    log.debug(f"[VDMS] Input constraints: {constraints}")

    # Apply only high-confidence constraints
    if constraints:
      for key, value in constraints.items():
        if value is None:
          log.debug(f"[VDMS] Skipping {key}: value is None")
          continue

        # Extract actual value and confidence from metadata dict
        actual_value = value
        confidence = None

        # Handle new metadata format: {label: <data>, model_name: <model>, confidence: <score>}
        if isinstance(value, dict) and 'label' in value:
          actual_value = value['label']
          confidence = value.get('confidence', None)
          log.debug(f"[VDMS] {key}: dict format - label={actual_value}, confidence={confidence}")
        else:
          log.debug(f"[VDMS] {key}: non-dict or no label - value={value}, type={type(value)}")

        # Only apply high-confidence constraints (>= 0.8)
        try:
          # If confidence is available, check if it meets threshold
          if confidence is not None:
            conf_value = float(confidence)
            # If confidence >= threshold, treat as AND constraint (strict matching)
            if conf_value >= self.confidence_threshold:
              query_constraints[key] = ["==", str(actual_value)]
              log.debug(f"[VDMS] ✓ ADDED: {key}={actual_value} (confidence={conf_value} >= {self.confidence_threshold})")
            else:
              # If confidence < threshold, ignore (rely on TIER 2 vector similarity)
              log.debug(f"[VDMS] ✗ IGNORED: {key} (confidence={conf_value} < {self.confidence_threshold}, will use TIER 2)")
          else:
            # No confidence available - skip this constraint, rely on TIER 2
            log.debug(f"[VDMS] ✗ IGNORED: {key} (no confidence available, will use TIER 2)")
        except (ValueError, TypeError):
          # Confidence value not convertible to float, ignore
          log.debug(f"[VDMS] ✗ IGNORED: {key} (confidence not convertible to float)")
          pass

    log.debug(f"[VDMS] Final TIER 1 query_constraints: {query_constraints}")
    return query_constraints

  def findMatches(self, object_type, reid_vectors, set_name=SCHEMA_NAME,
                   k_neighbors=K_NEIGHBORS, **constraints):
    """
    2-Tier Hybrid Search: TIER 1 (metadata filtering) + TIER 2 (vector similarity)

    @param   object_type  Class of the source of the reid vector (Person, Vehicle, etc.)
    @param   reid_vectors Re-ID embeddings produced by a detection model
    @param   set_name     Name of the set to find similarity scores
    @param   k_neighbors  Number of similar entries to return
    @param   constraints  Optional metadata filters built as VDMS constraint expressions
    @return  result       Entries with the closest similarity scores
    """
    log.debug(f"[VDMS] findMatches called: object_type={object_type}, k_neighbors={k_neighbors}")
    log.debug(f"[VDMS] findMatches constraints received: {constraints}")

    # TIER 1: Build dynamic constraints for metadata filtering
    query_constraints = self._build_query_constraints(object_type, **constraints)

    find_query = {
      "FindDescriptor": {
        "set": f"{set_name}",
        "constraints": query_constraints,
        "k_neighbors": k_neighbors,
        "results": {
          "list": [
            "uuid",
            "rvid",
            "_distance",
          ],
          "blob": False
        }
      }
    }

    log.debug(f"[VDMS] Executing TIER 1 find with constraints: {query_constraints}")

    # TIER 2: Vector similarity search on filtered candidates
    blob = []
    for reid_vector in reid_vectors:
      # Ensure vector is float32, then convert to bytes for VDMS
      vec_array = np.array(reid_vector, dtype="float32")
      blob.append(vec_array.tobytes())  # Flat list of blobs

    query = [find_query] * len(reid_vectors)
    response, _ = self.sendQuery(query, blob)

    log.debug(f"[VDMS] Raw VDMS response (truncated): status={response[0].get('status') if response else 'None'}, returned={response[0].get('returned') if response else 'None'}")
    if response and len(response) > 0:
      log.debug(f"[VDMS] Full first response: {response[0]}")

    if response:
      result = [
        item.get('entities')
        for item in response
        if (item.get('status') == 0 and item.get('returned') > 0)
      ]
      log.debug(f"[VDMS] findMatches returned {len(result)} result(s) from {len(reid_vectors)} vector(s)")
      return result
    log.debug("[VDMS] findMatches returned None (no response from VDMS)")
    return None
