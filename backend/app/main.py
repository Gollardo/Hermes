from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app import APP_VERSION
from app.api.router import create_api_router
from app.api.validation import validation_error_response
from app.core.config import Settings, get_settings
from app.core.database import create_database_engine, create_session_factory
from app.core.static import mount_frontend


def create_lifespan(settings: Settings) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(settings)
        app.state.database_engine = engine
        app.state.session_factory = create_session_factory(engine)
        try:
            yield
        finally:
            engine.dispose()

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    application = FastAPI(
        title=resolved_settings.app_name,
        version=APP_VERSION,
        lifespan=create_lifespan(resolved_settings),
    )
    application.add_exception_handler(RequestValidationError, validation_error_response)
    application.state.settings = resolved_settings
    application.include_router(create_api_router(), prefix=resolved_settings.api_prefix)
    mount_frontend(application, resolved_settings.static_dir)
    return application


app = create_app()
