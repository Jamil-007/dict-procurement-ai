"""
Run one review dimension and print what it produces.

No server, no database, no procurement record — just the analyzer. Use it
while writing a dimension, and before trusting one on a real procurement.

    # the built-in sample documents, against Procurement & Market
    python scripts/try_dimension.py

    # any other dimension
    python scripts/try_dimension.py --list
    python scripts/try_dimension.py -d document_quality

    # your own PDFs — repeat --doc once per file, "path=Document Type".
    # The type must be one of domain.DOC_TYPES; it decides which dimensions
    # read the file, so getting it wrong looks like a dimension ignoring it.
    python scripts/try_dimension.py \
        --doc "~/TOR.pdf=Terms of Reference (TOR)" \
        --doc "~/Market Study.pdf=Market Study" \
        --abc 2560000 --title "Supply of Rack Servers"

    # the full prompt, when a finding makes no sense and you need to see why
    python scripts/try_dimension.py --show-prompt

This calls a real model, so it costs a request and takes a minute. It needs
whichever key LLM_PROVIDER points at. TAVILY_API_KEY is optional — without it
Procurement & Market runs on the documents alone, which is the normal case.
"""

import argparse
import asyncio
import inspect
import sys
import time
from collections import Counter
from pathlib import Path

# The backend package is a directory up; imports below depend on this line.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from domain import DOC_TYPES
from review import ReviewContext, ReviewDocument, all_dimensions
from review.registry import get_dimension
from store.files import extract_text, read_document

SAMPLE = [
    (
        "Market Study.pdf",
        "Market Study",
        """[page 1] MARKET STUDY — Procurement of Rack Servers for the DICT Data
Center. The study canvassed three (3) suppliers in Metro Manila in January 2026.
[page 2] Indicative unit prices gathered: Supplier A PHP 512,000; Supplier B
PHP 498,500; Supplier C PHP 505,000. All prices are VAT-inclusive, ex-warehouse
Manila, exclusive of installation. No government price reference was consulted.
[page 3] Delivery lead time quoted by all three suppliers: 90 to 120 calendar
days from receipt of notice to proceed. The study does not address maintenance,
licensing or disposal costs over the service life of the equipment.""",
    ),
    (
        "Supplier Quotation A.pdf",
        "Supplier Quotation",
        """[page 1] QUOTATION — Supplier A. Item: Dell PowerEdge R760 rack server,
2x Intel Xeon Gold 6430, 256GB RAM. Unit price PHP 512,000 VAT-inclusive.
Validity 30 days. Delivery 90 calendar days. Warranty 3 years.""",
    ),
    (
        "TOR.pdf",
        "Terms of Reference (TOR)",
        """[page 3] 4. TECHNICAL SPECIFICATIONS. The server shall be a Dell PowerEdge
R760 or equivalent, fitted with 2x Intel Xeon Gold 6430 processors, 256GB DDR5
RAM expandable to 2TB, and the Dell iDRAC9 Enterprise management controller.
[page 4] 5. DELIVERY. All units shall be delivered, racked and commissioned
within forty-five (45) calendar days from receipt of the notice to proceed.
[page 5] 6. WARRANTY. Five (5) years on-site next-business-day support.
[page 6] 7. ELIGIBILITY. The bidder shall have completed at least three (3)
contracts for identical equipment within the last two (2) years.""",
    ),
    (
        "PPMP.pdf",
        "Project Procurement Management Plan (PPMP)",
        """[page 1] Quantity: five (5) units. Estimated budget: PHP 2,560,000.
Mode: Competitive Bidding. Source of funds: GAA 2026.""",
    ),
]


