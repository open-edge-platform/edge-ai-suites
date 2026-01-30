import asyncio
import logging
import json
import os
import cv2
from typing import List, Dict, Optional
from pydantic import ValidationError
from .stream_manager import LiveStreamManager
from .vlm_client import VLMClient
from .event_manager import EventManager
from src.schemas.monitor import AgentResult
from src.config import settings

logger = logging.getLogger(__name__)

class AgentManager:
    def __init__(self, vlm_url: str, vlm_api_key: str, model_name: str, config_file: str = "resources/streams.json"):
        self.config_file = config_file
        self.agents_config_file = "resources/agents.json"
        self.streams: Dict[str, LiveStreamManager] = {}
        self.vlm_client = VLMClient(base_url=vlm_url, api_key=vlm_api_key, model_name=model_name)
        self.running = False
        # Results structure: { stream_id: { agent_name: {"answer": "YES/NO", "reason": "..."} } }
        self.latest_results: Dict[str, Dict] = {} 
        
        # SSE Event Manager for real-time updates
        self.events = EventManager()
        
        # Dynamic agent config
        self.agents_config: List[Dict] = self._load_agents_config()
        
        self._load_config()

    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to real-time SSE events."""
        return await self.events.subscribe()

    async def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from SSE events."""
        await self.events.unsubscribe(queue)

    def _load_agents_config(self) -> List[Dict]:
        """Load user-defined agents from JSON. Returns defaults if missing."""
        if os.path.exists(self.agents_config_file):
            try:
                with open(self.agents_config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load alerts config: {e}")
        
        # Default agents
        return [
            {"name": "Fire Detection", "prompt": "Is there visible fire or smoke in the image?", "enabled": True},
            {"name": "Person Detection", "prompt": "Is there a person present in the frame?", "enabled": True}
        ]

    def save_agents_config(self, config: List[Dict]):
        """Save user-defined agents to JSON"""
        self.agents_config = config
        try:
            os.makedirs(os.path.dirname(self.agents_config_file), exist_ok=True)
            with open(self.agents_config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved {len(config)} alerts to config")
        except Exception as e:
            logger.error(f"Failed to save alerts config: {e}")

    def get_agents_config(self) -> List[Dict]:
        """Return current agent configuration"""
        return self.agents_config

    def _load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    streams = json.load(f)
                    logger.info(f"Loading {len(streams)} streams from config")
                    for s in streams:
                        self.add_stream(s['id'], s['url'], save=False)
            except Exception as e:
                logger.error(f"Failed to load stream config: {e}")

    def _save_config(self):
        try:
            data = [{"id": s_id, "url": mgr.rtsp_url} for s_id, mgr in self.streams.items()]
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save stream config: {e}")

    def add_stream(self, stream_id: str, rtsp_url: str, save: bool = True):
        if stream_id in self.streams:
            logger.warning(f"Stream {stream_id} already exists.")
            return
        
        manager = LiveStreamManager(rtsp_url)
        self.streams[stream_id] = manager
        self.latest_results[stream_id] = {}
        
        if self.running:
            manager.start()
        
        if save:
            self._save_config()
            
        logger.info(f"Added stream: {stream_id} -> {rtsp_url}")

    def remove_stream(self, stream_id: str):
        if stream_id in self.streams:
            self.streams[stream_id].stop()
            del self.streams[stream_id]
            if stream_id in self.latest_results:
                del self.latest_results[stream_id]
            
            self._save_config()
            logger.info(f"Removed stream: {stream_id}")

    def get_latest_frame(self, stream_id: str):
        """Return the most recent frame for the UI stream"""
        if stream_id not in self.streams:
            return None
        frames = self.streams[stream_id].get_recent_frames(count=1)
        if frames:
            return frames[0]
        return None

    def _build_dynamic_prompt(self) -> str:
        """Build VLM prompt dynamically based on enabled agents"""
        enabled_agents = [a for a in self.agents_config if a.get('enabled', False)]
        
        if not enabled_agents:
            return None
        
        questions = {}
        for agent in enabled_agents:
            questions[agent['name']] = agent['prompt']
        
        prompt = f"""You are an intelligent video monitoring assistant. Analyze the image and answer EACH of the following questions.

QUESTIONS TO ANSWER:
{json.dumps(questions, indent=2)}

IMPORTANT RULES:
1. For each question, you MUST answer with EXACTLY "YES" or "NO" (uppercase, no other words)
2. Provide a brief reason explaining your answer
3. You must include every single question key in your JSON response. Do not skip any.

OUTPUT FORMAT (strict JSON):
{{
{', '.join([f'  "{a["name"]}": {{"answer": "YES" or "NO", "reason": "your explanation"}}' for a in enabled_agents])}
}}

Return ONLY the JSON object, no markdown formatting."""
        
        return prompt

    async def _run_analysis_loop(self):
        """Main analysis loop - processes all streams with dynamic agents"""
        logger.info("Starting dynamic analysis loop")
        
        while self.running:
            start_time = asyncio.get_event_loop().time()
            stream_ids = list(self.streams.keys())
            
            if not stream_ids:
                await asyncio.sleep(1)
                continue
            
            # Build prompt once per cycle
            prompt = self._build_dynamic_prompt()
            if not prompt:
                await asyncio.sleep(1)
                continue
            
            for stream_id in stream_ids:
                try:
                    manager = self.streams.get(stream_id)
                    if not manager:
                        continue
                    
                    frames = manager.get_recent_frames(count=1)
                    if not frames:
                        continue
                    
                    # Analyze with VLM
                    logger.debug(f"Analyzing stream: {stream_id}")
                    response = await self.vlm_client.analyze_stream_segment(
                        frames,
                        system_prompt="You are a precise video analytics AI. Always respond with valid JSON.",
                        user_prompt=prompt
                    )
                    
                    if response:
                        try:
                            # Clean and parse response
                            clean_response = response.replace("```json", "").replace("```", "").strip()
                            
                            # Robust extraction: Find first { and last }
                            start_idx = clean_response.find('{')
                            end_idx = clean_response.rfind('}')
                            
                            if start_idx != -1 and end_idx != -1:
                                clean_response = clean_response[start_idx : end_idx + 1]
                            
                            data = json.loads(clean_response)
                            
                            # Get list of enabled agent names for validation
                            enabled_agent_names = [a['name'] for a in self.agents_config if a.get('enabled', False)]
                            
                            # Validate each agent result with Pydantic
                            validated_results = {}
                            for agent_name, result in data.items():
                                try:
                                    validated = AgentResult(**result)
                                    validated_results[agent_name] = validated.model_dump()
                                except ValidationError as ve:
                                    logger.warning(f"Validation failed for {agent_name}: {ve}")
                                    validated_results[agent_name] = {"answer": "NO", "reason": "Validation error"}
                            
                            # Check if VLM missed any enabled agents
                            for agent_name in enabled_agent_names:
                                if agent_name not in validated_results:
                                    logger.warning(f"VLM did not return result for alert: {agent_name}")
                                    validated_results[agent_name] = {"answer": "NO", "reason": "No response from VLM"}
                            
                            # Store validated results
                            self.latest_results[stream_id] = validated_results
                            logger.debug(f"Updated results for {stream_id}: {list(validated_results.keys())}")
                            
                            # Broadcast to SSE subscribers (real-time push)
                            await self.events.broadcast("analysis", {
                                "stream_id": stream_id,
                                "results": validated_results
                            })
                            
                            # Log alerts (YES answers)
                            alerts = [f"{k}={v['answer']}" for k,v in validated_results.items() if v['answer'] == 'YES']
                            if alerts:
                                logger.warning(f" ALERT [{stream_id}]: {', '.join(alerts)}")
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON parse error for {stream_id}: {e}")
                        except Exception as e:
                            logger.error(f"Processing error for {stream_id}: {e}")
                            
                except Exception as e:
                    logger.error(f"Error analyzing {stream_id}: {e}")
                
                # CRITICAL: Yield to event loop to prevent API starvation
                # This allows HTTP requests (save, delete) to be processed
                await asyncio.sleep(0)
            
            # Wait for next cycle
            elapsed = asyncio.get_event_loop().time() - start_time
            sleep_time = max(0.5, settings.ANALYSIS_INTERVAL - elapsed)
            await asyncio.sleep(sleep_time)

    async def start(self):
        """Start the stream managers and analysis loop"""
        self.running = True
        for manager in self.streams.values():
            manager.start()
        
        # Wait for buffers to fill
        await asyncio.sleep(2)
        
        logger.info(f"AgentManager started with {len(self.agents_config)} configured alerts")
        await self._run_analysis_loop()

    def stop(self):
        self.running = False
        for manager in self.streams.values():
            manager.stop()
