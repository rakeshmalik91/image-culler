import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run_all():
    """
    Discovers and executes all unit tests in the tests/ directory.
    """
    tests_dir = Path(__file__).resolve().parent
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(tests_dir), pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(not result.wasSuccessful())


if __name__ == "__main__":
    run_all()
