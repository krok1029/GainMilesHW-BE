from flask import Flask, Response, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        fields: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.fields = fields if fields is not None else {}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError) -> Response:
        response = jsonify(
            error={"code": error.code, "message": str(error), "fields": error.fields}
        )
        response.status_code = error.status
        return response

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException) -> Response:
        codes = {
            400: ("INVALID_JSON", "Request body must contain valid JSON."),
            404: ("NOT_FOUND", "Route not found."),
            405: ("METHOD_NOT_ALLOWED", "Method not allowed."),
            415: ("UNSUPPORTED_MEDIA_TYPE", "Content-Type must be application/json."),
        }
        code, message = codes.get(
            error.code or 500, (error.name.upper().replace(" ", "_"), error.name)
        )
        # Keep protocol headers such as Allow when replacing Werkzeug's HTML body.
        response = app.response_class(status=error.code, headers=error.get_headers())
        response.set_data(
            app.json.dumps({"error": {"code": code, "message": message, "fields": {}}})
        )
        response.content_type = "application/json"
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception) -> Response:
        app.logger.exception("Unexpected API error")
        return handle_api_error(
            ApiError(500, "INTERNAL_ERROR", "An unexpected error occurred.")
        )
