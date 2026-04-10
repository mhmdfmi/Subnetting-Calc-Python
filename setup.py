# setup.py minimal shim
# Keep this file only for legacy tooling that expects setup.py to exist.
# All package metadata should live in pyproject.toml.

from setuptools import setup

if __name__ == "__main__":
    # Intentionally empty: setuptools will read metadata from pyproject.toml
    setup()
