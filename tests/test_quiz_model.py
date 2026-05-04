import unittest

from generators.quiz.quiz_model import Quiz, QuizAnswer, QuizChoice, QuizQuestion


def _choice(choice_id: str, text: str) -> QuizChoice:
    return QuizChoice(choice_id=choice_id, text=text)


def _question(question_id: str, skill: str = "story_comprehension") -> QuizQuestion:
    return QuizQuestion(
        question_id=question_id,
        type="multiple_choice",
        skill=skill,
        question_text=f"Question {question_id}?",
        choices=[
            _choice("a", "Answer"),
            _choice("b", "Choice B"),
            _choice("c", "Choice C"),
            _choice("d", "Choice D"),
        ],
        answer=QuizAnswer(choice_id="a", text="Answer"),
        explanation="Because the story says so.",
        source_page_numbers=[1],
        source_vocabulary_entry_ids=["festival"] if skill == "vocabulary_in_context" else [],
    )


class TestQuizModel(unittest.TestCase):
    def test_valid_quiz_creation(self) -> None:
        quiz = Quiz(
            story_id="story-1",
            story_title_primary="Primary",
            story_title_secondary="Secondary",
            primary_language="Korean",
            secondary_language="English",
            question_count=5,
            questions=[
                _question("q1"),
                _question("q2", "cause_and_effect"),
                _question("q3", "character_emotion"),
                _question("q4", "sequence"),
                _question("q5", "vocabulary_in_context"),
            ],
        )

        self.assertEqual(len(quiz.questions), 5)
        self.assertEqual(quiz.questions[0].answer.choice_id, "a")
        self.assertEqual(quiz.questions[0].source_page_numbers, [1])

    def test_answer_must_match_choice(self) -> None:
        with self.assertRaises(ValueError):
            QuizQuestion(
                question_id="q1",
                type="multiple_choice",
                skill="story_comprehension",
                question_text="Question?",
                choices=[
                    _choice("a", "Answer"),
                    _choice("b", "Choice B"),
                    _choice("c", "Choice C"),
                    _choice("d", "Choice D"),
                ],
                answer=QuizAnswer(choice_id="z", text="Missing"),
                explanation="Because.",
                source_page_numbers=[1],
            )

    def test_quiz_requires_vocabulary_in_context_question(self) -> None:
        with self.assertRaises(ValueError):
            Quiz(
                story_id="story-1",
                story_title_primary="Primary",
                story_title_secondary="Secondary",
                primary_language="Korean",
                secondary_language="English",
                question_count=1,
                questions=[_question("q1")],
            )

    def test_five_question_quiz_requires_exactly_one_vocabulary_question(self) -> None:
        with self.assertRaises(ValueError):
            Quiz(
                story_id="story-1",
                story_title_primary="Primary",
                story_title_secondary="Secondary",
                primary_language="Korean",
                secondary_language="English",
                question_count=5,
                questions=[
                    _question("q1", "vocabulary_in_context"),
                    _question("q2", "vocabulary_in_context"),
                    _question("q3", "character_emotion"),
                    _question("q4", "sequence"),
                    _question("q5", "story_comprehension"),
                ],
            )


if __name__ == "__main__":
    unittest.main()
