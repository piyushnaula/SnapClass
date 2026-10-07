"""Checks for uploaded files: size limit and real file type (magic bytes).

We never trust the file name or the Content-Type header sent by the browser.
Instead we look at the first bytes of the file, which tell us the real format.
"""

from fastapi import UploadFile

from snapclass.core.errors import AppError, bad_request


def _is_image(data: bytes) -> bool:
    is_jpeg = data[:3] == b"\xff\xd8\xff"
    is_png = data[:8] == b"\x89PNG\r\n\x1a\n"
    return is_jpeg or is_png


def _is_audio(data: bytes) -> bool:
    is_webm = data[:4] == b"\x1a\x45\xdf\xa3"  # webm / mkv (browser recordings)
    is_wav = data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    is_ogg = data[:4] == b"OggS"
    is_mp3 = data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")
    is_mp4 = data[4:8] == b"ftyp"  # m4a / mp4 (phone recordings)
    return is_webm or is_wav or is_ogg or is_mp3 or is_mp4


async def read_upload(file: UploadFile, kind: str, max_mb: int) -> bytes:
    """Read an uploaded file, enforce the size limit and check its real type.

    kind is "image" or "audio".
    """
    limit = max_mb * 1024 * 1024
    data = await file.read(limit + 1)  # read at most one byte past the limit
    if len(data) > limit:
        raise AppError(413, "FILE_TOO_LARGE", f"{file.filename} is larger than {max_mb} MB")
    if not data:
        raise bad_request(f"{file.filename} is empty", "EMPTY_FILE")

    valid = _is_image(data) if kind == "image" else _is_audio(data)
    if not valid:
        expected = "a JPEG or PNG image" if kind == "image" else "an audio file"
        raise bad_request(f"{file.filename} is not {expected}", "INVALID_FILE_TYPE")
    return data


def image_extension(data: bytes) -> str:
    return "png" if data[:4] == b"\x89PNG" else "jpg"
