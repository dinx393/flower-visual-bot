"""Build a factual, human-readable passport for every design decision."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .contracts import (
    DecisionEvidence,
    DecisionPassport,
    GenerationPlan,
    InterventionLevel,
    StoryRequest,
)
from .knowledge import KnowledgeSnapshot
from .memory import MemoryRecord, _related, _tokens


@dataclass(frozen=True)
class _KnowledgeDocument:
    path: str
    text: str


def _documents(snapshot: KnowledgeSnapshot) -> tuple[_KnowledgeDocument, ...]:
    return tuple(
        _KnowledgeDocument(f"knowledge/{name}", text)
        for name, text in snapshot.documents
    )


def _document(documents: Iterable[_KnowledgeDocument], suffix: str) -> _KnowledgeDocument:
    for document in documents:
        if document.path.endswith(suffix):
            return document
    raise ValueError(f"Missing required knowledge document: {suffix}")


def _line_with(text: str, fragment: str) -> str:
    for line in text.splitlines():
        if fragment.casefold() in line.casefold():
            return line.strip().lstrip("- ").strip()
    raise ValueError(f"Missing expected knowledge evidence: {fragment}")


def _section_after(text: str, heading: str) -> str:
    lines = text.splitlines()
    target = f"## {heading}".casefold()
    for index, line in enumerate(lines):
        if line.strip().casefold() == target:
            for candidate in lines[index + 1:]:
                stripped = candidate.strip()
                if stripped.startswith("#"):
                    break
                if stripped:
                    return stripped.lstrip("- ").strip()
    raise ValueError(f"Missing expected knowledge section: {heading}")


def _first_case_lesson(record: MemoryRecord) -> str:
    """Return an exact accepted decision rather than inventing an interpretation."""
    lines = record.text.splitlines()
    preferred_sections = ("## Принятое решение", "## Что принято", "## Что можно использовать как ориентир")
    for heading in preferred_sections:
        try:
            return _section_after(record.text, heading.removeprefix("## "))
        except ValueError:
            continue
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            return stripped.removeprefix("- ").strip()
    return record.title


def _rejections(record: MemoryRecord) -> tuple[str, ...]:
    findings: list[str] = []
    for line in record.text.splitlines():
        stripped = line.strip()
        if "отклонено:" in stripped.casefold():
            findings.append(stripped.split(":", 1)[1].strip())
    return tuple(findings)


def _matched_terms(request: StoryRequest, record: MemoryRecord) -> str:
    query = " ".join(
        part for part in (request.user_instruction, request.mandatory_text, request.visual_context) if part
    )
    matches = sorted(
        query_token
        for query_token in _tokens(query)
        if any(_related(query_token, token) for token in record.title_tokens | record.body_tokens)
    )
    return ", ".join(matches[:4]) or "задача и визуальный контекст"


def build_decision_passport(
    request: StoryRequest,
    intervention: InterventionLevel | None,
    knowledge: KnowledgeSnapshot,
    case_memory_version: str,
    relevant_cases: tuple[MemoryRecord, ...],
) -> DecisionPassport:
    """Create traceable evidence at planning time, before an image is generated."""
    documents = _documents(knowledge)
    visual_dna = _document(documents, "visual-dna.md")
    intervention_rules = _document(documents, "intervention-rules.md")
    copy_rules = _document(documents, "copy-rules.md")

    rules: list[DecisionEvidence] = [
        DecisionEvidence(
            category="rule",
            source_path=visual_dna.path,
            label="Неприкосновенность товара",
            used_for="Сохранить тот же товар, упаковку, человека и масштаб кадра.",
            excerpt=_line_with(visual_dna.text, "Не добавлять, удалять"),
        ),
        DecisionEvidence(
            category="rule",
            source_path=copy_rules.path,
            label="Только подтверждённые данные",
            used_for="Не придумывать цену, состав, сорт, дату или повод.",
            excerpt=_line_with(copy_rules.text, "Не угадывать цену"),
        ),
    ]
    if intervention is not None:
        titles = {
            InterventionLevel.GENTLE: "Бережный",
            InterventionLevel.CREATIVE: "Творческий",
            InterventionLevel.RESCUE: "Спасательный",
        }
        rules.append(
            DecisionEvidence(
                category="rule",
                source_path=intervention_rules.path,
                label=f"Уровень вмешательства: {titles[intervention]}",
                used_for="Определить допустимую степень изменения исходного кадра.",
                excerpt=_section_after(intervention_rules.text, titles[intervention]),
            )
        )
    if request.price:
        rules.append(
            DecisionEvidence(
                category="rule",
                source_path=visual_dna.path,
                label="Цена как читаемый вторичный акцент",
                used_for=f"Показать переданную цену {request.price!r}, не превращая её в микроподпись.",
                excerpt=_line_with(visual_dna.text, "Цена — читаемый вторичный акцент"),
            )
        )

    references = tuple(
        DecisionEvidence(
            category="reference",
            source_path=record.source_path,
            label=record.title,
            used_for=(
                "Взять только конкретное решение из кейса, а не копировать весь макет. "
                f"Совпадения с текущей задачей: {_matched_terms(request, record)}."
            ),
            excerpt=_first_case_lesson(record),
        )
        for record in relevant_cases
        if record.kind == "approved_case"
    )
    anti_lessons = tuple(
        DecisionEvidence(
            category="anti_lesson",
            source_path=record.source_path,
            label=record.title,
            used_for="Не повторять отклонённое решение из похожей работы.",
            excerpt=lesson,
        )
        for record in relevant_cases
        if record.kind == "case_history"
        for lesson in _rejections(record)[:2]
    )

    employee_directions: list[DecisionEvidence] = [
        DecisionEvidence(
            category="employee_direction",
            source_path="request.user_instruction",
            label="Задание сотрудника",
            used_for="Это прямое задание для текущего макета.",
            excerpt=request.user_instruction,
        )
    ]
    if request.review_feedback and request.review_feedback.comment:
        employee_directions.append(
            DecisionEvidence(
                category="employee_direction",
                source_path="request.review_feedback.comment",
                label="Текстовая правка сотрудника",
                used_for="Изменить только обозначенные элементы; это не является одобрением.",
                excerpt=request.review_feedback.comment,
            )
        )
    for annotation in (request.review_feedback.annotations if request.review_feedback else ()):
        employee_directions.append(
            DecisionEvidence(
                category="employee_direction",
                source_path="request.review_feedback.annotations",
                label="Размеченная область",
                used_for=(
                    f"Область x={annotation.x:.3f}, y={annotation.y:.3f}, "
                    f"width={annotation.width:.3f}, height={annotation.height:.3f}."
                ),
                excerpt=annotation.instruction,
            )
        )

    return DecisionPassport(
        knowledge_version=knowledge.version,
        case_memory_version=case_memory_version,
        rules=tuple(rules),
        references=references,
        anti_lessons=anti_lessons,
        employee_directions=tuple(employee_directions),
    )


def explain_plan(plan: GenerationPlan) -> str:
    """Return the same stored rationale any chat can send to an employee."""
    passport = plan.decision_passport
    if passport is None:
        raise ValueError("This generation plan has no recorded decision passport.")

    def block(title: str, entries: tuple[DecisionEvidence, ...]) -> list[str]:
        if not entries:
            return []
        lines = [title]
        for entry in entries:
            lines.extend((
                f"- {entry.label} — {entry.used_for}",
                f"  Источник: {entry.source_path}",
                f"  Основание: {entry.excerpt}",
            ))
        return lines

    lines = [
        "На что я опирался при создании дизайна",
        f"Версия правил: {passport.knowledge_version}; версия памяти кейсов: {passport.case_memory_version}.",
        *block("\nАктивные правила:", passport.rules),
        *block("\nРеференсы:", passport.references),
        *block("\nАнти-уроки:", passport.anti_lessons),
        *block("\nПрямые указания сотрудника:", passport.employee_directions),
    ]
    if passport.references:
        lines.append("\nРеференсы использованы как доказательства отдельных решений, а не как шаблоны для копирования макета.")
    return "\n".join(lines)
