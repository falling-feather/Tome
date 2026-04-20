"""DailyQuota + RateLimiter 单元测试"""
from backend.app.services.resilience import DailyQuota, RateLimiter


class TestDailyQuota:
    def test_allows_under_limit(self):
        q = DailyQuota(limit=3)
        for _ in range(3):
            ok, _ = q.check(1)
            assert ok
            q.record(1)

    def test_blocks_over_limit(self):
        q = DailyQuota(limit=2)
        q.record(1)
        q.record(1)
        ok, msg = q.check(1)
        assert not ok
        assert "上限" in msg

    def test_separate_users(self):
        q = DailyQuota(limit=1)
        q.record(1)
        ok, _ = q.check(2)
        assert ok

    def test_zero_limit_means_unlimited(self):
        q = DailyQuota(limit=0)
        for _ in range(100):
            ok, _ = q.check(1)
            assert ok
            q.record(1)


class TestRateLimiter:
    def test_allows_within_window(self):
        rl = RateLimiter(per_user_limit=5, per_user_window=60.0, global_limit=100, global_window=60.0)
        for _ in range(5):
            ok, _ = rl.check(1)
            assert ok

    def test_blocks_over_user_limit(self):
        rl = RateLimiter(per_user_limit=2, per_user_window=60.0, global_limit=100, global_window=60.0)
        rl.check(1)
        rl.check(1)
        ok, msg = rl.check(1)
        assert not ok
        assert "频繁" in msg
