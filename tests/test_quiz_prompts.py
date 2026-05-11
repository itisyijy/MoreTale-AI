import unittest

from generators.quiz.quiz_prompts import QuizPrompt
from generators.story.story_model import STORY_PAGE_COUNT, Page, Story, VocabularyEntry


def _build_story(vocabulary: bool = True) -> Story:
    pages = []
    for page_number in range(1, STORY_PAGE_COUNT + 1):
        entries = []
        if vocabulary:
            entries.append(
                VocabularyEntry(
                    entry_id=f"page-{page_number}-festival",
                    primary_word="축제",
                    secondary_word="festival",
                    primary_definition="모두가 함께 즐기는 큰 행사.",
                    secondary_definition="A big event where everyone celebrates together.",
                )
            )
        pages.append(
            Page(
                page_number=page_number,
                text_primary=f"Primary text {page_number}",
                text_secondary=f"Secondary text {page_number}",
                illustration_prompt=f"Illustration prompt {page_number}",
                vocabulary=entries,
            )
        )
    return Story(
        title_primary="리아의 특별한 연",
        title_secondary="Lia's Special Kite",
        author_name="AI",
        primary_language="Korean",
        secondary_language="English",
        image_style="Watercolor",
        main_character_design="A child",
        pages=pages,
    )


class TestQuizPrompt(unittest.TestCase):
    def test_loads_and_formats_quiz_prompt(self) -> None:
        prompt = QuizPrompt()

        system_instruction = prompt.system_instruction
        user_prompt = prompt.generate_user_prompt(
            story_id="story-1",
            story=_build_story(),
            question_count=5,
        )

        self.assertIn("reading-comprehension quizzes", system_instruction)
        self.assertIn("story-1", user_prompt)
        self.assertIn("리아의 특별한 연", user_prompt)
        self.assertIn("festival", user_prompt)
        self.assertIn("VOCABULARY", user_prompt)
        self.assertIn("STORY", user_prompt)

    def test_formats_prompt_without_vocabulary_entries(self) -> None:
        prompt = QuizPrompt()

        user_prompt = prompt.generate_user_prompt(
            story_id="story-1",
            story=_build_story(vocabulary=False),
            question_count=5,
        )

        self.assertIn('"vocabulary": []', user_prompt)


if __name__ == "__main__":
    unittest.main()
