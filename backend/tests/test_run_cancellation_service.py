import asyncio
import unittest

from services.run_cancellation_service import RunCancellationService


class RunCancellationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_stops_registered_task_and_unregisters(self):
        service = RunCancellationService()
        started = asyncio.Event()

        async def run():
            await service.register("run-12345")
            started.set()
            try:
                await asyncio.Future()
            finally:
                await service.unregister("run-12345")

        task = asyncio.create_task(run())
        await started.wait()
        result = await service.cancel("run-12345")
        self.assertTrue(result.cancelled)
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(await service.is_active("run-12345"))

    async def test_unknown_run_is_safe_noop(self):
        result = await RunCancellationService().cancel("missing-run")
        self.assertFalse(result.cancelled)


if __name__ == "__main__":
    unittest.main()
