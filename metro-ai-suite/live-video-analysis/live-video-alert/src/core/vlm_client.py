import base64
import cv2
import logging
from openai import AsyncOpenAI
from typing import List, Optional

logger = logging.getLogger(__name__)

class VLMClient:
    def __init__(self, base_url: str, api_key: str, model_name: str):
        self.client = AsyncOpenAI(
            base_url=base_url, 
            api_key=api_key,
            timeout=30.0,
            max_retries=0
        )
        self.model_name = model_name
        logger.info(f"VLMClient initialized for model: {model_name} at {base_url}")

    def _encode_image(self, frame):
        try:
            # Resize to reduce bandwidth/latency (Max dimension 448)
            height, width = frame.shape[:2]
            max_dim = 448
            if max(height, width) > max_dim:
                scale = max_dim / max(height, width)
                new_w = int(width * scale)
                new_h = int(height * scale)
                frame = cv2.resize(frame, (new_w, new_h))

            _, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            return base64.b64encode(buffer).decode("utf-8").replace("\n", "")
        except Exception as e:
            logger.error(f"Failed to encode image: {e}")
            return None

    async def analyze_stream_segment(self, frames: List, system_prompt: str, user_prompt: str) -> Optional[str]:
        """
        Sends a batch of frames to the VLM for analysis.
        """
        if not frames:
            return None

        content = []
        
        for frame in frames:
            b64_img = self._encode_image(frame)
            if b64_img:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                })

        final_prompt = f"{system_prompt}\n\nTask: {user_prompt}"
        content.append({"type": "text", "text": final_prompt})

        try:
            logger.debug(f"Sending {len(frames)} frames to VLM...")
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": content}
                ],
                max_tokens=500,  # Increased to support up to 4 agents with reasons
                temperature=0.1,
            )
            result = response.choices[0].message.content
            logger.debug(f"VLM Raw Result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"VLM API Error: {str(e)}")
            return None
