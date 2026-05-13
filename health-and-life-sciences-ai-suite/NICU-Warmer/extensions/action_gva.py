"""gvapython callback for Action Recognition inside DLSPS pipeline.

This module is loaded by gvapython inside the DL Streamer pipeline:

  gvapython class=ActionCallback function=process
      module=/extensions/action_gva.py name=action_callback

Architecture (action-recognition-0001):
  - Encoder: runs every frame, produces a 512-dim feature vector
  - Decoder: runs every 16 accumulated encoder features → 400-class softmax
  - Labels:  Kinetics-400 action label file

The raw Kinetics-400 labels are mapped to NICU-relevant activity categories
so the UI shows meaningful activities like "Arm Movement", "Patient Handling",
"Reaching/Adjusting" rather than "dancing ballet" or "spinning poi".

Additionally, frame-differencing motion analysis detects:
  - Patient stillness (very low inter-frame change)
  - Significant movement / position change (high inter-frame change)
These override or augment the model's output for more accurate NICU monitoring.

The callback attaches {"action": {"activities": [...], ...}}
via frame.add_message() for MQTTPublisher.
"""
from __future__ import annotations

import json
import logging
from collections import deque
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger("ActionCallback")
logger.setLevel(logging.INFO)

# Encoder expects 224x224 BGR, normalised to [0,1]
ENCODER_SIZE = 224
SEQUENCE_LEN = 16   # decoder accumulates 16 encoder features
TOP_K = 15          # consider top-15 raw labels for better category coverage

# ---------------------------------------------------------------------------
# Motion analysis thresholds  (% of pixels that changed > PIXEL_THRESH)
# Using percentage-of-changed-pixels instead of mean diff makes the
# analyser much more sensitive to *localized* movements (hand raise,
# arm wiggle) which only affect ~5-15 % of the frame.
# ---------------------------------------------------------------------------
MOTION_PIXEL_THRESH = 5         # pixel diff magnitude to count as "changed"
MOTION_STILL_PCT = 0.10         # <0.10 % changed pixels → patient is truly still
MOTION_LOW_PCT = 0.5            # 0.10-0.5 % → low (subtle breathing/twitch)
MOTION_MOD_PCT = 2.0            # 0.5-2 % → moderate (hand raise, head turn)
                                 # >2 %    → high (flip, repositioning)
MOTION_HISTORY_LEN = 30         # frames of motion history for trend
MOTION_ROI_FRAC = (0.10, 0.15, 0.90, 0.85)  # (top, left, bottom, right) — wider patient area

# ---------------------------------------------------------------------------
# NICU Activity Mapping — Kinetics-400 label → NICU category
# ---------------------------------------------------------------------------
# Comprehensive mapping of ALL Kinetics-400 labels to NICU-relevant activity
# categories.  Probabilities are aggregated per category and *renormalised*
# so the UI shows meaningful relative confidence (not tiny absolute values).

