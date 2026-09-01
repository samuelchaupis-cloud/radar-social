import asyncio
import re
import time
from enum import StrEnum


def sanitizar_url_proxy(url: str) -> str:
    # Elimina usuario:password de URLs de proxies para evitar fugas en logs
    return re.sub(r"://[^:]+:[^@]+@", "://***:***@", url)


class CircuitBreakerOpenError(Exception):
    pass


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ProxyCircuitBreaker:
    def __init__(self, cooldown_seconds: float = 30.0) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.state = CircuitState.CLOSED
        self.last_failure_time: float = 0.0

    def record_exhaustion(self) -> None:
        self.state = CircuitState.OPEN
        self.last_failure_time = time.monotonic()

    def record_success(self) -> None:
        self.state = CircuitState.CLOSED

    def is_open(self) -> bool:
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time > self.cooldown_seconds:
                self.state = CircuitState.HALF_OPEN
                return False
            return True
        return False


class ProxyPool:
    def __init__(
        self,
        proxies: list[str],
        circuit_breaker: ProxyCircuitBreaker | None = None,
    ) -> None:
        self.circuit_breaker = circuit_breaker or ProxyCircuitBreaker()
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._all_proxies = set(proxies)
        self._penalized: set[str] = set()

        for p in proxies:
            self._queue.put_nowait(p)

    async def get_proxy(self) -> str:
        if self.circuit_breaker.is_open():
            raise CircuitBreakerOpenError("El Circuit Breaker de proxies esta ABIERTO")

        try:
            proxy = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            return proxy
        except TimeoutError as err:
            self.circuit_breaker.record_exhaustion()
            raise CircuitBreakerOpenError(
                "Todos los proxies del pool estan penalizados o agotados"
            ) from err

    async def penalizar_proxy(self, proxy: str) -> None:
        self._penalized.add(proxy)
        if len(self._penalized) >= len(self._all_proxies):
            self.circuit_breaker.record_exhaustion()

    async def devolver_proxy(self, proxy: str) -> None:
        if proxy in self._penalized:
            self._penalized.remove(proxy)
        self.circuit_breaker.record_success()
        await self._queue.put(proxy)
