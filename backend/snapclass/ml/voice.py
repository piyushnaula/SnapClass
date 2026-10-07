"""Voice pipeline (spec A.9.5): decode → voice activity detection → windows → embeddings.

1. ffmpeg converts any recording (webm, ogg, mp3, m4a, wav) to 16 kHz mono.
2. webrtcvad marks each 30 ms frame as speech or silence.
3. Continuous speech runs become windows (see docs/design for why we do not
   merge across silences).
4. Resemblyzer turns each window into a 256-number embedding of unit length.
"""

import subprocess

import numpy as np
import webrtcvad

VOICE_MODEL_VERSION = "resemblyzer-0.1.4"
SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 480 samples per frame


def decode_audio(data: bytes, max_seconds: int = 60) -> np.ndarray:
    """Any audio file bytes → float32 array in [-1, 1], 16 kHz mono, at most max_seconds long."""
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",  # read the file from stdin
        "-t",
        str(max_seconds),  # cut long recordings
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-f",
        "s16le",
        "pipe:1",  # raw 16-bit samples to stdout
    ]
    result = subprocess.run(command, input=data, capture_output=True, timeout=60, check=False)
    if result.returncode != 0:
        raise ValueError(f"Could not decode audio: {result.stderr.decode(errors='ignore')[:200]}")
    samples = np.frombuffer(result.stdout, dtype=np.int16)
    return samples.astype(np.float32) / 32768.0


def speech_runs(wav: np.ndarray, aggressiveness: int = 2, max_gap_ms: int = 300) -> list[tuple[int, int]]:
    """Return (start_sample, end_sample) for each continuous run of speech.

    Gaps of silence shorter than max_gap_ms are treated as part of the run
    (people pause briefly inside one sentence).
    """
    vad = webrtcvad.Vad(aggressiveness)  # 0 = least strict, 3 = most strict
    pcm = (np.clip(wav, -1, 1) * 32767).astype(np.int16).tobytes()
    frame_bytes = FRAME_SAMPLES * 2  # 2 bytes per 16-bit sample
    n_frames = len(pcm) // frame_bytes
    is_speech = [vad.is_speech(pcm[i * frame_bytes : (i + 1) * frame_bytes], SAMPLE_RATE) for i in range(n_frames)]

    max_gap_frames = max_gap_ms // FRAME_MS
    runs: list[tuple[int, int]] = []
    start = None
    last_speech = -1
    for i, speech in enumerate(is_speech):
        if speech:
            if start is None:
                start = i
            last_speech = i
        elif start is not None and i - last_speech > max_gap_frames:
            runs.append((start, last_speech + 1))
            start = None
    if start is not None:
        runs.append((start, last_speech + 1))
    return [(s * FRAME_SAMPLES, e * FRAME_SAMPLES) for s, e in runs]


def speech_seconds(wav: np.ndarray) -> float:
    return sum(end - start for start, end in speech_runs(wav)) / SAMPLE_RATE


def make_windows(runs: list[tuple[int, int]], min_s: float = 1.0, max_s: float = 3.0) -> list[tuple[int, int]]:
    """Turn speech runs into windows: drop runs shorter than min_s, split runs longer than max_s."""
    min_len, max_len = int(min_s * SAMPLE_RATE), int(max_s * SAMPLE_RATE)
    windows = []
    for start, end in runs:
        position = start
        while end - position >= min_len:
            window_end = min(position + max_len, end)
            windows.append((position, window_end))
            position = window_end
    return windows


class VoiceEmbedder:
    def __init__(self) -> None:
        # Imported here because torch is slow to import; only the worker needs it.
        from resemblyzer import VoiceEncoder

        self.encoder = VoiceEncoder("cpu", verbose=False)
        self.model_version = VOICE_MODEL_VERSION

        # Warm-up: librosa compiles its mel-spectrogram code (numba JIT) the first
        # time it runs, which takes ~18 s. Doing it here, while the worker starts,
        # means no teacher ever waits for it. Measured: 18 s first call, 0.002 s after.
        self.encoder.embed_utterance(np.zeros(SAMPLE_RATE, dtype=np.float32))

    def embed(self, wav: np.ndarray) -> np.ndarray:
        """One embedding for a whole clip (used for enrollment)."""
        from resemblyzer import preprocess_wav

        # preprocess_wav normalises loudness and removes long silences.
        cleaned = preprocess_wav(wav, source_sr=SAMPLE_RATE)
        return self._unit(self.encoder.embed_utterance(cleaned))

    def embed_windows(self, wav: np.ndarray) -> list[np.ndarray]:
        """One embedding per speech window (used for classroom recordings)."""
        windows = make_windows(speech_runs(wav))
        return [self._unit(self.encoder.embed_utterance(wav[start:end])) for start, end in windows]

    @staticmethod
    def _unit(vector: np.ndarray) -> np.ndarray:
        vector = np.asarray(vector, dtype=np.float32)
        return vector / np.linalg.norm(vector)
