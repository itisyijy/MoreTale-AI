from generators.quiz.quiz_model import Quiz, QuizAnswer, QuizChoice, QuizQuestion
from generators.quiz.quiz_prompts import QuizPrompt

__all__ = [
    "Quiz",
    "QuizAnswer",
    "QuizChoice",
    "QuizGenerator",
    "QuizPrompt",
    "QuizQuestion",
]


def __getattr__(name: str):
    if name == "QuizGenerator":
        from generators.quiz.quiz_generator import QuizGenerator

        return QuizGenerator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
