from src.utils import process_data


def test_process_valid_json():
    assert process_data('{"key": "value"}') == {"key": "value"}


def test_process_invalid_json():
    assert process_data("not json") == {}
