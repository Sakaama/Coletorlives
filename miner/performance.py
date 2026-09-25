"""Per-operation timings and bounded model reuse; never shared across worker threads."""
import time
from contextlib import contextmanager
from contextvars import ContextVar

_state = ContextVar("miner_performance", default=None)


@contextmanager
def session():
    if _state.get() is not None:
        yield
        return
    token = _state.set({"timings": {}, "models": {}})
    try:
        yield
    finally:
        _state.reset(token)


@contextmanager
def measure(name):
    begin = time.perf_counter()
    try:
        yield
    finally:
        state = _state.get()
        if state is not None:
            state["timings"][name] = state["timings"].get(name, 0) + time.perf_counter()-begin


def timings():
    return dict((_state.get() or {}).get("timings", {}))


def model(key, factory):
    state = _state.get()
    if state is not None and key in state["models"]:
        return state["models"][key]
    with measure("whisper_load"):
        value = factory()
    if state is not None:
        # The pipeline selects a single model; CPU fallback may occupy one further entry.
        if len(state["models"]) >= 2:
            state["models"].clear()
        state["models"][key] = value
    return value
