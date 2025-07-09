from multiprocessing import Queue as p_Queue
from queue import Queue

from da import config
from da.avatar3d.av_syncer import AVSyncer
from da.avatar3d.lip_sync_client import LipSyncClient
from da.avatar3d.lip_sync_worker import LipSyncWorker
from da.avatar3d.pose_sender import PoseSender
from da.speak.audio_player import AudioPlayer
from da.util.woker import PipelineWorker, WorkerType


class RenderIntegrator(PipelineWorker):
    def __init__(self, audio_input_queue: Queue):
        self.audio_input_queue = audio_input_queue

        super().__init__(self.__class__.__name__, WorkerType.Thread)

    # noinspection PyAttributeOutsideInit
    def _init(self):
        self.lip_sync_client = LipSyncClient(
            config.avatar3d.said_addr,
            config.avatar3d.said_fps,
            config.avatar3d.pose_sync_fps
        )

        self.lip_queue_from_said = Queue(config.avatar3d.pose_sync_fps * 10)  # 10s buffer
        self.audio_queue_from_said = Queue(1)
        self.lip_syncer = LipSyncWorker(
            self.lip_sync_client,
            self.audio_input_queue,
            self.lip_queue_from_said,
            self.audio_queue_from_said
        )

        self.lip_queue_to_pose_sender = Queue(1)
        self.audio_queue_to_player = p_Queue(1)
        self.av_syncer = AVSyncer(
            self.lip_queue_from_said,
            self.lip_queue_to_pose_sender,
            self.audio_queue_from_said,
            self.audio_queue_to_player
        )

        self.pose_sender = PoseSender(
            self.lip_queue_to_pose_sender,
            config.avatar3d.sio_addr,
            config.avatar3d.pose_sync_fps
        )

        self.audio_player = AudioPlayer(self.audio_queue_to_player)

    def _run(self):
        self.audio_player.start()
        self.pose_sender.start()
        self.av_syncer.start()
        self.lip_syncer.start()

        self._stop_event.wait()

        self.lip_syncer.stop()
        self.av_syncer.stop()
        self.pose_sender.stop()
        self.audio_player.stop()
