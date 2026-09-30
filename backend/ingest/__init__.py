"""Document ingestion layer.

Turns any uploaded file into markdown text, regardless of whether it has a
text layer. The public entry point is `load_document()`.
"""

from ingest.loaders import LoadedDocument, load_document

__all__ = ["LoadedDocument", "load_document"]
