"""Interactive ordering must never overlap requests or orphan a cancelled handoff."""

import asyncio
import pytest
from custom_components.lg_rs232_ip.command_queue import (
    PriorityLock,
    interactive_command,
)


async def queued(lock, label, order):
    async with lock:
        order.append(label)
        await asyncio.sleep(0)


async def test_actions_pass_queued_polling_but_keep_their_order():
    lock, order = PriorityLock(), []
    await lock.acquire()
    readers = [asyncio.create_task(queued(lock, f"read{i}", order)) for i in range(3)]
    await asyncio.sleep(0)
    action = interactive_command(queued)
    writers = [asyncio.create_task(action(lock, f"write{i}", order)) for i in range(3)]
    await asyncio.sleep(0)
    assert not order  # The already-running holder is not preempted.
    lock.release()
    await asyncio.gather(*readers, *writers)
    assert order == ["write0", "write1", "write2", "read0", "read1", "read2"]
    assert not lock.locked()


async def test_background_gets_a_turn_under_a_continuous_action_burst():
    lock, order = PriorityLock(), []
    await lock.acquire()
    reader = asyncio.create_task(queued(lock, "read", order))
    writers = [
        asyncio.create_task(interactive_command(queued)(lock, f"write{i}", order))
        for i in range(20)
    ]
    await asyncio.sleep(0)
    lock.release()
    await asyncio.gather(reader, *writers)
    assert order.index("read") == 8
    assert [x for x in order if x != "read"] == [f"write{i}" for i in range(20)]


@pytest.mark.parametrize("handoff", [False, True])
async def test_cancelled_waiter_does_not_lose_reserved_lock(handoff):
    lock, order = PriorityLock(), []
    await lock.acquire()
    cancelled = asyncio.create_task(
        interactive_command(queued)(lock, "cancelled", order)
    )
    follower = asyncio.create_task(queued(lock, "follower", order))
    await asyncio.sleep(0)
    if handoff:
        lock.release()  # Grant, then cancel before the new owner resumes.
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    if not handoff:
        lock.release()
    await asyncio.wait_for(follower, 1)
    assert order == ["follower"] and not lock.locked()


async def test_cancellation_inside_action_releases_current_lock():
    lock = PriorityLock()
    started = asyncio.Event()

    @interactive_command
    async def action():
        async with lock:
            started.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(action())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with asyncio.timeout(1):
        async with lock:
            pass


async def test_child_refresh_does_not_inherit_action_priority():
    lock, order = PriorityLock(), []
    await lock.acquire()
    ordinary = asyncio.create_task(queued(lock, "ordinary", order))
    await asyncio.sleep(0)

    @interactive_command
    async def spawn():
        child = asyncio.create_task(queued(lock, "child_refresh", order))
        await queued(lock, "action", order)
        return child

    task = asyncio.create_task(spawn())
    await asyncio.sleep(0)
    lock.release()
    child = await task
    await asyncio.gather(ordinary, child)
    assert order == ["action", "ordinary", "child_refresh"]


async def test_priority_is_reset_after_exception_and_nested_action():
    lock, order = PriorityLock(), []

    @interactive_command
    async def nested():
        raise ValueError("rejected")

    @interactive_command
    async def action():
        with pytest.raises(ValueError):
            await nested()
        await queued(lock, "action", order)

    await lock.acquire()
    plain = asyncio.create_task(queued(lock, "normal", order))
    urgent = asyncio.create_task(action())
    await asyncio.sleep(0)
    lock.release()
    await asyncio.gather(plain, urgent)
    assert order == ["action", "normal"]
    with pytest.raises(RuntimeError):
        lock.release()


async def test_mutex_under_mixed_burst():
    lock = PriorityLock()
    current = 0

    async def worker():
        nonlocal current
        for _ in range(3):
            async with lock:
                current += 1
                assert current == 1
                await asyncio.sleep(0)
                current -= 1

    await asyncio.gather(
        *(interactive_command(worker)() if i % 2 else worker() for i in range(40))
    )
    assert current == 0 and not lock.locked()
