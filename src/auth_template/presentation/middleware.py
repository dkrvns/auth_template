import json
import logging
import time
from uuid import uuid7

from starlette import status
from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger('auth_template.http')


class RequestBoundaryMiddleware:
    def __init__(self, app: ASGIApp, max_body_bytes: int = 16384) -> None:
        self._app = app
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self._app(scope, receive, send)
            return
        request_id = str(uuid7())
        started = time.monotonic()
        response_status = 500

        async def send_response(message: Message) -> None:
            nonlocal response_status
            if message['type'] == 'http.response.start':
                response_status = message['status']
                headers = MutableHeaders(scope=message)
                headers['X-Request-ID'] = request_id
                headers['Cache-Control'] = 'no-store'
                headers['X-Content-Type-Options'] = 'nosniff'
            await send(message)

        try:
            body = bytearray()
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                chunk = message.get('body', b'')
                if len(body) + len(chunk) > self._max_body_bytes:
                    await JSONResponse(
                        {'detail': 'Request body too large'},
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    )(scope, receive, send_response)
                    return
                body.extend(chunk)
                if not message.get('more_body', False):
                    break
            delivered = False

            async def receive_body() -> Message:
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {'type': 'http.request', 'body': bytes(body)}
                return await receive()

            await self._app(scope, receive_body, send_response)
        finally:
            logger.info(
                json.dumps(
                    {
                        'event': 'http_request',
                        'request_id': request_id,
                        'method': scope['method'],
                        'status': response_status,
                        'duration_ms': round((time.monotonic() - started) * 1000, 2),
                    }
                )
            )
