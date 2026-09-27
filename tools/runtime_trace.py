"""Bounded, default-off diagnostic spans; no request contents or hot-path I/O.

Use one K230_TRACE_ID and distinct K230_TRACE_PATH files per process. Only the
helper daemon initializes this module. One-shot theme commands remain disabled.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import itertools
import json
import os
import re
import threading
import time

CAPACITY = 65536
_parent = ContextVar("runtime_trace_parent", default=0)
_recorder = None


def now_us():
    return time.monotonic_ns() // 1000


class Recorder:
    def __init__(self, trace_id, seconds, capacity=CAPACITY):
        if not isinstance(trace_id, str) or not re.fullmatch(r"[0-9a-f]{32}", trace_id):
            raise ValueError("trace ID must be 32 lowercase hexadecimal digits")
        if not 10 <= seconds <= 180:
            raise ValueError("trace duration must be 10..180 seconds")
        self.trace_id = trace_id
        self.pid = os.getpid()
        self.deadline = now_us() + seconds * 1000000
        self.capacity = capacity
        self.events = []
        self.dropped = 0
        self.active = True
        self.counter = itertools.count(1)
        self.lock = threading.Lock()
        self.file = None

    def record(self, event):
        with self.lock:
            if not self.active:
                return
            if len(self.events) < self.capacity:
                self.events.append(event)
            else:
                self.dropped += 1

    def finish(self):
        with self.lock:
            self.active = False
            events, self.events = self.events, []
            return dict(schema=1, clock="CLOCK_MONOTONIC", trace_id=self.trace_id,
                        pid=self.pid, capacity=self.capacity, deadline_us=self.deadline,
                        finished_us=now_us(), dropped=self.dropped, events=events)


def init():
    global _recorder
    path = os.environ.get("K230_TRACE_PATH")
    if not path:
        return
    if _recorder is not None:
        raise ValueError("trace already initialized")
    recorder = Recorder(os.environ.get("K230_TRACE_ID", f"{os.getpid():016x}{now_us():016x}"),
                        int(os.environ.get("K230_TRACE_SECONDS", "120")))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    recorder.file = os.fdopen(fd, "w")
    _recorder = recorder


def finish_if_due():
    recorder = _recorder
    if recorder is None or not recorder.active or now_us() < recorder.deadline:
        return
    report = recorder.finish()
    with recorder.file as output:
        json.dump(report, output, separators=(",", ":"))
        output.write("\n")


@contextmanager
def span(kind):
    recorder = _recorder
    if recorder is None or not recorder.active:
        yield
        return
    parent = _parent.get()
    identity = (recorder.pid << 32) | next(recorder.counter)
    token = _parent.set(identity)
    start, cpu = now_us(), time.thread_time_ns() // 1000
    try:
        yield
    finally:
        end, cpu_end = now_us(), time.thread_time_ns() // 1000
        _parent.reset(token)
        recorder.record(dict(span_id=identity, parent_span_id=parent, kind=kind,
                             start_us=start, end_us=end, cpu_us=max(0, cpu_end - cpu),
                             tid=threading.get_native_id(), data=[0] * 6))


def traced(kind):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if _recorder is None or not _recorder.active:
                return function(*args, **kwargs)
            with span(kind):
                return function(*args, **kwargs)
        return wrapped
    return decorate


@contextmanager
def remote_parent(context):
    """Invalid/unrelated context never changes request semantics or traces."""
    recorder = _recorder
    parent = None
    if recorder is not None and recorder.active and isinstance(context, dict):
        value = context.get("parent_span_id")
        if (context.get("trace_id") == recorder.trace_id and isinstance(value, str)
                and re.fullmatch(r"[0-9a-f]{16}", value)):
            parent = int(value, 16)
    token = _parent.set(parent or 0)
    try:
        yield
    finally:
        _parent.reset(token)
