__all__ = ["IllustrationGenerator"]


def __getattr__(name: str):
    if name == "IllustrationGenerator":
        from .illustration_pipeline import IllustrationGenerator

        return IllustrationGenerator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