_NICU_CATEGORIES: dict[str, list[str]] = {
    "Arm Movement": [
        "stretching arm", "exercising arm", "arm wrestling",
        "swinging legs", "stretching leg", "pull ups", "push up",
        "clapping", "front raises", "hula hooping",
        # dance / rhythmic body movement ≈ limb motion
        "dancing ballet", "dancing gangnam style", "dancing charleston",
        "dancing macarena", "swing dancing", "salsa dancing",
        "country line dancing", "tango dancing", "tap dancing",
        "jumpstyle dancing", "breakdancing", "belly dancing",
        "capoeira", "krumping", "robot dancing",
        "spinning poi", "tai chi", "cheerleading",
        "cartwheeling", "gymnastics tumbling", "somersaulting",
        "trapezing", "side kick", "high kick",
        "exercising with an exercise ball", "doing aerobics",
        "skipping rope", "juggling balls", "juggling fire",
        "juggling soccer ball", "contact juggling",
        "sword fighting", "wrestling", "punching bag",
        "punching person (boxing)",
    ],
    "Hand Movement": [
        "shaking hands", "washing hands", "rock scissors paper",
        "tapping pen", "tapping guitar", "playing cards",
        "playing chess", "playing controller", "playing monopoly",
        "playing poker", "folding paper", "folding clothes",
        "folding napkins", "writing", "drawing",
        "knitting", "crocheting", "weaving basket",
        "applauding", "applying cream", "brushing hair",
        "brushing teeth", "finger snapping", "drumming fingers",
        "waxing back", "waxing chest", "waxing eyebrows", "waxing legs",
        "doing nails", "cutting nails", "filling eyebrows",
        "fixing hair", "curling hair", "braiding hair",
        "dying hair", "shaving head", "shaving legs",
        "trimming or shaving beard",
        "sharpening knives", "sharpening pencil",
        "shuffling cards", "ripping paper", "shredding paper",
        "counting money", "texting",
        "using computer", "using remote controller (not gaming)",
        "sign language interpreting", "tying bow tie",
        "tying knot (not on a tie)", "tying tie",
        "making jewelry", "bookbinding", "spray painting",
        "brush painting", "clay pottery making",
        "sticking tongue out",
    ],
    "Patient Handling": [
        "carrying baby", "hugging", "kissing",
        "wrapping present",  # proxy for swaddling
        "massaging back", "massaging feet", "massaging legs",
        "massaging person's head", "bandaging",
        "petting animal (not cat)", "petting cat",
        "grooming dog", "grooming horse",
        "getting a haircut", "getting a tattoo",
        "tickling",
    ],
    "Reaching / Adjusting": [
        "picking fruit", "opening bottle", "opening present",
        "pushing cart", "pushing wheelchair", "pushing car",
        "assembling computer", "building cabinet", "building shed",
        "changing oil", "changing wheel", "checking tires",
        "stacking dice", "setting table",
        "decorating the christmas tree",
        "moving furniture", "making bed",
        "ironing", "doing laundry", "sweeping floor",
        "mopping floor", "cleaning floor", "cleaning windows",
        "cleaning gutters", "cleaning pool", "cleaning shoes",
        "cleaning toilet", "sanding floor",
        "unboxing", "unloading truck",
        "laying bricks", "plastering", "digging",
        "shoveling snow", "welding", "planting trees",
        "trimming trees", "watering plants", "mowing lawn",
        "arranging flowers", "garbage collecting",
        "pumping gas", "climbing ladder",
        "blowing leaves",
    ],
    "Patient Distress": [
        "crying", "sneezing", "coughing", "yawning",
        "blowing nose", "gargling",
        "baby waking up", "crawling baby",
        "headbutting", "headbanging", "faceplanting",
    ],
    "Resting / Still": [
        "meditating", "yoga",
        "waiting in line", "slacklining",
        "smoking", "smoking hookah",
        "taking a shower", "washing feet", "washing hair",
        "washing dishes",
    ],
    "Walking / Moving": [
        "walking the dog", "marching", "jogging",
        "running on treadmill", "roller skating",
        "riding or walking with horse", "skateboarding",
        "biking through snow", "riding a bike", "riding mountain bike",
        "riding scooter", "riding unicycle", "hoverboarding",
        "using segway", "parkour",
        "climbing a rope", "climbing tree", "rock climbing",
        "ice climbing", "abseiling",
        "hopscotch", "lunge", "long jump", "high jump",
        "triple jump", "hurdling", "pole vault", "vault",
        "bungee jumping", "jumping into pool",
        "bouncing on trampoline",
    ],
    "Bending / Leaning": [
        "bending back", "bending metal", "deadlifting", "situp",
        "snatch weight lifting", "bench pressing",
        "clean and jerk", "squat",
        "hammer throw", "javelin throw", "shot put",
        "throwing axe", "throwing ball", "throwing discus",
        "chopping wood", "drop kicking",
        "kicking field goal", "kicking soccer ball",
        "stomping grapes",
    ],
    "Monitoring / Observing": [
        "answering questions", "testifying",
        "news anchoring", "presenting weather forecast",
        "reading book", "reading newspaper",
        "auctioning", "busking", "singing", "whistling",
        "beatboxing", "recording music",
        "laughing", "celebrating",
        "giving or receiving award",
        "tasting beer", "tasting food",
        "drinking", "drinking beer", "drinking shots",
        "dining", "eating burger", "eating cake", "eating carrots",
        "eating chips", "eating doughnuts", "eating hotdog",
        "eating ice cream", "eating spaghetti", "eating watermelon",
        "sniffing",
    ],
    "Food / Equipment Prep": [
        "baking cookies", "cooking chicken", "cooking egg",
        "cooking on campfire", "cooking sausages",
        "scrambling eggs", "frying vegetables",
        "flipping pancake", "making a cake", "making a sandwich",
        "making pizza", "making sushi", "making tea",
        "making snowman",
        "cutting pineapple", "cutting watermelon",
        "peeling apples", "peeling potatoes",
        "breading or breadcrumbing", "grinding meat",
        "tossing salad", "bartending",
        "blowing out candles", "balloon blowing",
        "blowing glass", "carving pumpkin",
        "spraying", "extinguishing fire", "blasting sand",
        "shining shoes",
    ],
    "Sports / Recreation": [
        "archery", "bowling", "golf chipping", "golf driving",
        "golf putting", "disc golfing",
        "playing badminton", "playing basketball",
        "playing cricket", "playing ice hockey",
        "playing kickball", "playing paintball",
        "playing squash or racquetball", "playing tennis",
        "playing volleyball",
        "catching fish", "catching or throwing baseball",
        "catching or throwing frisbee", "catching or throwing softball",
        "dribbling basketball", "dunking basketball",
        "shooting basketball", "shooting goal (soccer)",
        "passing American football (in game)",
        "passing American football (not in game)",
        "hitting baseball", "hockey stop",
        "hurling (sport)", "dodgeball",
        "surfing crowd", "surfing water", "water skiing",
        "water sliding", "windsurfing", "kitesurfing",
        "skiing (not slalom or crosscountry)",
        "skiing crosscountry", "skiing slalom", "ski jumping",
        "snowboarding", "snowkiting", "snowmobiling",
        "ice skating", "ice fishing", "bobsledding",
        "sled dog racing", "tobogganing",
        "canoeing or kayaking", "sailing", "jetskiing",
        "scuba diving", "snorkeling", "diving cliff",
        "springboard diving", "swimming backstroke",
        "swimming breast stroke", "swimming butterfly stroke",
        "paragliding", "parasailing", "skydiving",
        "flying kite", "training dog",
        "riding camel", "riding elephant",
        "riding mechanical bull", "riding mule",
        "motorcycling", "driving car", "driving tractor",
        "pumping fist", "slapping", "swinging on something",
        "milking cow", "shearing sheep", "feeding birds",
        "feeding fish", "feeding goats", "holding snake",
        "bee keeping", "egg hunting", "crossing river",
        "tossing coin",
    ],
    "Music": [
        "air drumming", "playing accordion", "playing bagpipes",
        "playing bass guitar", "playing cello", "playing clarinet",
        "playing cymbals", "playing didgeridoo", "playing drums",
        "playing flute", "playing guitar", "playing harmonica",
        "playing harp", "playing keyboard", "playing organ",
        "playing piano", "playing recorder", "playing saxophone",
        "playing trombone", "playing trumpet", "playing ukulele",
        "playing violin", "playing xylophone", "strumming guitar",
    ],
}

