from dataclasses import dataclass

from app.agent.contracts import (
    InterventionLevel,
    RenderStrategy,
    StoryRequest,
)


@dataclass(frozen=True)
class RenderingProfile:
    strategy: RenderStrategy
    model: str
    quality: str
    deadline_seconds: int
    max_attempts: int = 1


IMAGE_MODEL = "gpt-image-2.5-flare"
GENERATION_QUALITY = "medium"
GENERATION_DEADLINE_SECONDS = 120


def choose_rendering_profile(
    request: StoryRequest,
    intervention: InterventionLevel | None,
) -> RenderingProfile:
    """Every Story is generated once through the same production profile.

    Intervention changes the prompt, not the waiting time or visual quality.
    """
    return RenderingProfile(
        strategy=RenderStrategy.GENERATIVE_EDIT,
        model=IMAGE_MODEL,
        quality=GENERATION_QUALITY,
        deadline_seconds=GENERATION_DEADLINE_SECONDS,
    )
