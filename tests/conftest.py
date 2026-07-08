import os
import sys

# Allow tests to import the src/ layout without an install step.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
