"""App with security anti-patterns."""
import pickle

API_KEY = "sk-live-abc123secret"
password = "admin123"


def run_user_code(code):
    return eval(code)


def load_data(data):
    return pickle.loads(data)