# Build reverse lookup: raw_label (lowercased) → nicu_category
_LABEL_TO_CATEGORY: dict[str, str] = {}
for _cat, _labels in _NICU_CATEGORIES.items():
    for _lbl in _labels:
        _LABEL_TO_CATEGORY[_lbl.lower()] = _cat


# ---------------------------------------------------------------------------
# Motion Analysis — frame differencing for stillness / large-movement detection
# ---------------------------------------------------------------------------

class _MotionAnalyser:
    """Lightweight frame-differencing to detect patient stillness and large movements.

    Uses **percentage-of-changed-pixels** rather than mean absolute diff.
    This makes the analyser much more sensitive to localized movements
    (hand raise, arm wiggle) that only affect a small region of the frame.
    """

    def __init__(self) -> None:
        self._prev_gray: np.ndarray | None = None
        self._history: deque[float] = deque(maxlen=MOTION_HISTORY_LEN)

    def update(self, bgr: np.ndarray) -> dict[str, Any]:
        """Compute motion from frame difference.

        Returns dict with:
            motion_level: "still" | "low" | "moderate" | "high"
            motion_magnitude: float (% of pixels changed above PIXEL_THRESH)
            motion_trend: "stable" | "increasing" | "decreasing"
        """
        h, w = bgr.shape[:2]
        top, left, bot, right = MOTION_ROI_FRAC
        roi = bgr[int(h * top):int(h * bot), int(w * left):int(w * right)]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # Downsample for speed
        small = cv2.resize(gray, (112, 112), interpolation=cv2.INTER_AREA)

        if self._prev_gray is None:
            self._prev_gray = small
            return {"motion_level": "unknown", "motion_magnitude": 0.0, "motion_trend": "stable"}

        diff = cv2.absdiff(self._prev_gray, small)
        self._prev_gray = small

        # Percentage of pixels whose diff exceeds MOTION_PIXEL_THRESH
        total_px = diff.shape[0] * diff.shape[1]
        changed_px = int(np.count_nonzero(diff > MOTION_PIXEL_THRESH))
        pct_changed = (changed_px / total_px) * 100.0  # 0-100 scale

        self._history.append(pct_changed)

        # Classify motion level
        if pct_changed < MOTION_STILL_PCT:
            level = "still"
        elif pct_changed < MOTION_LOW_PCT:
            level = "low"
        elif pct_changed < MOTION_MOD_PCT:
            level = "moderate"
        else:
            level = "high"

        # Trend: compare recent 5 frames vs prior 5 frames
        trend = "stable"
        if len(self._history) >= 10:
            recent = sum(list(self._history)[-5:]) / 5
            prior = sum(list(self._history)[-10:-5]) / 5
            if prior > 0.01 and recent > prior * 1.5:
                trend = "increasing"
            elif prior > 0.01 and recent < prior * 0.6:
                trend = "decreasing"

        return {"motion_level": level, "motion_magnitude": round(pct_changed, 2), "motion_trend": trend}


