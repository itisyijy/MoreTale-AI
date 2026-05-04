import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from generators.quiz.quiz_model import Quiz
from generators.quiz.quiz_prompts import QuizPrompt
from generators.story.story_model import Story

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


class QuizGenerator:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        gemini_api_key = (os.getenv("GEMINI_STORY_API_KEY") or "").strip()
        if not gemini_api_key:
            raise ValueError("GEMINI_STORY_API_KEY environment variable not set.")
        self.client = genai.Client(api_key=gemini_api_key)
        self.model_name = model_name
        self.prompts = QuizPrompt()

    def generate_quiz(
        self,
        *,
        story_id: str,
        story: Story,
        question_count: int = 5,
    ) -> Quiz:
        user_prompt = self.prompts.generate_user_prompt(
            story_id=story_id,
            story=story,
            question_count=question_count,
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.prompts.system_instruction,
                    temperature=0.6,
                    response_mime_type="application/json",
                    response_schema=Quiz,
                ),
            )

            if response.parsed:
                return response.parsed
            return Quiz.model_validate_json(response.text)
        except Exception as error:
            print(f"Error generating quiz: {error}")
            raise
