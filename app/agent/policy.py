from app.rendering.strategy import choose_rendering_profile

from .knowledge import knowledge_cache
from .memory import case_memory_cache
from .explainability import build_decision_passport
from .contracts import (
    GenerationPlan,
    InterventionLevel,
    ReviewDecision,
    StoryRequest,
    TaskType,
)


def build_plan(request: StoryRequest, intervention: InterventionLevel | None) -> GenerationPlan:
    if request.review_feedback and request.review_feedback.decision is ReviewDecision.APPROVED:
        raise ValueError("An approved version must be published, not sent for another generation.")

    rendering = choose_rendering_profile(request, intervention)
    if request.price is None and request.task_type is TaskType.NEW_STORY:
        price_rule = "Price is absent: do not invent or display a price."
    else:
        price_rule = f"Use this exact price/text when applicable: {request.price or request.mandatory_text}."

    feedback_lines: list[str] = []
    if request.review_feedback:
        feedback_lines.append(
            f"Review decision: {request.review_feedback.decision.value}. This is not approval."
        )
        if request.review_feedback.comment:
            feedback_lines.append(f"Review comment: {request.review_feedback.comment}")
        for note in request.review_feedback.annotations:
            feedback_lines.append(
                "Marked region "
                f"x={note.x:.3f}, y={note.y:.3f}, width={note.width:.3f}, height={note.height:.3f}: "
                f"{note.instruction}"
            )

    knowledge = knowledge_cache.get()
    case_memory = case_memory_cache.get()
    memory_query = " ".join(
        part for part in (
            request.user_instruction,
            request.mandatory_text,
            request.visual_context,
        ) if part
    )
    relevant_cases = case_memory_cache.retrieve(memory_query)
    passport = build_decision_passport(
        request,
        intervention,
        knowledge,
        case_memory.version,
        relevant_cases,
    )
    memory_lines: tuple[str, ...] = ()
    if relevant_cases:
        memory_lines = (
            "Relevant experience records follow. Use their decisions and failure reasons; do not copy their layout mechanically:",
            *(f"## Memory source: {record.source_path}\n{record.text}" for record in relevant_cases),
        )
    prompt = "\n".join(
        (
            "Edit the supplied original image only according to this complete versioned knowledge snapshot:",
            knowledge.text,
            *memory_lines,
            f"Task: {request.task_type.value}.",
            f"Intervention level: {intervention.value if intervention else 'not applicable'}.",
            price_rule,
            f"Employee instruction: {request.user_instruction}",
            *feedback_lines,
            "Do not alter the factual identity of the product or any visible person.",
        )
    )
    return GenerationPlan(
        task_type=request.task_type,
        intervention=intervention,
        prompt=prompt,
        render_strategy=rendering.strategy,
        model=rendering.model,
        quality=rendering.quality,
        deadline_seconds=rendering.deadline_seconds,
        max_attempts=rendering.max_attempts,
        knowledge_version=knowledge.version,
        case_memory_version=case_memory.version,
        reference_case_ids=tuple(record.record_id for record in relevant_cases),
        reference_image_paths=case_memory_cache.existing_image_paths(relevant_cases),
        decision_passport=passport,
    )
