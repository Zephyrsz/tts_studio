from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SynthesisOptions:
    model: str = 'google/gemini-3.8-flash-tts'
    format: str = 'wav'
    sample_rate: int = 24000
    timeout: float = 120
    instructions: str = ''


@dataclass(frozen=True)
class SynthesisRequest:
    mode: str
    model: str
    text: str
    voice: str | None
    reference_data: str | None = None
    reference_name: str | None = None
    reference_text: str | None = None
    options: SynthesisOptions = field(default_factory=SynthesisOptions)
    api_key: str = field(default='', repr=False)


@dataclass(frozen=True)
class BatchRequest:
    directory: str
    timestamp: int
    text: str
    voices: list[str]
    concurrency: int
    filename_prefix: str
    options: SynthesisOptions
    api_key: str = ''
    mode: str = 'preset'
    reference_data: str | None = None
    reference_name: str | None = None
    reference_text: str | None = None


@dataclass
class Task:
    id: str
    voice: str
    filename: str
    status: str = 'pending'
    error: str = ''
    generation_id: str = ''
    size: int = 0
    saved_path: str = ''
    started_at: float | None = None
    finished_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Batch:
    id: str
    directory: str
    timestamp: int
    text: str
    concurrency: int
    mode: str
    tasks: list[Task]
    status: str = 'running'
    stop_requested: bool = False
    error: str = ''
    api_key: str = field(default='', repr=False)
    options: SynthesisOptions = field(default_factory=SynthesisOptions, repr=False)
    reference_data: str | None = field(default=None, repr=False)
    reference_name: str | None = field(default=None, repr=False)
    reference_text: str | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id, 'directory': self.directory, 'timestamp': self.timestamp,
            'text': self.text, 'concurrency': self.concurrency, 'mode': self.mode,
            'status': self.status, 'stop_requested': self.stop_requested,
            'error': self.error, 'tasks': [task.to_dict() for task in self.tasks],
        }
