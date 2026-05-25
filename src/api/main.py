import asyncio
import contextlib
from contextlib import asynccontextmanager

from api.handlers import payments, users
from fastapi import Depends, FastAPI, Header, HTTPException
from loguru import logger

from config import settings
from services.google_sheets_export import export_all_configured_bots

GOOGLE_EXPORT_INTERVAL_SEC = 3600
GOOGLE_EXPORT_STARTUP_DELAY_SEC = 20


def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid X-API-KEY")


async def _google_sheets_export_loop() -> None:
    await asyncio.sleep(GOOGLE_EXPORT_STARTUP_DELAY_SEC)
    while True:
        try:
            await asyncio.to_thread(export_all_configured_bots)
        except FileNotFoundError as exc:
            logger.warning("Google Sheets export skipped: {}", exc)
        except Exception:
            logger.exception("Google Sheets export failed")
        await asyncio.sleep(GOOGLE_EXPORT_INTERVAL_SEC)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    export_task: asyncio.Task[None] | None = None
    if settings.google_exports_enabled:
        export_task = asyncio.create_task(_google_sheets_export_loop())
        logger.info(
            "Google Sheets export enabled (first run in {}s, then every {}s)",
            GOOGLE_EXPORT_STARTUP_DELAY_SEC,
            GOOGLE_EXPORT_INTERVAL_SEC,
        )
    yield
    if export_task is not None:
        export_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await export_task


app = FastAPI(lifespan=lifespan, dependencies=[Depends(verify_api_key)])

app.include_router(users.router)
app.include_router(payments.router)
