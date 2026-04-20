"""
稳定性加固模块 (M6)

- CircuitBreaker: 断路器（失败计数 → 熔断 → 半开 → 恢复）
- RetryPolicy: 重试策略（指数退避）
- RateLimiter: 请求限流（滑动窗口）
- HealthMetrics: 健康指标收集
"""
import time
import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any

logger = logging.getLogger("inkless")


# ---------------------------------------------------------------------------
# 断路器
# ---------------------------------------------------------------------------
class CircuitBreaker:
    """
    三态断路器: CLOSED → OPEN → HALF_OPEN → CLOSED
    - CLOSED: 正常通行，失败次数累加
    - OPEN: 熔断，直接拒绝请求
    - HALF_OPEN: 允许少量请求试探恢复
    """

    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self.state = self.STATE_CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.half_open_count = 0

        # 统计
        self.total_calls = 0
        self.total_failures = 0
        self.total_rejections = 0

    def can_execute(self) -> bool:
        """检查是否允许执行请求"""
        self.total_calls += 1

        if self.state == self.STATE_CLOSED:
            return True

        if self.state == self.STATE_OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = self.STATE_HALF_OPEN
                self.half_open_count = 0
                logger.info(f"断路器[{self.name}]: OPEN → HALF_OPEN")
                return True
            self.total_rejections += 1
            return False

        if self.state == self.STATE_HALF_OPEN:
            if self.half_open_count < self.half_open_max:
                self.half_open_count += 1
                return True
            self.total_rejections += 1
            return False

        return True

    def record_success(self):
        """记录成功"""
        if self.state == self.STATE_HALF_OPEN:
            self.state = self.STATE_CLOSED
            self.failure_count = 0
            logger.info(f"断路器[{self.name}]: HALF_OPEN → CLOSED (恢复)")

    def record_failure(self):
        """记录失败"""
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = time.time()

        if self.state == self.STATE_HALF_OPEN:
            self.state = self.STATE_OPEN
            logger.warning(f"断路器[{self.name}]: HALF_OPEN → OPEN (试探失败)")
        elif self.failure_count >= self.failure_threshold:
            self.state = self.STATE_OPEN
            logger.warning(f"断路器[{self.name}]: CLOSED → OPEN (失败{self.failure_count}次)")

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_rejections": self.total_rejections,
        }


