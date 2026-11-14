from lucv11.reproduce import compare, flags, max_numeric_diff


def test_flags_are_the_keys_ending_in_pass():
    assert flags({"a_pass": True, "b": 1, "c_pass": False}) == {"a_pass": True, "c_pass": False}


def test_identical_analyses_reproduce_and_a_flipped_verdict_is_reported():
    a = {"H1_pass": True, "x": [0.1, 0.2], "t": {"k": 3.0}}
    assert compare(a, dict(a))["flags_equal"] and compare(a, dict(a))["max_numeric_diff"] == 0.0
    flipped = compare(a, {**a, "H1_pass": False})
    assert not flipped["flags_equal"] and flipped["differing_flags"] == {"H1_pass": (True, False)}


def test_no_flags_at_all_is_not_a_pass():
    assert compare({"x": 1}, {"x": 1})["flags_equal"] is False


def test_numeric_differences_and_structure_changes_are_measured():
    assert max_numeric_diff({"a": [1.0, 2.0]}, {"a": [1.0, 2.5]}) == 0.5
    assert max_numeric_diff({"a": 1}, {"b": 1}) == float("inf") and max_numeric_diff([1], [1, 2]) == float("inf")
    assert max_numeric_diff(True, False) == float("inf") and max_numeric_diff("a", "a") == 0.0
