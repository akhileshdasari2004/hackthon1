from src.calculator import divide, safe_divide, add


def test_divide():
    assert divide(10, 2) == 5


def test_safe_divide():
    assert safe_divide(10, 2) == 5


def test_add():
    result = add(1, 2)
    assert result is None
