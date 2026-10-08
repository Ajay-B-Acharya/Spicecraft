"""Bound circuit request bodies before JSON decoding and schema validation."""
import asyncio

from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from starlette.responses import JSONResponse

from app.services.production import PipelineLimits


async def circuit_http_error(request, exc):
    if (request.url.path != '/circuits' and not request.url.path.startswith('/circuits/')) or isinstance(exc.detail, dict):
        return await http_exception_handler(request, exc)
    return JSONResponse({'detail': {
        'code': 'HTTP_ERROR', 'message': exc.detail, 'stage': 'input_validation', 'retryable': False,
    }}, status_code=exc.status_code, headers=exc.headers)


async def circuit_validation_error(request, exc):
    if request.url.path != '/circuits' and not request.url.path.startswith('/circuits/'):
        return await request_validation_exception_handler(request, exc)
    diagnostics = [dict(code=error['type'], message=error['msg'],
                        location=list(error['loc']), stage='input_validation')
                   for error in exc.errors()]
    return JSONResponse({'detail': {
        'code': 'INVALID_REQUEST', 'message': 'Invalid circuit request',
        'stage': 'input_validation', 'retryable': False, 'diagnostics': diagnostics,
    }}, status_code=422)


class CircuitRequestLimits:
    def __init__(self, app, limits=None):
        self.app = app
        self.limits = limits or PipelineLimits.from_environment()

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        if scope['type'] != 'http' or (path != '/circuits' and not path.startswith('/circuits/')) or scope.get('method') not in {'POST', 'PUT', 'PATCH'}:
            await self.app(scope, receive, send)
            return

        async def reject(code, message, status):
            await JSONResponse({'detail': {'code': code, 'stage': 'input_validation', 'message': message,
                                           'retryable': code == 'REQUEST_TIMEOUT'}}, status_code=status)(scope, receive, send)

        headers = dict(scope.get('headers', []))
        length = headers.get(b'content-length')
        if length is not None:
            try:
                size = int(length)
            except ValueError:
                await reject('INVALID_CONTENT_LENGTH', 'Invalid Content-Length header', 400)
                return
            if size < 0 or size > self.limits.max_input_bytes:
                await reject('RESOURCE_LIMIT', f'Circuit request exceeds {self.limits.max_input_bytes} bytes', 413)
                return
        buffer, size = bytearray(), 0
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.limits.request_body_seconds
        try:
            async with asyncio.timeout(self.limits.request_body_seconds):
                while True:
                    message = await receive()
                    if loop.time() > deadline:
                        raise TimeoutError
                    if message['type'] == 'http.disconnect':
                        return
                    body = message.get('body', b'')
                    size += len(body)
                    if size > self.limits.max_input_bytes:
                        await reject('RESOURCE_LIMIT', f'Circuit request exceeds {self.limits.max_input_bytes} bytes', 413)
                        return
                    buffer.extend(body)
                    if not message.get('more_body', False):
                        break
        except TimeoutError:
            await reject('REQUEST_TIMEOUT', 'Circuit request body exceeded its time budget', 408)
            return
        body = bytes(buffer)
        buffer.clear()
        try:
            text = body.decode('utf-8')
        except UnicodeDecodeError:
            await reject('INVALID_JSON_ENCODING', 'Circuit JSON must use UTF-8', 422)
            return
        # Bound nesting before the framework's recursive JSON decoder runs.
        depth, quoted, escaped = 0, False, False
        for character in text:
            if quoted:
                if escaped:
                    escaped = False
                elif character == '\\':
                    escaped = True
                elif character == '"':
                    quoted = False
            elif character == '"':
                quoted = True
            elif character in '[{':
                depth += 1
                if depth > self.limits.max_input_depth + 1:
                    await reject('RESOURCE_LIMIT', 'Circuit JSON exceeds the nesting limit', 413)
                    return
            elif character in ']}':
                depth -= 1
        consumed = False

        async def bounded_receive():
            nonlocal consumed
            if consumed:
                return await receive()
            consumed = True
            return {'type': 'http.request', 'body': body, 'more_body': False}

        await self.app(scope, bounded_receive, send)
