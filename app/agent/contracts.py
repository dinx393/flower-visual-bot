from dataclasses import dataclass
from enum import Enum


class TaskType(str, Enum):
    NEW_STORY = "new_story"
    TARGETED_EDIT = "targeted_edit"
    REMOVE_PRICE = "remove_price"
    ADAPT_FORMAT = "adapt_format"


class InterventionLevel(str, Enum):
    GENTLE = "gentle"
    CREATIVE = "creative"
    RESCUE = "rescue"


class RenderStrategy(str, Enum):
    GENERATIVE_EDIT = "generative_edit"


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    POSITIVE_FEEDBACK = "positive_feedback"
    REVISION_REQUESTED = "revision_requested"
    REJECTED = "rejected"


@dataclass(frozen=True)
class VisualAnnotation:
    """A normalised rectangle marked by an employee on the reviewed image."""

    instruction: str
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if not all(0 <= value <= 1 for value in (self.x, self.y, self.width, self.height)):
            raise ValueError("Annotation coordinates must be normalised between 0 and 1.")


@dataclass(frozen=True)
class ReviewFeedback:
    """Review state is explicit: a marked-up image never implies approval."""

    decision: ReviewDecision
    comment: str | None = None
    annotations: tuple[VisualAnnotation, ...] = ()


@dataclass(frozen=True)
class StoryRequest:
    source_image_id: str
    task_type: TaskType
    user_instruction: str
    price: str | None = None
    mandatory_text: str | None = None
    visual_context: str | None = None
    review_feedback: ReviewFeedback | None = None


@dataclass(frozen=True)
class DecisionEvidence:
    """One exact source used to make a design decision."""

    category: str  # rule | reference | anti_lesson | employee_direction
    source_path: str
    label: str
    used_for: str
    excerpt: str


@dataclass(frozen=True)
class DecisionPassport:
    """Auditable explanation created together with a generation plan."""

    knowledge_version: str
    case_memory_version: str
    rules: tuple[DecisionEvidence, ...] = ()
    references: tuple[DecisionEvidence, ...] = ()
    anti_lessons: tuple[DecisionEvidence, ...] = ()
    employee_directions: tuple[DecisionEvidence, ...] = ()


@dataclass(frozen=True)
class GenerationPlan:
    task_type: TaskType
    intervention: InterventionLevel | None
    prompt: str
    requires_human_approval: bool = True
    render_strategy: RenderStrategy = RenderStrategy.GENERATIVE_EDIT
    model: str = "gpt-image-2.5-flare"
    quality: str = "medium"
    deadline_seconds: int = 120
    max_attempts: int = 1
    knowledge_version: str = ""
    case_memory_version: str = ""
    reference_case_ids: tuple[str, ...] = ()
    reference_image_paths: tuple[str, ...] = ()
    decision_passport: DecisionPassport | None = None
