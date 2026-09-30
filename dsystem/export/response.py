from urllib.parse import quote

from fastapi import Response

TRUNCATED_HEADER = "X-Export-Truncated"
EXPOSED_HEADERS = ["Content-Disposition", TRUNCATED_HEADER]


def content_disposition(filename: str) -> str:
    fallback = filename.encode("ascii", "ignore").decode().replace('"', "").replace("\\", "").strip() or "export"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"


def attachment(content: bytes, filename: str, media_type: str, *, truncated: bool = False) -> Response:
    headers = {"Content-Disposition": content_disposition(filename)}
    if truncated:
        headers[TRUNCATED_HEADER] = "true"
    return Response(content=content, media_type=media_type, headers=headers)


def file_responses(media_type: str, description: str) -> dict:
    return {
        200: {
            "description": description,
            "content": {media_type: {"schema": {"type": "string", "format": "binary"}}},
            "headers": {
                "Content-Disposition": {
                    "description": "`attachment` with an ASCII `filename` and a UTF-8 `filename*`",
                    "schema": {"type": "string"},
                },
                TRUNCATED_HEADER: {
                    "description": "`true` when more rows matched than the export carries",
                    "schema": {"type": "string", "enum": ["true"]},
                },
            },
        }
    }
