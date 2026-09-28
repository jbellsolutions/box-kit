import asyncio
import unittest

from gateway.lock import LaneBusy, lane


class SingleFlight(unittest.IsolatedAsyncioTestCase):
    async def test_lane_is_exclusive(self):
        """One Chromium, one job. A second claimant must be told, not queued forever."""
        async with lane(label="first"):
            with self.assertRaises(LaneBusy):
                async with lane(wait_seconds=0, label="second"):
                    self.fail("two jobs held the lane at once")

    async def test_lane_is_released_on_exit(self):
        async with lane(label="first"):
            pass
        async with lane(wait_seconds=0, label="second"):
            pass

    async def test_lane_is_released_when_the_job_raises(self):
        with self.assertRaises(ZeroDivisionError):
            async with lane(label="doomed"):
                1 / 0
        async with lane(wait_seconds=0, label="after"):
            pass

    async def test_busy_message_explains_the_constraint(self):
        async with lane(label="holder"):
            try:
                async with lane(wait_seconds=0, label="waiter"):
                    pass
            except LaneBusy as exc:
                self.assertIn("one browser at a time", str(exc))
                self.assertIn("fetch", str(exc))
            else:
                self.fail("expected LaneBusy")

    async def test_a_waiter_gets_the_lane_when_the_holder_finishes(self):
        order = []

        async def holder():
            async with lane(label="holder"):
                order.append("held")
                await asyncio.sleep(0.4)
            order.append("released")

        async def waiter():
            await asyncio.sleep(0.1)
            async with lane(wait_seconds=5, label="waiter"):
                order.append("waiter-ran")

        await asyncio.gather(holder(), waiter())
        self.assertEqual(order, ["held", "released", "waiter-ran"])


if __name__ == "__main__":
    unittest.main()
