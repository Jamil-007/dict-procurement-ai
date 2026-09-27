"""
Makes `backend/` importable from the tests.

Backend modules import each other as top-level names — `from config import
settings`, `from review.schema import ...` — so the package root has to be on
sys.path. pytest prepends the directory holding the root conftest, which is
this one, so an empty file here is enough. Run pytest from `backend/`.
"""
