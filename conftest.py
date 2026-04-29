import sys
import os

# Ensure the project root is on sys.path so that `agent.*` imports resolve
# regardless of which directory pytest is invoked from.
sys.path.insert(0, os.path.dirname(__file__))
