from dataclasses import dataclass


@dataclass(frozen=True)
class QualityFinding:
    code: str
    severity: str  # blocking | warning
    message: str


@dataclass(frozen=True)
class QualityReport:
    passed: bool
    findings: tuple[QualityFinding, ...]


BLOCKING_CHECKS = (
    "product_identity_changed",
    "person_anatomy_error",
    "price_or_text_error",
    "wrong_aspect_ratio",
)
