#!/usr/bin/env python3
# pylint: disable=duplicate-code
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

"""Mel-spectrogram to waveform vocoder models with OpenVINO inference."""

import os.path as osp

import numpy as np

from utils.wav_processing import (
    fold_with_overlap,
    infer_from_discretized_mix_logistic,
    pad_tensor,
    xfade_and_unfold,
)


class WaveRNNIE:  # pylint: disable=too-many-instance-attributes
    """OpenVINO-based WaveRNN vocoder for mel-to-waveform synthesis."""
    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        model_upsample,
        model_rnn,
        core,
        target=11000,
        overlap=550,
        hop_length=275,
        bits=9,
        device='CPU',
        verbose=False,
        upsampler_width=-1,
    ):
        """
        return class provided WaveRNN inference.

        :param model_upsample: path to xml with upsample model of WaveRNN
        :param model_rnn: path to xml with rnn parameters of WaveRNN model
        :param target: length of the processed fragments
        :param overlap: overlap of the processed frames
        :param hop_length: The number of samples between successive frames,
                           e.g., the columns of a spectrogram.
        :return:
        """
        self.verbose = verbose
        self.device = device
        self.target = target
        self.overlap = overlap
        self.dynamic_overlap = overlap
        self.hop_length = hop_length
        self.bits = bits
        self.indent = 550
        self.pad = 2
        self.batch_sizes = [1, 2, 4, 8, 16, 32, 64, 128, 256]
        self.core = core

        self.upsample_net = self.load_network(model_upsample)
        if upsampler_width > 0:
            orig_shape = self.upsample_net.inputs[0].shape
            inp_name = self.upsample_net.inputs[0].any_name
            new_shape = (orig_shape[0], upsampler_width, orig_shape[2])
            self.upsample_net.reshape({inp_name: new_shape})

        self.upsample_exec = self.create_exec_network(self.upsample_net)

        self.rnn_net = self.load_network(model_rnn)
        self.rnn_exec = self.create_exec_network(self.rnn_net, batch_sizes=self.batch_sizes)

        # fixed number of the mels in mel-spectrogramm
        self.mel_len = self.upsample_net.inputs[0].shape[1] - 2 * self.pad
        self.rnn_width = next(
            (inp for inp in self.rnn_net.inputs if inp.any_name == 'x'),
            self.rnn_net.inputs[0],
        ).shape[1]

    def load_network(self, model_xml):
        """Read an OpenVINO IR model from disk."""
        model_bin_name = '.'.join(osp.basename(model_xml).split('.')[:-1]) + '.bin'
        model_bin = osp.join(osp.dirname(model_xml), model_bin_name)
        print(f'Loading network files:\n\t{model_xml}\n\t{model_bin}')
        net = self.core.read_model(model=model_xml)
        return net

    def create_exec_network(self, net, batch_sizes=None):
        """Compile a model for the target device, optionally per batch size."""
        if batch_sizes is not None:
            exec_net = []
            for _b_s in batch_sizes:
                # Create a new model instance with batch size
                rt_info = net.get_rt_info()
                model_path = (
                    rt_info["model_path"]
                    if "model_path" in rt_info
                    else None
                )
                reshaped_net = self.core.read_model(model=model_path)
                if reshaped_net is None:
                    # If we can't reload, reshape the existing one
                    reshaped_net = net
                # Note: OpenVINO 2024 doesn't have batch_size property, need to reshape inputs
                exec_net.append(self.core.compile_model(reshaped_net, self.device))
        else:
            exec_net = self.core.compile_model(net, self.device)
        return exec_net

    @staticmethod
    def get_rnn_init_states(b_size=1, rnn_dims=328):
        """Return zeroed initial hidden states for the RNN."""
        h1 = np.zeros((b_size, rnn_dims), dtype=float)
        h2 = np.zeros((b_size, rnn_dims), dtype=float)
        x = np.zeros((b_size, 1), dtype=float)
        return h1, h2, x

    def forward(self, mels):
        """Synthesise a waveform from mel-spectrogram frames."""
        mels = (mels + 4) / 8
        np.clip(mels, 0, 1, out=mels)
        mels = np.transpose(mels)
        mels = np.expand_dims(mels, axis=0)

        n_parts = (
            mels.shape[1] // self.mel_len + 1
            if mels.shape[1] % self.mel_len > 0
            else mels.shape[1] // self.mel_len
        )
        upsampled_mels = []
        aux = []
        last_padding = 0
        for i in range(n_parts):
            i_start = i * self.mel_len
            i_end = i_start + self.mel_len
            if i_end > mels.shape[1]:
                last_padding = i_end - mels.shape[1]
                mel = np.pad(
                    mels[:, i_start: mels.shape[1], :],  # fmt: skip
                    ((0, 0), (0, last_padding), (0, 0)),
                    'constant',
                    constant_values=0,
                )
            else:
                mel = mels[:, i_start:i_end, :]

            upsampled_mels_b, aux_b = self.forward_upsample(mel)
            upsampled_mels.append(upsampled_mels_b)
            aux.append(aux_b)
        if len(aux) > 1:
            upsampled_mels = np.concatenate(upsampled_mels, axis=1)
            aux = np.concatenate(aux, axis=1)
        else:
            upsampled_mels = upsampled_mels[0]
            aux = aux[0]
        if last_padding > 0:
            upsampled_mels = upsampled_mels[:, : -last_padding * self.hop_length, :]
            aux = aux[:, : -last_padding * self.hop_length, :]

        upsampled_mels, (_, self.dynamic_overlap) = fold_with_overlap(
            upsampled_mels, self.target, self.overlap
        )
        aux, _ = fold_with_overlap(aux, self.target, self.overlap)

        audio = self.forward_rnn(mels, upsampled_mels, aux)
        audio = (audio * (2**15 - 1)).astype('<h')

        return audio

    def forward_upsample(self, mels):
        """Upsample mel frames to match the audio sample rate."""
        mels = pad_tensor(mels, pad=self.pad)

        out = self.upsample_exec(mels)
        upsample_out = out[self.upsample_exec.outputs[0]]
        upsample_mels = upsample_out[:, self.indent:-self.indent, :]
        aux = out[self.upsample_exec.outputs[1]]
        return upsample_mels, aux

    def forward_rnn(self, mels, upsampled_mels, aux):  # pylint: disable=too-many-locals
        """Run the autoregressive RNN to produce audio samples."""
        wave_len = (mels.shape[1] - 1) * self.hop_length

        d = aux.shape[2] // 4
        aux_split = [aux[:, :, d * i: d * (i + 1)] for i in range(4)]  # fmt: skip

        b_size, seq_len, _ = upsampled_mels.shape
        seq_len = min(seq_len, aux_split[0].shape[1])

        if b_size not in self.batch_sizes:
            raise ValueError(
                f'Incorrect batch size {b_size}. Correct should be 2 ** something'
            )

        active_network = self.batch_sizes.index(b_size)

        h1, h2, x = self.get_rnn_init_states(b_size, self.rnn_width)

        output = []

        for i in range(seq_len):
            m_t = upsampled_mels[:, i, :]

            a1_t, a2_t, a3_t, a4_t = (a[:, i, :] for a in aux_split)

            out = self.rnn_exec[active_network](
                {
                    'm_t': m_t,
                    'a1_t': a1_t,
                    'a2_t': a2_t,
                    'a3_t': a3_t,
                    'a4_t': a4_t,
                    'h1.1': h1,
                    'h2.1': h2,
                    'x': x,
                }
            )

            logits = out[self.rnn_exec[active_network].outputs[0]]
            h1 = out[self.rnn_exec[active_network].outputs[1]]
            h2 = out[self.rnn_exec[active_network].outputs[2]]

            sample = infer_from_discretized_mix_logistic(logits)

            x = sample[:]
            x = np.expand_dims(x, axis=1)
            output.append(sample)

        output = np.stack(output).transpose(1, 0)
        output = output.astype(np.float64)

        if b_size > 1:
            output = xfade_and_unfold(output, self.dynamic_overlap)
        else:
            output = output[0]

        fade_out = np.linspace(1, 0, 20 * self.hop_length)
        output = output[:wave_len]
        output[-20 * self.hop_length:] *= fade_out  # fmt: skip
        return output


