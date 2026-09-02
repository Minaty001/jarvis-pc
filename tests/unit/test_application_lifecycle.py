import asyncio
import signal
import pytest
from jarvis.app.application import Application
from jarvis.app.lifecycle import setup_signal_handlers
from jarvis.app.health import check_health, HealthStatus


class DummyComponent:
    def __init__(self, name="dummy", fail_on_stop=False):
        self.name = name
        self.started = False
        self.stopped = False
        self.fail_on_stop = fail_on_stop

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True
        if self.fail_on_stop:
            raise RuntimeError(f"Component {self.name} failed to stop")

    async def health_check(self):
        return {"status": "ok", "name": self.name}


@pytest.mark.asyncio
async def test_application_lifecycle():
    dummy_scheduler = DummyComponent("scheduler")
    dummy_voice = DummyComponent("voice")
    dummy_api = DummyComponent("api")

    app = Application()
    app.scheduler = dummy_scheduler
    app.voice = dummy_voice
    app.api = dummy_api

    assert app.is_started is False

    await app.start()
    assert app.is_started is True
    assert dummy_scheduler.started is True
    assert dummy_voice.started is True
    assert dummy_api.started is True

    # Idempotent start call
    await app.start()
    assert app.is_started is True

    await app.stop()
    assert app.is_started is False
    assert dummy_scheduler.stopped is True
    assert dummy_voice.stopped is True
    assert dummy_api.stopped is True

    # Idempotent stop call
    await app.stop()
    assert app.is_started is False


@pytest.mark.asyncio
async def test_application_stop_handles_errors():
    good_component = DummyComponent("good")
    failing_component = DummyComponent("failing", fail_on_stop=True)

    app = Application()
    app.scheduler = failing_component
    app.voice = good_component
    await app.start()

    with pytest.raises(RuntimeError, match=r"1 component\(s\) failed to stop"):
        await app.stop()

    assert app.is_started is False
    assert failing_component.stopped is True
    assert good_component.stopped is True


@pytest.mark.asyncio
async def test_health_check():
    dummy = DummyComponent("scheduler")
    app = Application()
    app.scheduler = dummy

    health_before = await check_health(app)
    assert health_before.status == "healthy"
    assert health_before.started is False

    await app.start()
    health_after = await check_health(app)
    assert health_after.status == "healthy"
    assert health_after.started is True


def test_signal_handlers():
    dummy = DummyComponent("scheduler")
    app = Application()
    app.scheduler = dummy
    # Register signal handlers on current event loop
    loop = asyncio.get_event_loop()
    handlers = setup_signal_handlers(app, loop=loop)
    assert len(handlers) >= 2
