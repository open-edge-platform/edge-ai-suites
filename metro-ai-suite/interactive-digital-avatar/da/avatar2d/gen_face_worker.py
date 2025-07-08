from queue import Queue, Empty

import numpy as np

from da.avatar2d.avatar_ov import AvatarOV, pad_array_to_batch_size
from da.util.woker import PipelineWorker, WorkerType


class GenFaceWorker(PipelineWorker):
    def __init__(self, avatar: AvatarOV, whisper_input_queue: Queue, face_output_queue: Queue):

        self.avatar = avatar
        self.whisper_input_queue = whisper_input_queue
        self.face_output_queue = face_output_queue

        super().__init__(self.__class__.__name__, WorkerType.Thread)

    def _init(self):
        pass

    def _run(self):
        idx = 0
        idx_len = len(self.avatar.input_latent_list_cycle)

        while self._is_running():
            try:
                whisper_batch = self.whisper_input_queue.get_nowait()
            except Empty:
                whisper_batch = None

            if whisper_batch is None:
                # No audio input, tell combine face worker output original img by set face to None.
                self.face_output_queue.put((None, idx))
                idx = (idx + 1) % idx_len
                continue

            # Get audio input, generate face
            src_idxs = []
            for _ in range(len(whisper_batch)):
                src_idxs.append(idx)
                idx = (idx + 1) % idx_len

            latent_batch = np.concatenate([self.avatar.input_latent_list_cycle[i].numpy() for i in src_idxs])

            # Pad to batch size
            actual_batch_size = whisper_batch.shape[0]
            if actual_batch_size < self.avatar.batch_size:
                whisper_batch = pad_array_to_batch_size(whisper_batch, self.avatar.batch_size)
                latent_batch = pad_array_to_batch_size(latent_batch, self.avatar.batch_size)

            recon = self.avatar.unet_vae_ov((whisper_batch, latent_batch, self.avatar.timesteps))[0]

            # un-pad
            if actual_batch_size < self.avatar.batch_size:
                recon = recon[:actual_batch_size]

            for face_frame, i in zip(recon, src_idxs):
                self.face_output_queue.put((face_frame, i))
