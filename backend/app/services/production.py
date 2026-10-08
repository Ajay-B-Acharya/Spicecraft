"""Request-local execution budgets and diagnostics; no mutable circuit cache."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, fields
import json
import logging
import math
import os
from time import perf_counter

from app.services.asc_validation import ERROR, AscExportError, ExportDiagnostic

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineLimits:
    max_components: int = 500
    max_pins: int = 4000
    max_nets: int = 4000
    max_wires: int = 10000
    max_routing_segments: int = 20000
    max_layout_iterations: int = 1000000
    max_routing_iterations: int = 2000000
    max_optimization_iterations: int = 2000000
    max_export_bytes: int = 4000000
    max_input_bytes: int = 2000000
    request_body_seconds: float = 10.0
    max_input_items: int = 100000
    max_input_depth: int = 32
    max_string_length: int = 4096
    max_coordinate: int = 10000000
    layout_seconds: float = 5.0
    routing_seconds: float = 10.0
    optimization_seconds: float = 5.0
    total_seconds: float = 30.0

    def __post_init__(self):
        for item in fields(self):
            value = getattr(self, item.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{item.name} must be finite and positive")
            if item.name.startswith('max_') and not isinstance(value, int):
                raise ValueError(f"{item.name} must be an integer")

    @classmethod
    def from_environment(cls):
        values = {}
        for item in fields(cls):
            raw = os.getenv('SPICECRAFT_' + item.name.upper())
            if raw is not None:
                values[item.name] = float(raw) if item.name.endswith('_seconds') else int(raw)
        return cls(**values)


def circuit_size(count: int | None) -> str:
    if type(count) is not int or count < 1:
        return 'unknown'
    return 'small' if count <= 20 else 'medium' if count <= 100 else 'large' if count <= 500 else 'extreme'


class PipelineError(AscExportError):
    def __init__(self, code: str, message: str, *, stage: str, circuit=None, component=None, pin=None, net=None):
        self.stage = stage
        super().__init__([ExportDiagnostic(ERROR, code, message, circuit=circuit, component=component, pin=pin, net=net, stage=stage)])


@dataclass
class Execution:
    limits: PipelineLimits
    circuit_id: str = ''
    debug: bool = False
    started: float = field(default_factory=perf_counter)
    stage: str = 'input_validation'
    stage_started: float = field(default_factory=perf_counter)
    timings: dict[str, float] = field(default_factory=dict)
    iterations: dict[str, int] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)

    def check(self, *, iterations=0, segments=None):
        now = perf_counter()
        seconds = getattr(self.limits, self.stage + '_seconds', self.limits.total_seconds)
        stage_seconds = self.timings.get(self.stage, 0.0) / 1000 + now - self.stage_started
        if now - self.started > self.limits.total_seconds or stage_seconds > seconds:
            raise PipelineError('PIPELINE_TIMEOUT', f'{self.stage} exceeded its execution budget ({seconds:g} seconds stage / {self.limits.total_seconds:g} seconds total)', stage=self.stage, circuit=self.circuit_id)
        self.iterations[self.stage] = self.iterations.get(self.stage, 0) + iterations
        limit = getattr(self.limits, 'max_' + self.stage + '_iterations', None)
        if limit is not None and self.iterations[self.stage] > limit:
            raise PipelineError('RESOURCE_LIMIT', f'{self.stage} exceeded {limit} iterations', stage=self.stage, circuit=self.circuit_id)
        if segments is not None:
            self.require('routing_segments', segments)

    def transition(self, stage):
        self.check()
        now = perf_counter()
        self.timings[self.stage] = self.timings.get(self.stage, 0.0) + (now - self.stage_started) * 1000
        self.stage, self.stage_started = stage, now

    def require(self, resource, count):
        limit = getattr(self.limits, 'max_' + resource)
        if count > limit:
            raise PipelineError('RESOURCE_LIMIT', f'{resource}: {count} exceeds configured limit {limit}', stage=self.stage, circuit=self.circuit_id)

    @contextmanager
    def measure(self, stage):
        previous, previous_started = self.stage, self.stage_started
        self.stage, self.stage_started = stage, perf_counter()
        try:
            self.check()
            yield
            self.check()
        finally:
            self.timings[stage] = self.timings.get(stage, 0.0) + (perf_counter() - self.stage_started) * 1000
            self.stage, self.stage_started = previous, previous_started

    def report(self, diagnostics=()):
        return dict(circuitId=self.circuit_id, **self.counts,
                    classification=circuit_size(self.counts.get('componentCount', 0)),
                    stagesMs={key: round(value, 3) for key, value in self.timings.items()},
                    totalTimeMs=round((perf_counter() - self.started) * 1000, 3),
                    warningCount=sum(d.severity == 'warning' for d in diagnostics),
                    errorCount=sum(d.severity == ERROR for d in diagnostics),
                    iterations=dict(self.iterations))


_CURRENT: ContextVar[Execution | None] = ContextVar('spicecraft_execution', default=None)


def current_execution():
    return _CURRENT.get()


def checkpoint(stage=None, *, iterations=0, segments=None):
    execution = _CURRENT.get()
    if execution is not None:
        execution.check(iterations=iterations, segments=segments)


@contextmanager
def execution_context(execution):
    token = _CURRENT.set(execution)
    try:
        yield execution
    finally:
        _CURRENT.reset(token)


def log_report(event, report):
    level = logging.ERROR if report.get('errorCount', 0) else logging.WARNING if report.get('warningCount', 0) else logging.INFO
    logger.log(level, json.dumps(dict(event=event, **report), sort_keys=True, allow_nan=False))
