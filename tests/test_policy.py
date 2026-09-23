from app.agent.contracts import (
    InterventionLevel,
    RenderStrategy,
    ReviewDecision,
    ReviewFeedback,
    StoryRequest,
    TaskType,
    VisualAnnotation,
)
from app.agent.policy import build_plan
from app.agent.knowledge import KnowledgeCache
from app.agent.memory import CaseMemoryCache
from app.agent.explainability import explain_plan
from pathlib import Path
from tempfile import TemporaryDirectory
from app.quality_control.review import may_publish


def test_new_story_without_price_explicitly_forbids_invention() -> None:
    plan = build_plan(
        StoryRequest("source-1", TaskType.NEW_STORY, "Создай сторис"),
        InterventionLevel.GENTLE,
    )
    assert "do not invent or display a price" in plan.prompt


def test_request_price_is_preserved_verbatim() -> None:
    plan = build_plan(
        StoryRequest("source-1", TaskType.NEW_STORY, "Создай сторис", price="12 500 р"),
        InterventionLevel.CREATIVE,
    )
    assert "12 500 р" in plan.prompt


def test_gentle_story_uses_the_standard_generator_once() -> None:
    plan = build_plan(
        StoryRequest("source-1", TaskType.NEW_STORY, "Создай сторис", price="165 р"),
        InterventionLevel.GENTLE,
    )
    assert plan.render_strategy is RenderStrategy.GENERATIVE_EDIT
    assert plan.model == "gpt-image-2.5-flare"
    assert plan.quality == "medium"
    assert plan.deadline_seconds == 120
    assert plan.max_attempts == 1


def test_creative_story_uses_the_same_standard_generator_once() -> None:
    plan = build_plan(
        StoryRequest("source-1", TaskType.NEW_STORY, "Создай сторис"),
        InterventionLevel.CREATIVE,
    )
    assert plan.render_strategy is RenderStrategy.GENERATIVE_EDIT
    assert plan.model == "gpt-image-2.5-flare"
    assert plan.quality == "medium"
    assert plan.max_attempts == 1


def test_marked_regions_are_revision_instructions_not_approval() -> None:
    feedback = ReviewFeedback(
        decision=ReviewDecision.REVISION_REQUESTED,
        comment="Исправь подпись и цену.",
        annotations=(
            VisualAnnotation("Increase headline size.", 0.04, 0.12, 0.35, 0.15),
            VisualAnnotation("Move and enlarge price.", 0.58, 0.66, 0.34, 0.20),
        ),
    )
    plan = build_plan(
        StoryRequest("version-2", TaskType.TARGETED_EDIT, "Внести отмеченные правки", review_feedback=feedback),
        None,
    )
    assert "This is not approval" in plan.prompt
    assert "x=0.040, y=0.120" in plan.prompt
    assert not may_publish(feedback)


def test_only_explicit_approval_allows_publication() -> None:
    assert may_publish(ReviewFeedback(decision=ReviewDecision.APPROVED))
    assert not may_publish(None)


def test_approved_version_cannot_be_regenerated() -> None:
    approved = ReviewFeedback(decision=ReviewDecision.APPROVED)
    try:
        build_plan(StoryRequest("version-2", TaskType.TARGETED_EDIT, "", review_feedback=approved), None)
    except ValueError as error:
        assert "approved version" in str(error)
    else:
        raise AssertionError("Approved version must not produce a generation plan")


def test_only_changed_knowledge_document_is_reread() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        first_path = root / "visual-dna.md"
        second_path = root / "copy-rules.md"
        first_path.write_text("first rule", encoding="utf-8")
        second_path.write_text("second rule", encoding="utf-8")
        reads: list[Path] = []

        def reader(item: Path) -> str:
            reads.append(item)
            return item.read_text(encoding="utf-8")

        cache = KnowledgeCache(root, reader)
        first = cache.get()
        second = cache.get()
        assert first is second
        assert len(reads) == 2
        assert "first rule" in first.text
        assert "second rule" in first.text

        second_path.write_text("changed second rule", encoding="utf-8")
        third = cache.get()
        assert len(reads) == 3
        assert third.version != first.version

        (root / "new-rule.md").write_text("new rule", encoding="utf-8")
        fourth = cache.get()
        assert len(reads) == 4
        assert "new rule" in fourth.text

        first_path.unlink()
        fifth = cache.get()
        assert len(reads) == 4
        assert "first rule" not in fifth.text


def test_generation_plan_records_the_policy_version() -> None:
    plan = build_plan(
        StoryRequest("source-1", TaskType.NEW_STORY, "Создай сторис"),
        InterventionLevel.GENTLE,
    )
    assert len(plan.knowledge_version) == 12
    assert "# Source: visual-dna.md" in plan.prompt


def test_case_memory_rereads_only_the_changed_record() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        tests_dir = root / "tests"
        history_dir = root / "database" / "case-history"
        tests_dir.mkdir()
        history_dir.mkdir(parents=True)
        approved = tests_dir / "approved-case-001-lilies.md"
        history = history_dir / "lilies.md"
        approved.write_text("# Шикарные лилии\n\nБелые лилии и оливковый текст.", encoding="utf-8")
        history.write_text("# История лилий\n\nЧёрный текст был отклонён.", encoding="utf-8")
        reads: list[Path] = []

        def reader(item: Path) -> str:
            reads.append(item)
            return item.read_text(encoding="utf-8")

        memory = CaseMemoryCache(root, reader)
        first = memory.get()
        second = memory.get()
        assert first is second
        assert len(reads) == 2

        history.write_text("# История лилий\n\nТёмный текст был отклонён.", encoding="utf-8")
        changed = memory.get()
        assert len(reads) == 3
        assert changed.version != first.version


def test_relevant_case_memory_is_added_to_generation_plan() -> None:
    plan = build_plan(
        StoryRequest(
            "source-lilies",
            TaskType.NEW_STORY,
            "Шикарные лилии",
            price="210р",
            visual_context="бело-зелёный букет лилий в руках",
        ),
        InterventionLevel.GENTLE,
    )
    assert "approved-case-004-shikarnye-lilii" in plan.reference_case_ids
    assert "tests/fixtures/approved/case-004-shikarnye-lilii.png" in plan.reference_image_paths
    assert len(plan.reference_image_paths) == len(set(plan.reference_image_paths))
    assert "Relevant experience records follow" in plan.prompt
    assert len(plan.case_memory_version) == 12


def test_generation_plan_has_an_exact_decision_passport() -> None:
    plan = build_plan(
        StoryRequest(
            "source-lilies",
            TaskType.NEW_STORY,
            "Шикарные лилии",
            price="210р",
            visual_context="бело-зелёный букет лилий в руках",
        ),
        InterventionLevel.GENTLE,
    )
    passport = plan.decision_passport
    assert passport is not None
    assert passport.knowledge_version == plan.knowledge_version
    assert passport.case_memory_version == plan.case_memory_version
    assert any(item.source_path == "knowledge/visual-dna.md" for item in passport.rules)
    assert any(item.source_path == "tests/approved-case-004-shikarnye-lilii.md" for item in passport.references)
    assert any(item.source_path == "database/case-history/lilies-210r-2026-09-13.md" for item in passport.anti_lessons)
    explanation = explain_plan(plan)
    assert "210р" in explanation
    assert "tests/approved-case-004-shikarnye-lilii.md" in explanation
    assert "не копировать весь макет" in explanation
