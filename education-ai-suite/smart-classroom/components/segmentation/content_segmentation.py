from components.base_component import PipelineComponent
import openvino_genai as ov_genai
import logging
from utils.config_loader import config

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
                    "You are a transcript segmentation engine. Your ONLY job is to output valid JSON.\n\n"
                    "HARD CONSTRAINT: Output EXACTLY between 15 and 25 topic objects. NEVER more than 25. NEVER fewer than 15.\n\n"
                    "BEFORE outputting, count your segments. If count > 25, merge the most related adjacent segments until count ≤ 25.\n\n"
                    "Segmentation rules:\n"
                    "- Each topic = one major teaching concept (think: lesson chapters, not paragraphs)\n"
                    "- Each topic must span multiple minutes\n"
                    "- Ignore minor explanation shifts or small tangents\n"
                    "- Merge adjacent related segments aggressively\n"
                    "- Do NOT split mid-sentence\n"
                    "- Use only timestamps present in the transcript\n\n"
                    "Topic title rules (IMPORTANT — titles are used for semantic search and embedding):\n"
                    "- Each title must be a descriptive sentence of 10–15 words\n"
                    "- The title must clearly summarize WHAT was taught in that segment\n"
                    "- Write as if describing the segment to someone who hasn't seen the transcript\n"
                    "- Good: 'Explaining how Newton's third law applies to rocket propulsion with examples'\n"
                    "- Bad: 'Newton law', 'Topic 3', 'Continued explanation'\n\n"
                    "Output format — return ONLY this JSON, nothing else:\n"
                    "[{\"topic\": \"<descriptive title>\", \"start_time\": <float>, \"end_time\": <float>}]\n\n"
                    "No markdown. No explanation. No comments. No text outside the JSON array."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Segment this transcript into 15–25 topics (MAXIMUM 25, merge aggressively if needed).\n\n"
                    f"{transcript_text}\n\n"
                    f"Remember:\n"
                    f"1. Output ONLY a JSON array with 15–25 objects. Count before you output.\n"
                    f"2. Each topic title must be a descriptive 10–15 word sentence useful for semantic search."
                )
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

            full_output = self.model.generate(prompt, False)
            logger.info("Topic segmentation completed.")
            return full_output

        except Exception as e:
            logger.error(f"Topic segmentation failed: {e}")
            raise
