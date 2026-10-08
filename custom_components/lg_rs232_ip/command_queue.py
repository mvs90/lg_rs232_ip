"""Give interactive device operations priority without interrupting in-flight I/O."""

import asyncio
from collections import deque
from contextvars import ContextVar
from functools import wraps

# Store the task, not a boolean: refresh tasks inherit context variables but
# must not inherit the originating action's interactive priority.
_ACTION_TASK = ContextVar("lg_action_task", default=None)


def interactive_command(method):
    """Keep prerequisite reads, mutation and readback at the same priority."""

    @wraps(method)
    async def wrapped(*args, **kwargs):
        token = _ACTION_TASK.set(asyncio.current_task())
        try:
            return await method(*args, **kwargs)
        finally:
            _ACTION_TASK.reset(token)

    return wrapped


class PriorityLock:
    """FIFO within each priority; one normal waiter after eight urgent grants.

    A running command is never cancelled or preempted: serial replies remain
    paired with their request. Cancellation releases a reserved handoff slot.
    The interface intentionally matches the asyncio.Lock usage in this project.
    """

    def __init__(self):
        self._locked = False
        self._urgent = deque()
        self._normal = deque()
        self._burst = 0

    def locked(self):
        return self._locked

    async def acquire(self):
        if not self._locked:
            self._locked = True
            return True
        urgent = _ACTION_TASK.get() is asyncio.current_task()
        queue = self._urgent if urgent else self._normal
        future = asyncio.get_running_loop().create_future()
        queue.append(future)
        try:
            await future
            return True
        except asyncio.CancelledError:
            if not future.cancelled():
                # This task was granted the lock, then cancelled before resuming.
                self._wake_next()
            raise
        finally:
            try:
                queue.remove(future)
            except ValueError:
                pass

    def release(self):
        if not self._locked:
            raise RuntimeError("Lock is not acquired")
        self._wake_next()

    def _wake_next(self):
        while True:
            while self._urgent and self._urgent[0].done():
                self._urgent.popleft()
            while self._normal and self._normal[0].done():
                self._normal.popleft()
            if self._urgent and (self._burst < 8 or not self._normal):
                future = self._urgent.popleft()
                self._burst += 1
            elif self._normal:
                future = self._normal.popleft()
                self._burst = 0
            else:
                self._locked = False
                self._burst = 0
                return
            future.set_result(None)
            return

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *_):
        self.release()