# ---------------------------------------------------------------------------
# 重试策略
# ---------------------------------------------------------------------------
class RetryPolicy:
    """指数退避重试"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        backoff_factor: float = 2.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    async def execute(self, func: Callable[..., Awaitable], *args, **kwargs) -> Any:
        """带重试执行异步函数"""
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (self.backoff_factor ** attempt),
                        self.max_delay,
                    )
                    logger.warning(
                        f"重试 {attempt + 1}/{self.max_retries}: {e}, 等待{delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
        raise last_error


# ---------------------------------------------------------------------------
# 请求限流 (滑动窗口)
# ---------------------------------------------------------------------------
class RateLimiter:
    """
    滑动窗口限流器。
    per_user: 按用户ID限流
    global_limit: 全局限流
    """

    def __init__(
        self,
        per_user_limit: int = 10,
        per_user_window: float = 60.0,
        global_limit: int = 100,
        global_window: float = 60.0,
    ):
        self.per_user_limit = per_user_limit
        self.per_user_window = per_user_window
        self.global_limit = global_limit
        self.global_window = global_window

        self._user_requests: dict[int, list[float]] = defaultdict(list)
        self._global_requests: list[float] = []

        # 统计
        self.total_allowed = 0
        self.total_rejected = 0

    def check(self, user_id: int) -> tuple[bool, str]:
        """
        检查是否允许请求。
        返回 (allowed, reason)
        """
        now = time.time()

        # 清理过期记录
        self._cleanup(now)

        # 全局限流检查
        if len(self._global_requests) >= self.global_limit:
            self.total_rejected += 1
            return False, "服务器繁忙，请稍后重试"

        # 用户限流检查
        user_reqs = self._user_requests[user_id]
        if len(user_reqs) >= self.per_user_limit:
            self.total_rejected += 1
            remaining = user_reqs[0] + self.per_user_window - now
            return False, f"操作过于频繁，请{int(remaining)}秒后重试"

        # 允许
        self._global_requests.append(now)
        user_reqs.append(now)
        self.total_allowed += 1
        return True, ""

    def _cleanup(self, now: float):
        """清理过期记录"""
        cutoff_global = now - self.global_window
        self._global_requests = [t for t in self._global_requests if t > cutoff_global]

        cutoff_user = now - self.per_user_window
        for uid in list(self._user_requests.keys()):
            self._user_requests[uid] = [t for t in self._user_requests[uid] if t > cutoff_user]
            if not self._user_requests[uid]:
                del self._user_requests[uid]

    def get_stats(self) -> dict:
        return {
            "total_allowed": self.total_allowed,
            "total_rejected": self.total_rejected,
            "active_users": len(self._user_requests),
            "current_global": len(self._global_requests),
        }


# ---------------------------------------------------------------------------
# 健康指标
# ---------------------------------------------------------------------------
class HealthMetrics:
    """简单的健康指标收集器"""

    def __init__(self):
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._timings: dict[str, list[float]] = defaultdict(list)
        self._start_time = time.time()

    def inc(self, name: str, value: int = 1):
        """计数器递增"""
        self._counters[name] += value

    def set_gauge(self, name: str, value: float):
        """设置瞬时值"""
        self._gauges[name] = value

    def record_timing(self, name: str, duration_ms: float):
        """记录一次耗时"""
        timings = self._timings[name]
        timings.append(duration_ms)
        # 只保留最近1000条
        if len(timings) > 1000:
            self._timings[name] = timings[-1000:]

    def get_report(self) -> dict:
        """获取健康报告"""
        report = {
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "timings": {},
        }

        for name, values in self._timings.items():
            if values:
                sorted_vals = sorted(values)
                n = len(sorted_vals)
                report["timings"][name] = {
                    "count": n,
                    "avg_ms": round(sum(sorted_vals) / n, 1),
                    "p50_ms": round(sorted_vals[n // 2], 1),
                    "p95_ms": round(sorted_vals[int(n * 0.95)], 1) if n >= 20 else None,
                    "p99_ms": round(sorted_vals[int(n * 0.99)], 1) if n >= 100 else None,
                    "max_ms": round(sorted_vals[-1], 1),
                }

        return report


# ---------------------------------------------------------------------------
# 每日配额
# ---------------------------------------------------------------------------
class DailyQuota:
    """按用户 ID 统计每日动作次数，跨天自动重置。"""

    def __init__(self, limit: int = 200):
        self.limit = limit
        self._counts: dict[int, int] = {}
        self._date: str = ""  # YYYY-MM-DD

    def _maybe_reset(self):
        import datetime as _dt
        today = _dt.date.today().isoformat()
        if today != self._date:
            self._counts.clear()
            self._date = today

    def check(self, user_id: int) -> tuple[bool, str]:
        if self.limit <= 0:
            return True, ""
        self._maybe_reset()
        used = self._counts.get(user_id, 0)
        if used >= self.limit:
            return False, f"今日操作已达上限（{self.limit}次），请明日再来"
        return True, ""

    def record(self, user_id: int):
        self._maybe_reset()
        self._counts[user_id] = self._counts.get(user_id, 0) + 1

    def get_stats(self) -> dict:
        self._maybe_reset()
        return {
            "limit": self.limit,
            "active_users": len(self._counts),
        }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------
# LLM 调用断路器
llm_circuit_breaker = CircuitBreaker(
    name="llm_primary",
    failure_threshold=5,
    recovery_timeout=30.0,
)

llm_fallback_circuit_breaker = CircuitBreaker(
    name="llm_fallback",
    failure_threshold=3,
    recovery_timeout=60.0,
)

# 重试策略
llm_retry_policy = RetryPolicy(max_retries=2, base_delay=1.0, max_delay=8.0)

# 请求限流
game_rate_limiter = RateLimiter(
    per_user_limit=15,      # 每用户每分钟15次操作
    per_user_window=60.0,
    global_limit=200,       # 全局每分钟200次
    global_window=60.0,
)

# 健康指标
health_metrics = HealthMetrics()

# 每日配额 (启动时从 config 读取)
def _init_daily_quota() -> DailyQuota:
    try:
        from backend.app.config import settings
        return DailyQuota(limit=settings.DAILY_ACTION_LIMIT)
    except Exception:
        return DailyQuota(limit=200)

daily_quota = _init_daily_quota()
