from queue import Queue

import numpy as np
import openvino as ov

from da.avatar2d.avatar import Avatar
from ext.musetalk.utils.utils import datagen


def pad_array_to_batch_size(input_array, target_batch_size):
    current_batch_size = input_array.shape[0]
    if current_batch_size >= target_batch_size:
        return input_array

    # Calculate the padding needed
    padding_size = target_batch_size - current_batch_size
    padding_array = np.zeros((padding_size, *input_array.shape[1:]), dtype=input_array.dtype)

    # Concatenate the input array with the padding array
    padded_array = np.concatenate((input_array, padding_array), axis=0)

    return padded_array


def load_ov_model(ov_path, device):
    return ov.compile_model(ov_path, device)


class AvatarOV(Avatar):
    def __init__(self, ov_device: str, **kwargs):
        self.timesteps = np.array([0])

        # load ov model.
        self.unet_vae_ov = load_ov_model("resource/musetalk_models/musetalk/unet-vae-b4.xml", ov_device)

        super().__init__(**kwargs)

    def gen_face(self, whisper_chunks, output_face_queue: Queue):
        gen = datagen(whisper_chunks, self.input_latent_list_cycle, self.batch_size, delay_frame=self.idx)
        for i, (whisper_batch, latent_batch) in enumerate(gen):

            latent_batch = latent_batch.cpu().numpy()

            # Pad to batch size
            actual_batch_size = whisper_batch.shape[0]
            if actual_batch_size < self.batch_size:
                whisper_batch = pad_array_to_batch_size(whisper_batch, self.batch_size)
                latent_batch = pad_array_to_batch_size(latent_batch, self.batch_size)

            recon = self.unet_vae_ov((whisper_batch, latent_batch, self.timesteps))[0]

            # un-pad
            if actual_batch_size < self.batch_size:
                recon = recon[:actual_batch_size]

            for res_frame in recon:
                output_face_queue.put(res_frame)
