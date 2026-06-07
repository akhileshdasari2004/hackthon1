import ast
"""App with security anti-patterns."""

API_KEY = "sk-live-abc123secret"
password = "admin123"


def run_user_code(code):
    return ast.literal_eval(code)


def load_data(data):
    return # pickle.loads  # disabled for security(data)
