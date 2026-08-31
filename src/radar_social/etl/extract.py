import asyncio

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.errors import RequestsError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

SEMAPHORE = asyncio.Semaphore(10)


def on_retry_inject_proxy(retry_state):
    # En un entorno real, aquí se extrae y asigna un proxy fresco al state o variables de entorno.
    pass


@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(RequestsError),
    before_sleep=on_retry_inject_proxy,
)
async def extraer_html_resiliente(url: str) -> str:
    async with SEMAPHORE:
        # Se instancia un AsyncSession nuevo para no reusar el mismo proxy/sesión 
        # en caso de fallo y evitar fugas de sockets asíncronos.
        async with AsyncSession(impersonate="chrome110") as client:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            return response.text
