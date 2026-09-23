import sys
import os

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "legal_case_management")
)

from legal_case_management.app import app