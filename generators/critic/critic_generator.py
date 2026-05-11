from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from generators.critic.critic_model import CriticResult
from generators.story.story_model import Story

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = PROJECT_ROOT / "prompts"
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


class CriticGenerator:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        gemini_api_key = (os.getenv("GEMINI_STORY_API_KEY") or "").strip()
        if not gemini_api_key:
            raise ValueError("GEMINI_STORY_API_KEY environment variable not set.")
        self.client = genai.Client(api_key=gemini_api_key)
        self.model_name = model_name
        self._system_instruction: str | None = None

    @property
    def system_instruction(self) -> str:
        if self._system_instruction is None:
            path = PROMPTS_DIR / "critic_system_instruction.txt"
            self._system_instruction = path.read_text(encoding="utf-8").strip()
        return self._system_instruction

    def evaluate(self, story: Story, generation_params: dict) -> CriticResult:
        user_prompt = json.dumps(
            {
                "generation_parameters": generation_params,
                "story": json.loads(story.model_dump_json()),
            },
            ensure_ascii=False,
            indent=2,
        )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=CriticResult,
                ),
            )
            if response.parsed:
                return response.parsed
            return CriticResult.model_validate_json(response.text)
        except Exception as error:
            print(f"Error running critic: {error}")
            raise