class MelGANIE:  # pylint: disable=too-many-instance-attributes
    """OpenVINO-based MelGAN vocoder for mel-to-waveform synthesis."""
    def __init__(self, model, core, device='CPU', default_width=800):
        """
        return class provided MelGAN inference.

        :param model: path to xml with MelGAN model of WaveRNN
        :param core: instance of the Core
        :param device: target device
        :return:
        """
        self.device = device
        self.core = core

        self.scales = 4
        self.hop_length = 256

        self.net = self.load_network(model)
        if self.net.inputs[0].shape[2] != default_width:
            orig_shape = self.net.inputs[0].shape
            new_shape = (orig_shape[0], orig_shape[1], default_width)
            self.net.reshape({self.net.inputs[0].any_name: new_shape})

        self.exec_net = self.create_exec_network(self.net, self.scales)

        # fixed number of columns in mel-spectrogramm
        self.mel_len = self.net.inputs[0].shape[2]
        self.widths = [self.mel_len * (i + 1) for i in range(self.scales)]

    def load_network(self, model_xml):
        """Read an OpenVINO IR model from disk."""
        model_bin_name = '.'.join(osp.basename(model_xml).split('.')[:-1]) + '.bin'
        model_bin = osp.join(osp.dirname(model_xml), model_bin_name)
        print(f'Loading network files:\n\t{model_xml}\n\t{model_bin}')
        net = self.core.read_model(model=model_xml)
        return net

    def create_exec_network(self, net, scales=None):
        """Compile the model at multiple scales for variable-length input."""
        if scales is not None:
            orig_shape = list(net.inputs[0].shape)
            exec_net = []
            for i in range(scales):
                new_shape = (orig_shape[0], orig_shape[1], orig_shape[2] * (i + 1))
                net.reshape({net.inputs[0].any_name: new_shape})
                exec_net.append(self.core.compile_model(net, self.device))
                net.reshape({net.inputs[0].any_name: orig_shape})
        else:
            exec_net = self.core.compile_model(net, self.device)
        return exec_net

    def forward(self, mel):
        """Synthesise a waveform from a mel-spectrogram using MelGAN."""
        mel = np.expand_dims(mel, axis=0)
        res_audio = []
        last_padding = 0
        if mel.shape[2] % self.mel_len:
            last_padding = self.mel_len - mel.shape[2] % self.mel_len

        mel = np.pad(
            mel, ((0, 0), (0, 0), (0, last_padding)), 'constant', constant_values=-11.5129
        )

        active_net = -1
        cur_w = -1
        cols = mel.shape[2]

        for i, w in enumerate(self.widths):
            if cols <= w:
                cur_w = w
                active_net = i
                break
        if active_net == -1:
            cur_w = self.widths[-1]

        c_begin = 0
        c_end = cur_w
        while c_begin < cols:
            audio = self.exec_net[active_net](mel[:, :, c_begin:c_end])[
                self.exec_net[active_net].outputs[0]
            ]
            res_audio.extend(audio)

            c_begin = c_end

            if c_end + cur_w >= cols:
                for i, w in enumerate(self.widths):
                    if w >= cols - c_end:
                        cur_w = w
                        active_net = i
                        break

            c_end += cur_w
        if last_padding:
            audio = res_audio[: -self.hop_length * last_padding]
        else:
            audio = res_audio

        audio = np.array(audio).astype(dtype=np.int16)

        return audio
