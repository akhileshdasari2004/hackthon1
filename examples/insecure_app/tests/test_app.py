from src.app import run_user_code


def test_eval():
    assert run_user_code("1 + 1") == 2
