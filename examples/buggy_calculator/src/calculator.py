"""Buggy calculator module with known issues."""


def divide(a, b):
    try:
        return a / b
    except Exception:
        return None


def safe_divide(a, b):
    return a / b


def add(a, b):
    pass
