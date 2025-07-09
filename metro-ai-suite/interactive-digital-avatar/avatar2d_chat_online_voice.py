import argparse

from da import config
from da.listen.listener import Listener


def parse_args():
    parser = argparse.ArgumentParser(
        description="2D Avatar Client: Voice Chat.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--avatar_id",
        "-ai",
        type=str,
        default="my-avatar",
        help="Id for avatar loaded."
    )

    return parser.parse_args()


def main(args):
    from queue import Empty
    from multiprocessing import Queue

    from da.avatar2d.render import AvatarRender
    from da.llm.ecrag_client import ECRAGRemoteClient
    from da.llm.qwen_client import QwenLocalClient
    from da.speak.tts_worker import TTSWorker
    from da.util.log import logger

    # load EC-RAG client
    # llm_client = QwenLocalClient()
    llm_client = ECRAGRemoteClient()

    # load ASR
    question_text_queue = Queue(1)
    audio_queue = Queue(1)
    hello_wav = config.tts.male_hello_wav if config.tts.male_hello_wav else config.tts.female_hello_wav
    listener = Listener(question_text_queue, audio_queue, hello_wav)

    # load tts model
    answer_text_queue = Queue(1)
    tts_worker = TTSWorker(config.tts.male_voice, answer_text_queue, audio_queue)

    # load avatar render
    avatar = AvatarRender(args.avatar_id, config.avatar2d.render_fps, audio_queue)

    avatar.start()
    tts_worker.start()
    listener.start()

    logger.info("Listening...")

    try:
        while True:
            try:
                question = question_text_queue.get(timeout=1)
            except Empty:
                continue

            if len(question.strip()) == 0:
                continue

            for answer in llm_client.generate_text_complete_sentences(question):
                answer_text_queue.put(answer)
    except KeyboardInterrupt:
        logger.info("Exit...")
        listener.stop()
        tts_worker.stop()
        avatar.stop()


if __name__ == '__main__':
    main(parse_args())
