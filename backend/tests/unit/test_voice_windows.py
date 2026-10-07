import numpy as np

from snapclass.ml.voice import SAMPLE_RATE, make_windows, speech_runs

S = SAMPLE_RATE  # samples per second


def test_short_runs_are_dropped():
    assert make_windows([(0, int(0.5 * S))]) == []


def test_long_runs_are_split_into_max_windows():
    windows = make_windows([(0, int(6.5 * S))], min_s=1.0, max_s=3.0)
    assert windows == [(0, 3 * S), (3 * S, 6 * S)]  # the last 0.5 s piece is shorter than min_s
    windows = make_windows([(0, int(7.5 * S))], min_s=1.0, max_s=3.0)
    assert windows[-1] == (6 * S, int(7.5 * S))


def test_windows_never_cross_runs():
    windows = make_windows([(0, 2 * S), (3 * S, 5 * S)])
    assert windows == [(0, 2 * S), (3 * S, 5 * S)]


def test_silence_has_no_speech():
    assert speech_runs(np.zeros(3 * S, dtype=np.float32)) == []
