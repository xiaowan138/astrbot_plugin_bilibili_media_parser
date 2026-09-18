import unittest

from bilibili_parser.live_monitor import (
    MAX_PER_UMO,
    MAX_TOTAL,
    MAX_UMOS_PER_ROOM,
    LiveSubscriptionStore,
    should_notify_live_end,
    should_notify_live_start,
)


class LiveSubscriptionStoreTests(unittest.TestCase):
    def test_add_and_remove_subscription(self):
        store = LiveSubscriptionStore()
        changed, message = store.add(6, "qq:group1")
        self.assertTrue(changed)
        self.assertEqual(message, "ok")
        self.assertEqual(store.rooms(), [6])
        self.assertEqual(store.umos_for(6), ["qq:group1"])
        self.assertEqual(len(store), 1)

        changed, message = store.remove(6, "qq:group1")
        self.assertTrue(changed)
        self.assertEqual(len(store), 0)
        self.assertEqual(store.rooms(), [])

    def test_duplicate_add_is_rejected(self):
        store = LiveSubscriptionStore()
        store.add(6, "qq:group1")
        changed, message = store.add(6, "qq:group1")
        self.assertFalse(changed)
        self.assertIn("已订阅", message)

    def test_remove_missing_subscription_is_rejected(self):
        store = LiveSubscriptionStore()
        changed, message = store.remove(6, "qq:group1")
        self.assertFalse(changed)
        self.assertIn("没有订阅", message)

    def test_same_room_can_be_subscribed_by_multiple_conversations(self):
        store = LiveSubscriptionStore()
        store.add(6, "qq:group1")
        store.add(6, "qq:group2")
        self.assertEqual(store.umos_for(6), ["qq:group1", "qq:group2"])
        self.assertEqual(store.rooms(), [6])

    def test_per_conversation_limit(self):
        store = LiveSubscriptionStore()
        for room in range(1, MAX_PER_UMO + 1):
            self.assertTrue(store.add(room, "qq:group1")[0])
        changed, message = store.add(MAX_PER_UMO + 1, "qq:group1")
        self.assertFalse(changed)
        self.assertIn(str(MAX_PER_UMO), message)

    def test_per_room_limit(self):
        store = LiveSubscriptionStore()
        for index in range(MAX_UMOS_PER_ROOM):
            self.assertTrue(store.add(6, f"qq:group{index}")[0])
        changed, message = store.add(6, "qq:overflow")
        self.assertFalse(changed)
        self.assertIn("上限", message)

    def test_total_limit(self):
        store = LiveSubscriptionStore()
        added = 0
        room = 1000
        while added < MAX_TOTAL:
            for _ in range(MAX_UMOS_PER_ROOM):
                if added >= MAX_TOTAL:
                    break
                self.assertTrue(store.add(room, f"qq:group{added}")[0])
                added += 1
            room += 1
        changed, message = store.add(room, "qq:newgroup")
        self.assertFalse(changed)
        self.assertIn("上限", message)

    def test_remove_umo_clears_all_its_subscriptions(self):
        store = LiveSubscriptionStore()
        store.add(1, "qq:group1")
        store.add(2, "qq:group1")
        store.add(1, "qq:group2")
        removed = store.remove_umo("qq:group1")
        self.assertEqual(removed, 2)
        self.assertEqual(store.umos_for(1), ["qq:group2"])
        self.assertEqual(store.rooms(), [1])

    def test_json_roundtrip(self):
        store = LiveSubscriptionStore()
        store.add(6, "qq:group1")
        store.add(6, "qq:group2")
        store.add(9, "qq:group1")
        restored = LiveSubscriptionStore.from_json(store.to_json())
        self.assertEqual(restored.items(), store.items())
        self.assertEqual(len(restored), 3)

    def test_from_json_tolerates_garbage(self):
        for raw in (None, "", "not json", "[]", "[\"bad\"]", "[\"x@y\"]", "[\"6@qq:ok\"]"):
            store = LiveSubscriptionStore.from_json(raw)
            if raw == "[\"6@qq:ok\"]":
                self.assertEqual(store.items(), [(6, "qq:ok")])
            else:
                self.assertEqual(len(store), 0)


class ShouldNotifyLiveStartTests(unittest.TestCase):
    def test_notifies_on_idle_to_live_transition(self):
        self.assertTrue(should_notify_live_start(0, 1))

    def test_notifies_on_round_robin_to_live_transition(self):
        self.assertTrue(should_notify_live_start(2, 1))

    def test_no_notification_on_first_observation(self):
        # 重启后第一次轮询不推送，避免对已在播的直播间刷屏。
        self.assertFalse(should_notify_live_start(None, 1))

    def test_no_notification_when_still_live(self):
        self.assertFalse(should_notify_live_start(1, 1))

    def test_no_notification_when_not_live(self):
        self.assertFalse(should_notify_live_start(0, 0))
        self.assertFalse(should_notify_live_start(1, 0))


class ShouldNotifyLiveEndTests(unittest.TestCase):
    def test_notifies_on_live_to_idle_transition(self):
        self.assertTrue(should_notify_live_end(1, 0))

    def test_notifies_on_live_to_round_robin_transition(self):
        self.assertTrue(should_notify_live_end(1, 2))

    def test_no_notification_on_first_observation(self):
        # 重启后第一次轮询不推送，避免对未在播的直播间误报下播。
        self.assertFalse(should_notify_live_end(None, 0))
        self.assertFalse(should_notify_live_end(None, 1))

    def test_no_notification_when_still_live(self):
        self.assertFalse(should_notify_live_end(1, 1))

    def test_no_notification_when_already_idle(self):
        self.assertFalse(should_notify_live_end(0, 0))
        self.assertFalse(should_notify_live_end(2, 0))


if __name__ == "__main__":
    unittest.main()
