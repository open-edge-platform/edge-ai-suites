from multiprocessing import Queue as p_Queue
from queue import Queue

from da import config
from da.avatar2d.av_syncer import AVSyncer
from da.avatar2d.avatar_ov import AvatarOV
from da.avatar2d.combine_face_worker import CombineFaceWorker
from da.avatar2d.frame_displayer import FrameDisplayer
from da.avatar2d.gen_face_worker import GenFaceWorker
from da.avatar2d.whisper_worker import WhisperWorker
from da.speak.audio_player import AudioPlayer
from da.util.woker import PipelineWorker, WorkerType


class AvatarRender(PipelineWorker):
    def __init__(self, avatar_id: str, fps: int, audio_input_queue: Queue):
        self.fps = fps
        self.avatar_id = avatar_id
        self.audio_input_queue = audio_input_queue

        super().__init__(self.__class__.__name__, WorkerType.Thread)

    # noinspection PyAttributeOutsideInit
    def _init(self):
        self.avatar = AvatarOV(
            avatar_id=self.avatar_id,
            video_path="",
            bbox_shift=0,
            batch_size=4,
            preparation=False,
            fps=self.fps,
            ov_device=config.ov.device,
        )

        self.audio_queue_from_whisper = Queue(1)
        self.chunks_queue_from_whisper = Queue(self.avatar.fps * 10)  # 10s buffer
        self.whisper = WhisperWorker(
            self.avatar,
            self.audio_input_queue,
            self.chunks_queue_from_whisper,
            self.audio_queue_from_whisper
        )

        self.chunks_queue_to_gen_face = Queue(1)
        self.audio_queue_to_player = p_Queue(1)
        self.av_syncer = AVSyncer(self.chunks_queue_from_whisper, self.chunks_queue_to_gen_face, self.audio_queue_from_whisper, self.audio_queue_to_player)

        self.face_queue = Queue(1)
        self.gen_face = GenFaceWorker(self.avatar, self.chunks_queue_to_gen_face, self.face_queue)

        self.frame_queue = Queue(self.avatar.batch_size + 1)
        self.combine_face = CombineFaceWorker(self.avatar, self.face_queue, self.frame_queue)
        self.displayer = FrameDisplayer(self.fps, self.frame_queue)

        self.audio_player = AudioPlayer(self.audio_queue_to_player)

    def _run(self):
        self.audio_player.start()
        self.displayer.start()
        self.combine_face.start()
        self.gen_face.start()
        self.av_syncer.start()
        self.whisper.start()

        self._stop_event.wait()

        self.whisper.stop()
        self.av_syncer.stop()
        self.gen_face.stop()
        self.combine_face.stop()
        self.displayer.stop()
        self.audio_player.stop()
