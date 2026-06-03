import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

SESSION_COOKIE = "session_token"
logger = logging.getLogger("session")


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        cookies = dict(request.cookies)
        token = cookies.get(SESSION_COOKIE)
        if token:
            request.state.session_token = token
        logger.info(
            "REQ %s %s cookies=%s has_token=%s",
            request.method,
            request.url.path,
            cookies,
            bool(token),
        )
        response = await call_next(request)
        set_cookies = response.headers.getlist("set-cookie")
        logger.info(
            "RES %s %s set-cookie=%s",
            request.method,
            request.url.path,
            set_cookies,
        )
        return response
