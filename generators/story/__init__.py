from .story_model import STORY_PAGE_COUNT, Page, Story, VocabularyEntry
from .story_prompts import StoryPrompt

__all__ = [
    "Page",
    "STORY_PAGE_COUNT",
    "Story",
    "StoryPrompt",
    "StoryGenerator",
    "VocabularyEntry",
]


def __getattr__(name: str):
    if name == "StoryGenerator":
        from .story_generator import StoryGenerator

        return StoryGenerator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
