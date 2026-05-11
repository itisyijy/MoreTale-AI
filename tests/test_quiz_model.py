import unittest

from generators.quiz.quiz_model import Quiz, QuizAnswer, QuizChoice, QuizQuestion


def _choice(choice_id: str, text: str) -> QuizChoice:
    return QuizChoice(choice_id=choice_id, text=text)


def _question(question_id: str, skill: str = "STORY") -> QuizQuestion:
    return QuizQuestion(
        question_id=question_id,
        type="multiple_choice",
        skill=skill,
        question_text=f"Question {question_id}?",
        choices=[
            _choice("1", "Answer"),
            _choice("2", "Choice B"),
            _choice("3", "Choice C"),
            _choice("4", "Choice D"),
        ],
        answer=QuizAnswer(choice_id="1", text="Answer"),
        explanation="Because the story says so.",
        source_page_numbers=[1],
        source_vocabulary_entry_ids=["festival"] if skill == "VOCABULARY" else [],
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
                _question("q2"),
                _question("q3"),
                _question("q4"),
                _question("q5", "VOCABULARY"),
            ],
        )

        self.assertEqual(len(quiz.questions), 5)
        self.assertEqual(quiz.questions[0].answer.choice_id, "1")
        self.assertEqual(quiz.questions[0].source_page_numbers, [1])

    def test_answer_must_match_choice(self) -> None:
        with self.assertRaises(ValueError):
            QuizQuestion(
                question_id="q1",
                type="multiple_choice",
                skill="STORY",
                question_text="Question?",
                choices=[
                    _choice("1", "Answer"),
                    _choice("2", "Choice B"),
                    _choice("3", "Choice C"),
                    _choice("4", "Choice D"),
                ],
                answer=QuizAnswer(choice_id="1", text="Missing"),
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
                    _question("q1", "VOCABULARY"),
                    _question("q2", "VOCABULARY"),
                    _question("q3"),
                    _question("q4"),
                    _question("q5"),
                ],
            )


if __name__ == "__main__":
    unittest.main()
