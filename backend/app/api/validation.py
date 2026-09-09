"""Safe, language-neutral validation metadata at the HTTP boundary."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def validation_error_response(request: Request, error: Exception) -> JSONResponse:
    """Retain 422 detail-list shape without echoing passwords or financial input."""
    assert isinstance(error, RequestValidationError)
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": item["loc"], "type": item["type"], "msg": "Invalid request value"}
                for item in error.errors()
            ]
        },
    )
