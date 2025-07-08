import argparse


def parse_args():
    parser = argparse.ArgumentParser(
        description="2D Avatar Client: Text Chat",
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
    from multiprocessing import Queue
    from da.avatar2d.render import AvatarRender
    from da import config
    from da.llm.ecrag_client import ECRAGRemoteClient
    from da.llm.qwen_client import QwenLocalClient
    from da.speak.tts_worker import TTSWorker
    from da.util.log import logger

    # load EC-RAG client
    # llm_client = QwenLocalClient()
    llm_client = ECRAGRemoteClient()

    # load tts model
    text_queue = Queue(1)
    audio_queue = Queue(1)
    tts_worker = TTSWorker(config.tts.male_voice, text_queue, audio_queue)

    # Load avatar render.
    avatar = AvatarRender(args.avatar_id, config.avatar2d.render_fps, audio_queue)

    avatar.start()
    tts_worker.start()

    while True:
        question = input("请输入问题：")
        if question == "exit":
            logger.info("Exiting...")
            break

        if question == "":
            continue

        audio_queue.put(config.tts.qa_transition_wav)
        for answer in llm_client.generate_text_complete_sentences(question):
            text_queue.put(answer)

    tts_worker.stop()
    avatar.stop()


if __name__ == '__main__':
    main(parse_args())
