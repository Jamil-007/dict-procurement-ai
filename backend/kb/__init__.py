"""Legal knowledge base.

Findings must cite a real section of a real issuance. An unaided model will
invent plausible-looking section numbers, so citations here are *retrieved*
from an index built out of the actual PDFs, never generated.
"""

from kb.retriever import Authority, LegalRetriever, get_retriever

__all__ = ["Authority", "LegalRetriever", "get_retriever"]
