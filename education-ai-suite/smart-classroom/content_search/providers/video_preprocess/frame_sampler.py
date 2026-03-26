import os
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from PIL import Image
from decord import VideoReader, cpu
import uuid


class FrameSampler:
    def __init__(
        self,
        max_num_frames: int = 32,
        resolution: Optional[List[int]] = None,
        save_frame: bool = False,
        output_dir: Optional[str] = None,
        deduplicate: bool = True,
        dedup_threshold: float = 3.0,
        dedup_resize: Optional[List[int]] = None,
        dedup_max_consecutive: int = 4,
    ):
        """Initialize the FrameSampler."""
        self.max_num_frames = max_num_frames
        self.resolution = resolution if resolution is not None else []
        self.save_frame = save_frame
        self.output_dir = output_dir
        self.deduplicate = deduplicate
        self.dedup_threshold = float(dedup_threshold)
        self.dedup_resize = dedup_resize if dedup_resize is not None else [64, 64]
        self.dedup_max_consecutive = dedup_max_consecutive

    def save_frames(self, frames: np.ndarray, frame_indices: List[int], video_path: str):
        """Save sampled frames as images."""
        output_dir = self.output_dir or os.path.splitext(video_path)[0] + "_frames"
        os.makedirs(output_dir, exist_ok=True)
        for i, idx in enumerate(frame_indices):
            img = Image.fromarray(frames[i])
            img.save(os.path.join(output_dir, f"frame_{idx}.jpg"))

    @staticmethod
    def uniform_sample(frame_list: List[int], num_frames: int) -> List[int]:
        """Uniformly sample num_frames indices from frame_list."""
        if num_frames <= 0 or not frame_list:
            return []
        if num_frames >= len(frame_list):
            return list(frame_list)
        gap = len(frame_list) / num_frames
        idxs = [int(i * gap + gap / 2) for i in range(num_frames)]
        return [frame_list[i] for i in idxs]

    @staticmethod
    def _frames_similar_mad(
        f1: np.ndarray, f2: np.ndarray, resize_wh: Tuple[int, int], threshold: float
    ) -> bool:
        a = np.array(
            Image.fromarray(f1).resize(resize_wh).convert("L"),
            dtype=np.float32,
        )
        b = np.array(
            Image.fromarray(f2).resize(resize_wh).convert("L"),
            dtype=np.float32,
        )
        mad = float(np.mean(np.abs(a - b)))
        return mad <= threshold

    def _deduplicate_frames(
        self, frames: np.ndarray, frame_ids: List[int]
    ) -> Tuple[np.ndarray, List[int]]:
        if len(frame_ids) <= 1:
            return frames, frame_ids

        resize_wh = (int(self.dedup_resize[0]), int(self.dedup_resize[1]))
        keep_positions: List[int] = [0]
        oldpos_to_newpos: Dict[int, int] = {0: 0}
        consecutive_similar_count = 0

        for old_pos in range(1, len(frame_ids)):
            last_keep_pos = keep_positions[-1]
            if self._frames_similar_mad(
                frames[last_keep_pos],
                frames[old_pos],
                resize_wh=resize_wh,
                threshold=self.dedup_threshold,
            ):
                consecutive_similar_count += 1
                if consecutive_similar_count >= self.dedup_max_consecutive - 1:
                    keep_positions.append(old_pos)
                    oldpos_to_newpos[old_pos] = len(keep_positions) - 1
                    consecutive_similar_count = 0
                else:
                    oldpos_to_newpos[old_pos] = len(keep_positions) - 1
            else:
                keep_positions.append(old_pos)
                oldpos_to_newpos[old_pos] = len(keep_positions) - 1
                consecutive_similar_count = 0

        if len(keep_positions) == len(frame_ids):
            return frames, frame_ids

        new_frames = frames[keep_positions]
        new_frame_ids = [frame_ids[i] for i in keep_positions]

        return new_frames, new_frame_ids

    def sample_frames_from_video(
        self,
        video_path: Optional[str],
        detected_objects: List[Dict[str, Any]],
        frames_array: Optional[Any] = None,
        start_frame: Optional[int] = None,
        end_frame: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Uniformly sample frames from a video.

        Note: `detected_objects` is accepted for backward compatibility but ignored.
        """
        _ = detected_objects
        vr = None
        frames_source = None

        if frames_array is not None:
            frames_source = np.asarray(frames_array)
            total_frames = int(len(frames_source))
        else:
            if not video_path:
                raise ValueError("Either video_path or frames_array must be provided.")
            vr_args = {"ctx": cpu(0)}
            if self.resolution:
                vr_args.update({"width": self.resolution[0], "height": self.resolution[1]})
            vr = VideoReader(video_path, **vr_args)
            total_frames = int(len(vr))

        sf = int(start_frame) if start_frame is not None else 0
        ef = int(end_frame) if end_frame is not None else total_frames
        sf = max(0, sf)
        ef = min(total_frames, ef)
        if ef <= sf:
            return {"frames": np.empty((0,)), "frame_ids": [], "detected_objects": []}

        all_frames_idx = list(range(sf, ef))
        frame_idx = self.uniform_sample(all_frames_idx, self.max_num_frames)

        frame_idx = sorted(set(frame_idx))

        if frames_source is not None:
            frames = frames_source[frame_idx]
        else:
            frames = vr.get_batch(frame_idx).asnumpy()

        if self.deduplicate:
            frames, frame_idx = self._deduplicate_frames(frames=frames, frame_ids=frame_idx)

        if self.save_frame and video_path:
            print("Saving sampled frames to disk...")
            print(f"frame_idx: {frame_idx}")
            self.save_frames(frames, frame_idx, video_path)

        return {"frames": frames, "frame_ids": frame_idx, "detected_objects": []}

    def iter_chunks(
        self, video_path: str, chunk_duration_s: int, chunk_overlap_s: int = 0
    ) -> List[Dict[str, Any]]:
        """Split a local video file into time-based chunks.

        Returns a list of chunk dicts with frame ranges (no chunk files written).
        """
        vr_args = {"ctx": cpu(0)}
        if self.resolution:
            vr_args.update({"width": self.resolution[0], "height": self.resolution[1]})
        vr = VideoReader(video_path, **vr_args)
        fps = float(vr.get_avg_fps() or 0.0)
        if fps <= 0.0:
            raise ValueError(f"Unable to determine FPS for: {video_path}")
        total_frames = int(len(vr))

        chunk_frames = max(1, int(round(float(chunk_duration_s) * fps)))
        overlap_frames = max(0, int(round(float(chunk_overlap_s) * fps)))
        step = max(1, chunk_frames - overlap_frames)

        chunks: List[Dict[str, Any]] = []
        start = 0
        while start < total_frames:
            end = min(start + chunk_frames, total_frames)
            chunks.append(
                {
                    "video_path": video_path,
                    "chunk_id": str(uuid.uuid4()),
                    "start_time": start / fps,
                    "end_time": end / fps,
                    "start_frame": start,
                    "end_frame": end,
                    "detected_objects": [],
                }
            )
            if end >= total_frames:
                break
            start += step

        return chunks
