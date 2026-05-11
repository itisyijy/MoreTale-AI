from generators.critic.critic_model import CriticIssue, CriticResult

__all__ = ["CriticGenerator", "CriticResult", "CriticIssue"]


def __getattr__(name: str):
    if name == "CriticGenerator":
        from generators.critic.critic_generator import CriticGenerator

        return CriticGenerator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
