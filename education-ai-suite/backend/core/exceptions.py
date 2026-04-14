import traceback
import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    error_trace = traceback.format_exc()

    print("\n" + "🔥" * 20)
    print(f"ERROR OCCURRED AT: {request.method} {request.url.path}")
    print(f"ERROR TYPE: {type(exc).__name__}")
    print(f"DETAIL: {str(exc)}")
    print("-" * 40)
    print(error_trace)
    print("🔥" * 20 + "\n")

    logger.error(f"Path: {request.url.path} | Error: {str(exc)}")

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "message": str(exc),
            "type": type(exc).__name__
        }
    )

def setup_exception_handlers(app):
    app.add_exception_handler(Exception, global_exception_handler)