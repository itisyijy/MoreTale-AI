__all__ = ["TTSGenerator"]


def __getattr__(name: str):
    if name == "TTSGenerator":
        from .tts_generator import TTSGenerator

        return TTSGenerator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