def _map_to_nicu(raw_labels: list[str], raw_probs: list[float],
                 motion: dict[str, Any] | None = None) -> dict[str, Any]:
    """Map raw Kinetics-400 top-K labels to NICU activity categories.

    Aggregates probabilities per NICU category, renormalises to relative
    percentages (so the UI shows 45% instead of 3.1%).

    When motion analysis is available:
      - "still" → forces "Resting / Still" as top category
      - "high"  → adds "Significant Movement" as top category
    """
    cat_scores: dict[str, float] = {}

    for label, prob in zip(raw_labels, raw_probs):
        lower = label.lower().strip()
        # Try exact match first, then substring
        category = _LABEL_TO_CATEGORY.get(lower)
        if category is None:
            for substr, cat in _LABEL_TO_CATEGORY.items():
                if substr in lower or lower in substr:
                    category = cat
                    break
        if category is None:
            category = "General Activity"

        cat_scores[category] = cat_scores.get(category, 0.0) + prob

    # Inject motion-based categories
    motion_level = (motion or {}).get("motion_level", "unknown")
    motion_mag = (motion or {}).get("motion_magnitude", 0.0)

    if motion_level == "still":
        # Patient is truly still — gentle nudge towards "Resting / Still"
        # but don't overwhelm the model's prediction
        cat_scores["Resting / Still"] = cat_scores.get("Resting / Still", 0.0) + 0.15
    elif motion_level == "high":
        # Large movement detected (possible flip, repositioning, distress)
        cat_scores["Significant Movement"] = 0.4
        cat_scores["Patient Distress"] = cat_scores.get("Patient Distress", 0.0) + 0.2
    elif motion_level == "moderate":
        # Moderate movement — boost movement-related categories slightly
        cat_scores["Arm Movement"] = cat_scores.get("Arm Movement", 0.0) + 0.1
        cat_scores["Hand Movement"] = cat_scores.get("Hand Movement", 0.0) + 0.05

    # Renormalise so scores sum to 1.0 (relative confidence)
    total = sum(cat_scores.values())
    if total > 0:
        cat_scores = {k: v / total for k, v in cat_scores.items()}

    # Sort by aggregated score
    ranked = sorted(cat_scores.items(), key=lambda x: x[1], reverse=True)

    activities = []
    for cat, score in ranked[:4]:
        activities.append({
            "activity": cat,
            "confidence": round(score, 4),
        })

    result: dict[str, Any] = {
        "activities": activities,
        "top_activity": activities[0]["activity"] if activities else "Unknown",
        "top_confidence": activities[0]["confidence"] if activities else 0.0,
        "status": "valid",
    }
    if motion:
        result["motion_level"] = motion_level
        result["motion_magnitude"] = motion_mag

    return result


