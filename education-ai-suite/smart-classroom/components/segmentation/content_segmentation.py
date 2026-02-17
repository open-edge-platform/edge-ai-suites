from components.base_component import PipelineComponent
import openvino_genai as ov_genai
import logging

logger = logging.getLogger(__name__)

class ContentSegmentationComponent(PipelineComponent):
    def __init__(self, session_id, temperature=0.2):
        self.session_id = session_id
        self.temperature = temperature

    def _build_messages(self, transcript_text):
        return [
            {
                "role": "system",
                "content": (
                    "You are given a classroom teacher transcript with timestamps.\n\n"
                    "Split the transcript into topic segments.\n"
                    "Each topic must represent one coherent teaching concept.\n\n"
                    "Return ONLY valid JSON in the following exact format:\n"
                    "[{\"topic\": \"\", \"start_time\": 0.0, \"end_time\": 0.0}]\n\n"
                    "Rules:\n"
                    "- Do NOT split mid-sentence\n"
                    "- Use only timestamps present in the transcript\n"
                    "- Do NOT hallucinate timestamps\n"
                    "- Do NOT explain\n"
                    "- Do NOT add markdown\n"
                    "- Do NOT add comments\n"
                    "- Do NOT output anything outside JSON\n"
                    "- Ensure the output is valid JSON that can be parsed by json.loads()\n"
                )
            },
            {
                "role": "user",
                "content": transcript_text
            }
        ]

    def generate_topics(self, transcript_text):
        try:
            logger.info("Generating topic segmentation...")

            prompt = self.model.tokenizer.apply_chat_template(
                self._build_messages(transcript_text),
                tokenize=False,
                add_generation_prompt=True
            )

            streamer = self.model.generate(prompt)

            full_output = "".join(token for token in streamer)

            logger.info("Topic segmentation completed.")
            return full_output

        except Exception as e:
            logger.error(f"Topic segmentation failed: {e}")
            raise
