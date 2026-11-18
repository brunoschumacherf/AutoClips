from transcriptions.diarization import dominant_speaker


def test_assign_speaker_with_greatest_combined_overlap():
    turns = [(0, 2, "A"), (2, 5, "B"), (5, 7, "A")]
    assert dominant_speaker(0, 7, turns) == "A"
    assert dominant_speaker(2, 5, turns) == "B"
    assert dominant_speaker(7, 10, turns) is None
