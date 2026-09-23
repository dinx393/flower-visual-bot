from contextlib import contextmanager
from dataclasses import dataclass, field
from time import monotonic
from typing import Iterator


@dataclass
class TimingReport:
    stages_ms: dict[str, int] = field(default_factory=dict)

    @property
    def total_ms(self) -> int:
        return sum(self.stages_ms.values())

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        started = monotonic()
        try:
            yield
        finally:
            self.stages_ms[stage] = round((monotonic() - started) * 1000)
