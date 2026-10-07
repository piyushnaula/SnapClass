"""Face detection + embedding with OpenCV (YuNet detector, SFace recognizer).

YuNet finds faces and 5 landmarks (eyes, nose, mouth corners). SFace uses
those landmarks to align the face to 112×112 pixels and returns a 128-number
embedding. We scale every embedding to length 1, so the L2 distance between
two embeddings is between 0 (same) and 2 (opposite).
"""

from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np


@dataclass(frozen=True)
class DetectedFace:
    box: tuple[int, int, int, int]  # left, top, right, bottom (pixels)
    embedding: np.ndarray  # shape (128,), unit length
    quality: float  # 0..1, detector confidence × sharpness
    sharpness: float  # variance of the Laplacian of the aligned face (higher = sharper)


class FaceEncoder(Protocol):
    """Any face model must offer this. Swapping models is then a one-file change."""

    model_version: str

    def encode(self, image: np.ndarray, min_face_px: int) -> list[DetectedFace]: ...


def decode_image(data: bytes) -> np.ndarray | None:
    """Bytes (JPEG/PNG) → BGR image array, or None if the file is not a valid image."""
    array = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def sharpness(image: np.ndarray) -> float:
    """Variance of the Laplacian: a blurry image has few edges, so a low value."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def crop_face(image: np.ndarray, box: tuple[int, int, int, int], size: int = 160) -> bytes:
    """Cut the face out (with a small margin) and return it as JPEG bytes for the review UI."""
    left, top, right, bottom = box
    margin = int(0.2 * (right - left))
    height, width = image.shape[:2]
    left, top = max(0, left - margin), max(0, top - margin)
    right, bottom = min(width, right + margin), min(height, bottom + margin)
    face = cv2.resize(image[top:bottom, left:right], (size, size))
    ok, encoded = cv2.imencode(".jpg", face, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise ValueError("Could not encode face crop")
    return encoded.tobytes()


class OpenCVFaceEncoder:
    model_version = "opencv-yunet2023-sface2021"

    # Images bigger than this are scaled down before detection to keep it fast.
    MAX_SIDE = 2048

    def __init__(self, detector_path: str, recognizer_path: str, score_threshold: float = 0.7, blur_ok: float = 40.0):
        # The input size is a placeholder; we set the real size for every image.
        self.detector = cv2.FaceDetectorYN.create(detector_path, "", (320, 320), score_threshold, 0.3, 5000)
        self.recognizer = cv2.FaceRecognizerSF.create(recognizer_path, "")
        self.blur_ok = blur_ok

    def encode(self, image: np.ndarray, min_face_px: int = 24) -> list[DetectedFace]:
        """Find every face and embed it. Boxes are in the ORIGINAL image's pixels."""
        height, width = image.shape[:2]
        scale = min(1.0, self.MAX_SIDE / max(height, width))
        small = image if scale == 1.0 else cv2.resize(image, (int(width * scale), int(height * scale)))

        self.detector.setInputSize((small.shape[1], small.shape[0]))
        _, rows = self.detector.detect(small)
        if rows is None:
            return []

        faces = []
        for row in rows:
            # row = [x, y, w, h, 5 landmark points (10 numbers), confidence]
            x, y, w, h = (v / scale for v in row[:4])  # back to original pixels
            if min(w, h) < min_face_px:
                continue  # too small to recognise reliably
            aligned = self.recognizer.alignCrop(small, row)
            embedding = self.recognizer.feature(aligned).flatten().astype(np.float32)
            embedding /= np.linalg.norm(embedding)
            sharp = sharpness(aligned)
            confidence = float(row[14])
            quality = confidence * min(1.0, sharp / (2 * self.blur_ok))
            box = (int(x), int(y), int(x + w), int(y + h))
            faces.append(DetectedFace(box, embedding, round(quality, 3), sharp))
        return faces