def load(argument: str) -> ReviewDocument:
    """Turn a 'path=Document Type' argument into a parsed document."""
    path_text, _, doc_type = argument.partition("=")
    if not doc_type:
        raise SystemExit(
            f"--doc needs a type: {argument!r} should be 'path=Document Type'"
        )
    if doc_type not in DOC_TYPES:
        raise SystemExit(
            f"Unknown document type {doc_type!r}.\nPick one of:\n  "
            + "\n  ".join(DOC_TYPES)
        )

    path = Path(path_text.strip()).expanduser()
    if not path.exists():
        raise SystemExit(f"No such file: {path}")

    text = extract_text(read_document(str(path)))
    if not text.strip():
        raise SystemExit(f"No readable text in {path.name} — is it a scanned image?")

    return ReviewDocument(
        name=path.name, doc_type=doc_type, pages=text.count("[page "), text=text
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-d", "--dimension", default="procurement_market")
    parser.add_argument("--doc", action="append", default=[], metavar="PATH=TYPE")
    parser.add_argument("--title", default="Supply and Delivery of Rack Servers")
    parser.add_argument("--abc", type=float, default=2_560_000.0)
    parser.add_argument("--mode", default="Competitive Bidding")
    parser.add_argument("--category", default="Goods")
    parser.add_argument("--show-prompt", action="store_true")
    parser.add_argument("--list", action="store_true", help="list dimension keys")
    args = parser.parse_args()

    if args.list:
        for entry in all_dimensions():
            print(f"{entry.key:22} {entry.owner or '—':8} {entry.label}")
        return 0

    try:
        spec = get_dimension(args.dimension)
    except KeyError:
        keys = ", ".join(d.key for d in all_dimensions())
        raise SystemExit(
            f"No dimension {args.dimension!r}. Try one of: {keys}"
        ) from None

    documents = (
        [load(item) for item in args.doc]
        if args.doc
        else [
            ReviewDocument(name=n, doc_type=t, pages=x.count("[page "), text=x)
            for n, t, x in SAMPLE
        ]
    )

    print(f"Dimension : {spec.label} ({spec.key})")
    print(f"Provider  : {settings.LLM_PROVIDER}")
    print(
        f"Search    : {'Tavily key set' if settings.TAVILY_API_KEY else 'no Tavily key — documents only'}"
    )
    print("Documents :")
    for document in documents:
        print(f"  {document.name}  [{document.doc_type}]  {len(document.text):,} chars")
    print()

    context = ReviewContext(
        procurement_ref="PROC-TRY-001",
        documents=documents,
        meta={
            "title": args.title,
            "abc": args.abc,
            "mode": args.mode,
            "category": args.category,
        },
    )

    if args.show_prompt:
        # Wrapping the dimension's own analyze is the only way to see the
        # prompt: a dimension builds it privately and never returns it.
        module = sys.modules[spec.run.__module__]
        original = module.analyze

        def show(prompt: str, dimension: str):
            print("=" * 72)
            print(prompt)
            print("=" * 72)
            print()
            return original(prompt, dimension)

        module.analyze = show

    started = time.monotonic()
    findings = spec.run(context)
    if inspect.isawaitable(findings):  # a dimension may be written async
        findings = asyncio.run(findings)
    elapsed = time.monotonic() - started

    print(f"=== {len(findings)} findings in {elapsed:.1f}s ===")
    print("severity  :", dict(Counter(f.severity for f in findings)))
    print("confidence:", dict(Counter(str(f.confidence) for f in findings)))
    print()

    for finding in findings:
        print(f"[{finding.severity.upper()}] {finding.title}")
        locator = f"p{finding.source.page}" if finding.source.page else "no page"
        print(
            f"  source      : {finding.source.doc} {locator} {finding.source.section}"
        )
        print(f"  confidence  : {finding.confidence}")
        if finding.policy_basis:
            print(f"  policy      : {finding.policy_basis}")
        print(f"  analysis    : {finding.analysis}")
        if finding.recommendation:
            print(f"  recommend   : {finding.recommendation}")
        if finding.quote:
            print(f"  quote       : “{finding.quote}”")
        for side in finding.comparison:
            print(f"  compared    : {side.doc} — {side.label}: “{side.quote}”")
        if finding.delta:
            print(f"  delta       : {finding.delta}")
        for source in finding.external_sources:
            print(f"  cited       : [tier {source.tier}] {source.url}")
        print()

    # The things most likely to be wrong, called out rather than left to spot.
    sourceless = [f for f in findings if not f.source.doc]
    if sourceless:
        print(f"WARNING: {len(sourceless)} finding(s) cite no document.")
    if not any(f.severity == "compliant" for f in findings):
        print(
            "NOTE: nothing was recorded as compliant — the BAC cannot see what passed."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
