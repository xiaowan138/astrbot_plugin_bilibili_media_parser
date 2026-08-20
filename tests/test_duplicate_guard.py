import asyncio
import unittest

from bilibili_parser.duplicate_guard import DuplicateGuard


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


class DuplicateGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_within_window_and_allows_boundary(self):
        clock = FakeClock()
        guard = DuplicateGuard(10, clock=clock)

        self.assertFalse(await guard.check_and_mark("group", "BV1xx411c7mD"))
        clock.value = 9.999
        self.assertTrue(await guard.check_and_mark("group", "BV1xx411c7mD"))
        clock.value = 10.0
        self.assertFalse(await guard.check_and_mark("group", "BV1xx411c7mD"))

    async def test_scopes_are_independent(self):
        guard = DuplicateGuard(10, clock=lambda: 1.0)
        self.assertFalse(await guard.check_and_mark("group-a", "BV1xx411c7mD"))
        self.assertFalse(await guard.check_and_mark("group-b", "BV1xx411c7mD"))

    async def test_concurrent_messages_have_one_winner(self):
        guard = DuplicateGuard(10, clock=lambda: 1.0)
        results = await asyncio.gather(
            *(guard.check_and_mark("group", "BV1xx411c7mD") for _ in range(20))
        )
        self.assertEqual(results.count(False), 1)
        self.assertEqual(results.count(True), 19)

    async def test_zero_window_disables_guard(self):
        guard = DuplicateGuard(0)
        self.assertFalse(await guard.check_and_mark("group", "video"))
        self.assertFalse(await guard.check_and_mark("group", "video"))

    async def test_failed_parse_can_release_reservation(self):
        guard = DuplicateGuard(10, clock=lambda: 1.0)
        self.assertFalse(await guard.check_and_mark("group", "video"))
        await guard.forget("group", "video")
        self.assertFalse(await guard.check_and_mark("group", "video"))

    async def test_unique_key_burst_is_capacity_bounded(self):
        guard = DuplicateGuard(10, clock=lambda: 1.0)
        for index in range(2055):
            self.assertFalse(
                await guard.check_and_mark("group", f"video-{index}")
            )
        self.assertLessEqual(len(guard._seen), 2048)


if __name__ == "__main__":
    unittest.main()
