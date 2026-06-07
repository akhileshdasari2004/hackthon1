"""Utility module with style issues."""
import os

import json


def process_data(data):
    try:
        return json.loads(data)
    except Exception:
        return {}


def unused_helper():
    return "never called"