class ActionCallback:
    """Called by gvapython for each frame in the DL Streamer pipeline.

    Constructor kwargs (passed via pipeline parameters):
        encoder_model: str — path to encoder .xml
        decoder_model: str — path to decoder .xml
        labels_file:   str — path to kinetics labels .txt
        device:        str — OpenVINO device (default "CPU")
    """

    def __init__(
        self,
        encoder_model: str = "/models/action/action-recognition-0001-encoder.xml",
        decoder_model: str = "/models/action/action-recognition-0001-decoder.xml",
        labels_file: str = "/models/action/kinetics.txt",
        device: str = "CPU",
    ) -> None:
        self._encoder_path = encoder_model
        self._decoder_path = decoder_model
        self._labels_file = labels_file
        self._device = device

        self._encoder: Any = None
        self._decoder: Any = None
        self._labels: list[str] = []

        # Rolling buffer of encoder feature vectors
        self._features: deque[np.ndarray] = deque(maxlen=SEQUENCE_LEN)
        self._frame_count = 0
        self._motion = _MotionAnalyser()
        self._latest_motion: dict[str, Any] = {}

        # Cache latest result so every frame has action data
        self._latest_result: dict[str, Any] = {
            "activities": [],
            "top_activity": "Warming Up",
            "top_confidence": 0.0,
            "status": "warming_up",
        }

        logger.info(
            "ActionCallback init: encoder=%s decoder=%s labels=%s device=%s",
            encoder_model, decoder_model, labels_file, device,
        )

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------
    def _load_models(self) -> None:
        if self._encoder is not None:
            return
        import openvino as ov

        core = ov.Core()
        try:
            self._encoder = core.compile_model(self._encoder_path, self._device)
            logger.info("Action encoder compiled on %s", self._device)
        except Exception:
            logger.warning("Action encoder compile failed on %s, using CPU", self._device)
            self._encoder = core.compile_model(self._encoder_path, "CPU")

        try:
            self._decoder = core.compile_model(self._decoder_path, self._device)
            logger.info("Action decoder compiled on %s", self._device)
        except Exception:
            logger.warning("Action decoder compile failed on %s, using CPU", self._device)
            self._decoder = core.compile_model(self._decoder_path, "CPU")

        # Load labels
        lpath = Path(self._labels_file)
        if lpath.exists():
            self._labels = [line.strip() for line in lpath.read_text().splitlines() if line.strip()]
            logger.info("Loaded %d action labels from %s", len(self._labels), lpath)
        else:
            logger.warning("Labels file not found: %s", lpath)

    # ------------------------------------------------------------------
    # Encoder: frame → 512-dim feature
    # ------------------------------------------------------------------
    def _encode_frame(self, bgr: np.ndarray) -> np.ndarray:
        """Resize to 224x224, normalise, run encoder → (512,) feature."""
        resized = cv2.resize(bgr, (ENCODER_SIZE, ENCODER_SIZE), interpolation=cv2.INTER_LINEAR)
        # HWC → CHW, float32, normalised [0,1]
        blob = resized.astype(np.float32).transpose(2, 0, 1) / 255.0
        blob = blob[np.newaxis, ...]  # (1, 3, 224, 224)

        out = self._encoder([blob])
        feat = out[self._encoder.output(0)]  # (1, 512, 1, 1)
        return feat.reshape(512)

    # ------------------------------------------------------------------
    # Decoder: 16 features → 400-class softmax
    # ------------------------------------------------------------------
    def _decode(self) -> dict[str, Any]:
        """Run decoder on accumulated features → NICU-mapped activity."""
        feats = np.array(list(self._features))  # (16, 512)
        inp = feats[np.newaxis, ...]  # (1, 16, 512)

        out = self._decoder([inp])
        logits = out[self._decoder.output(0)].flatten()  # (400,)

        # Softmax
        exp = np.exp(logits - np.max(logits))
        probs = exp / exp.sum()

        # Top-K raw labels
        top_idx = np.argsort(probs)[-TOP_K:][::-1]
        raw_labels = []
        raw_probs = []
        for idx in top_idx:
            label = self._labels[idx] if idx < len(self._labels) else f"class_{idx}"
            raw_labels.append(label)
            raw_probs.append(float(probs[idx]))

        # Map to NICU-relevant categories (with motion context)
        return _map_to_nicu(raw_labels, raw_probs, motion=self._latest_motion)

    # ------------------------------------------------------------------
    # gvapython entry point
    # ------------------------------------------------------------------
    def process(self, frame) -> bool:
        """Called once per frame by gvapython."""
        try:
            self._frame_count += 1
            self._load_models()

            # Extract BGR from GVA VideoFrame
            with frame.data() as image:
                vi = frame.video_info()
                h, w = vi.height, vi.width
                fmt = vi.to_caps().get_structure(0).get_value('format')

                if fmt in ('RGBA', 'BGRA', 'BGRx'):
                    channels = 4
                elif fmt == 'GRAY8':
                    channels = 1
                else:
                    channels = 3

                arr = np.frombuffer(image, dtype=np.uint8).reshape((h, w, channels))

                if fmt == 'RGB':
                    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                elif fmt in ('RGBA',):
                    bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
                elif fmt in ('BGRA', 'BGRx'):
                    bgr = arr[:, :, :3].copy()
                elif fmt == 'GRAY8':
                    bgr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
                else:
                    bgr = arr

                # Encode this frame (timed)
                _t0 = __import__('time').monotonic()
                feat = self._encode_frame(bgr)
                self._last_encode_ms = (__import__('time').monotonic() - _t0) * 1000.0
                self._features.append(feat)

                # Motion analysis every frame (lightweight)
                self._latest_motion = self._motion.update(bgr)

            # Decode every 8 frames once buffer is full (sliding window)
            if len(self._features) == SEQUENCE_LEN and self._frame_count % 8 == 0:
                _t0 = __import__('time').monotonic()
                self._latest_result = self._decode()
                self._last_decode_ms = (__import__('time').monotonic() - _t0) * 1000.0

                if self._frame_count % 64 == 0:
                    logger.info(
                        "Action frame %d: %s (%.1f%%) motion=%.1f%% [%s]",
                        self._frame_count,
                        self._latest_result.get("top_activity", "?"),
                        (self._latest_result.get("top_confidence", 0) * 100),
                        self._latest_motion.get("motion_magnitude", 0.0),
                        self._latest_motion.get("motion_level", "?"),
                    )

            # Merge *current* frame's motion data into the published result
            # so the UI sees real-time motion, not stale 16-frame-old data.
            result = dict(self._latest_result)
            result["motion_level"] = self._latest_motion.get("motion_level", "unknown")
            result["motion_magnitude"] = self._latest_motion.get("motion_magnitude", 0.0)
            result["encoder_ms"] = round(getattr(self, '_last_encode_ms', 0.0), 2)
            result["decoder_ms"] = round(getattr(self, '_last_decode_ms', 0.0), 2)
            result["inference_ms"] = round(
                getattr(self, '_last_encode_ms', 0.0) + getattr(self, '_last_decode_ms', 0.0), 2
            )
            frame.add_message(json.dumps({"action": result}))

        except Exception as exc:
            logger.warning("ActionCallback error at frame %d: %s", self._frame_count, exc)
            frame.add_message(json.dumps({"action": {
                "activities": [], "top_activity": "Error",
                "top_confidence": 0.0, "status": "error",
            }}))

        return True
