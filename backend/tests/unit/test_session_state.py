import pytest

from snapclass.domain.session import InvalidTransition, can_change_media, check_transition, status_after_media_change

VALID = [
    ("CREATED", "UPLOADED"),
    ("UPLOADED", "PROCESSING"),
    ("UPLOADED", "CREATED"),  # every photo removed
    ("PROCESSING", "REVIEW"),
    ("PROCESSING", "FAILED"),
    ("FAILED", "PROCESSING"),
    ("FAILED", "UPLOADED"),  # photos changed after a failed check
    ("REVIEW", "FINALIZED"),
    ("REVIEW", "UPLOADED"),  # teacher adds/removes photos during review
]

INVALID = [
    ("CREATED", "PROCESSING"),  # must add photos first
    ("CREATED", "FINALIZED"),
    ("REVIEW", "PROCESSING"),  # changed photos go back to UPLOADED first
    ("FINALIZED", "REVIEW"),  # saved attendance is final
    ("FINALIZED", "UPLOADED"),
    ("FAILED", "REVIEW"),
    ("PROCESSING", "UPLOADED"),  # cannot change photos while they are being checked
]


@pytest.mark.parametrize("current,target", VALID)
def test_valid_transitions(current, target):
    check_transition(current, target)  # does not raise


@pytest.mark.parametrize("current,target", INVALID)
def test_invalid_transitions(current, target):
    with pytest.raises(InvalidTransition):
        check_transition(current, target)


def test_photos_can_change_until_saved_except_while_checking():
    for status in ("CREATED", "UPLOADED", "REVIEW", "FAILED"):
        assert can_change_media(status)
    assert not can_change_media("PROCESSING")
    assert not can_change_media("FINALIZED")


def test_status_after_media_change():
    assert status_after_media_change(True) == "UPLOADED"
    assert status_after_media_change(False) == "CREATED"
