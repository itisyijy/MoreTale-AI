import unittest

from pydantic import ValidationError

from generators.story.story_generator import StoryGenerator
from generators.story.story_model import STORY_PAGE_COUNT, Page, Story, VocabularyEntry


class TestStoryValidation(unittest.TestCase):
    def setUp(self):
        self.valid_page = Page(
            page_number=1,
            text_primary="Test primary",
            text_secondary="Test secondary",
            illustration_prompt="Test illustration",
        )

    def test_valid_story_creation(self):
        story = Story(
            title_primary="Test Title",
            title_secondary="Test Title 2",
            author_name="AI",
            primary_language="Korean",
            secondary_language="English",
            image_style="Watercolor",
            main_character_design="Boy",
            pages=[
                self.valid_page.model_copy(update={"page_number": i + 1})
                for i in range(STORY_PAGE_COUNT)
            ],
        )
        self.assertEqual(len(story.pages), STORY_PAGE_COUNT)

    def test_shorter_age_adjusted_story_creation(self):
        pages = [
            self.valid_page.model_copy(update={"page_number": i + 1})
            for i in range(2)
        ]

        story = Story(
            title_primary="Test Title",
            title_secondary="Test Title 2",
            author_name="AI",
            primary_language="Korean",
            secondary_language="English",
            image_style="Watercolor",
            main_character_design="Boy",
            pages=pages,
        )

        self.assertEqual(len(story.pages), 2)

    def test_invalid_page_count_high(self):
        pages = [
            self.valid_page.model_copy(update={"page_number": i + 1})
            for i in range(STORY_PAGE_COUNT + 1)
        ]

        with self.assertRaises(ValidationError) as context:
            Story(
                title_primary="Test Title",
                title_secondary="Test Title 2",
                author_name="AI",
                primary_language="Korean",
                secondary_language="English",
                image_style="Watercolor",
                main_character_design="Boy",
                pages=pages,
            )

        self.assertIn("at most 32 items", str(context.exception))

    def test_invalid_page_sequence(self):
        pages = [
            self.valid_page.model_copy(update={"page_number": 1}),
            self.valid_page.model_copy(update={"page_number": 3}),
        ]

        with self.assertRaises(ValueError) as context:
            Story(
                title_primary="Test Title",
                title_secondary="Test Title 2",
                author_name="AI",
                primary_language="Korean",
                secondary_language="English",
                image_style="Watercolor",
                main_character_design="Boy",
                pages=pages,
            )

        self.assertIn("numbered sequentially", str(context.exception))

    def test_page_accepts_bilingual_vocabulary_entries(self):
        page = self.valid_page.model_copy(
            update={
                "vocabulary": [
                    VocabularyEntry(
                        primary_word="dragon",
                        secondary_word="용",
                        primary_definition="a large creature from stories",
                        secondary_definition="이야기 속에 나오는 큰 상상 동물",
                    )
                ]
            }
        )

        self.assertEqual(len(page.vocabulary), 1)
        self.assertEqual(page.vocabulary[0].primary_word, "dragon")
        self.assertEqual(page.vocabulary[0].secondary_word, "용")

    def test_vocabulary_entry_ids_are_page_order_based(self):
        story = Story(
            title_primary="우주 이야기",
            title_secondary="Space Story",
            author_name="AI",
            primary_language="Korean",
            secondary_language="Vietnamese",
            image_style="Watercolor",
            main_character_design="Child",
            pages=[
                self.valid_page.model_copy(
                    update={
                        "page_number": 1,
                        "vocabulary": [
                            VocabularyEntry(
                                entry_id="b-phi-h-nh-gia",
                                primary_word="우주복",
                                secondary_word="bộ đồ phi hành gia",
                                primary_definition="우주에서 입는 특별한 옷",
                                secondary_definition="áo đặc biệt mặc khi bay vào không gian",
                            ),
                            VocabularyEntry(
                                entry_id="th-v",
                                primary_word="신나는",
                                secondary_word="thú vị",
                                primary_definition="아주 즐겁고 기쁜",
                                secondary_definition="rất vui và hạnh phúc",
                            ),
                        ],
                    }
                ),
                self.valid_page.model_copy(
                    update={
                        "page_number": 2,
                        "vocabulary": [
                            VocabularyEntry(
                                entry_id=None,
                                primary_word="달",
                                secondary_word="mặt trăng",
                                primary_definition="밤하늘에 뜨는 둥근 구슬",
                                secondary_definition="quả cầu tròn trên bầu trời đêm",
                            )
                        ],
                    }
                ),
            ],
        )

        StoryGenerator._populate_vocabulary_fields(story)

        self.assertEqual(
            [entry.entry_id for entry in story.pages[0].vocabulary],
            ["page-01-word-01", "page-01-word-02"],
        )
        self.assertEqual(story.pages[1].vocabulary[0].entry_id, "page-02-word-01")


if __name__ == "__main__":
    unittest.main()
