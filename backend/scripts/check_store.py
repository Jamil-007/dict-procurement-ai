"""
Exercise the whole Store contract against whatever backend is configured.

    # against the emulator (no credentials, no GCP resources needed)
    gcloud emulators firestore start --host-port=127.0.0.1:8098
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8098 STORE_BACKEND=firestore \
    GOOGLE_CLOUD_PROJECT=demo-local python scripts/check_store.py

    # against the real database, once it exists
    STORE_BACKEND=firestore GOOGLE_CLOUD_PROJECT=ai-innov-474401 \
    FIRESTORE_PREFIX=smoketest_ python scripts/check_store.py

Writes under a throwaway prefix and deletes everything it created, so it is
safe to point at a real database. Exits non-zero on the first failure.
"""

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from domain import ProcurementCreate, ProcurementDocument, ProcurementPatch  # noqa: E402
from review.schema import ComparedText, Comment, Source, StoredFinding  # noqa: E402

PASSED = 0


def check(label: str, got, want) -> None:
    global PASSED
    if got != want:
        print(f"  FAIL  {label}\n        got:  {got!r}\n        want: {want!r}")
        sys.exit(1)
    PASSED += 1
    print(f"  ok    {label}")


def main() -> None:
    emulator = os.environ.get("FIRESTORE_EMULATOR_HOST")
    print(f"backend : {os.environ.get('STORE_BACKEND', 'memory')}")
    print(f"project : {os.environ.get('GOOGLE_CLOUD_PROJECT', '(default)')}")
    print(f"emulator: {emulator or 'no — talking to real Firestore'}")

    # Isolate this run so it cannot collide with real data.
    if not os.environ.get("FIRESTORE_PREFIX"):
        os.environ["FIRESTORE_PREFIX"] = f"check_{uuid.uuid4().hex[:8]}_"
    prefix = os.environ["FIRESTORE_PREFIX"]
    print(f"prefix  : {prefix}\n")

    from store import get_store

    store = get_store()
    created: list[str] = []

    try:
        print("procurements")
        first = store.create_procurement(
            ProcurementCreate(title="Supply of Laptops", abc=1_500_000, category="ICT")
        )
        created.append(first.ref)
        check("create returns a ref", first.ref.startswith("PROC-"), True)
        check("create persists the title", first.title, "Supply of Laptops")

        fetched = store.get_procurement(first.ref)
        check("get round-trips", fetched.title if fetched else None, "Supply of Laptops")
        check("get on a missing ref", store.get_procurement("PROC-9999-999"), None)
        check("abc survives the round trip", fetched.abc if fetched else None, 1_500_000)

        second = store.create_procurement(ProcurementCreate(title="Network Switches"))
        created.append(second.ref)
        check("refs are sequential", second.ref != first.ref, True)

        listed = store.list_procurements()
        check("list returns both", len(listed), 2)
        check("list is newest first", listed[0].ref, second.ref)

        patched = store.patch_procurement(
            first.ref, ProcurementPatch(mode="Direct Contracting")
        )
        check("patch applies", patched.mode if patched else None, "Direct Contracting")
        check(
            "patch leaves other fields alone",
            patched.title if patched else None,
            "Supply of Laptops",
        )
        check(
            "patch on a missing ref",
            store.patch_procurement("PROC-9999-999", ProcurementPatch(mode="x")),
            None,
        )

        print("\ndocuments")
        doc = ProcurementDocument(
            id="d1", name="TOR.pdf", doc_type="TOR", pages=12,
            gcs_path="gs://proc-ai-staging-files/procurements/x/TOR.pdf",
        )
        with_doc = store.add_documents(first.ref, [doc])
        check("add_documents attaches", len(with_doc.documents) if with_doc else 0, 1)
        check(
            "document fields survive",
            with_doc.documents[0].doc_type if with_doc else None,
            "TOR",
        )
        reread = store.get_procurement(first.ref)
        check("documents are persisted", len(reread.documents) if reread else 0, 1)

        removed = store.remove_document(first.ref, "d1")
        check("remove_document detaches", len(removed.documents) if removed else -1, 0)

        print("\nfindings")
        findings = [
            StoredFinding(
                id="F-001", procurement_ref=first.ref, dimension="document_quality",
                severity="critical", title="Unmeasurable requirement",
                analysis="a", recommendation="r",
                source=Source(doc="TOR.pdf", page=4, section="Section 4 — Specifications"),
                policy_basis="RA 12009 §?",
                # Nested model lists are the thing most likely to break on the
                # way through Firestore, so put one in deliberately.
                comparison=[
                    ComparedText(doc="TOR.pdf", page=4, label="Quantity", quote="120 units"),
                    ComparedText(doc="PR.pdf", page=1, label="Quantity", quote="150 units"),
                ],
                delta="Differs by 30 units",
            ),
            StoredFinding(
                id="F-002", procurement_ref=first.ref, dimension="compliance",
                severity="medium", title="Missing annex", analysis="a",
                recommendation="r", source=Source(doc="PR.pdf"),
            ),
        ]
        store.replace_findings(first.ref, findings)
        check("list_findings returns both", len(store.list_findings(first.ref)), 2)
        check("findings are scoped by ref", len(store.list_findings(second.ref)), 0)

        one = store.get_finding(first.ref, "F-001")
        check("get_finding round-trips", one.title if one else None, "Unmeasurable requirement")
        check("nested source survives", one.source.page if one else None, 4)
        check("nested comparison list survives", len(one.comparison) if one else 0, 2)
        check(
            "comparison quote survives",
            one.comparison[1].quote if one else None,
            "150 units",
        )
        check("an unset optional stays None", (one.source.page, one.decision)[1] if one else "x", None)
        check("get_finding on a missing id", store.get_finding(first.ref, "nope"), None)

        one.decision = "accepted"
        one.decided_by = "BAC Admin"
        store.save_finding(one)
        again = store.get_finding(first.ref, "F-001")
        check("save_finding persists a decision", again.decision if again else None, "accepted")

        commented = store.add_comment(
            first.ref,
            "F-002",
            Comment(
                text="Check with the end user",
                author="BAC Admin",
                at="2026-09-25T10:00:00Z",
            ),
        )
        check("add_comment appends", len(commented.comments) if commented else 0, 1)
        check(
            "comment text survives",
            commented.comments[0].text if commented else None,
            "Check with the end user",
        )

        store.replace_findings(first.ref, [findings[0]])
        check("replace_findings clears the old set", len(store.list_findings(first.ref)), 1)

        print("\nknowledge hub")
        # MemoryStore seeds on construction and writes nothing here; Firestore
        # writes the entries. Either way the Hub must end up populated.
        store.seed_knowledge()
        check("seed is idempotent", store.seed_knowledge(), 0)
        all_entries = store.list_knowledge()
        check("the Knowledge Hub is populated", len(all_entries) > 0, True)
        sample = all_entries[0]
        check(
            "filter by category",
            all(e.category == sample.category
                for e in store.list_knowledge(category=sample.category)),
            True,
        )
        check(
            "get_knowledge round-trips",
            (store.get_knowledge(sample.id) or sample).title,
            sample.title,
        )
        check("get_knowledge on a missing id", store.get_knowledge("nope"), None)

        print("\ndeletion")
        check("delete removes the record", store.delete_procurement(first.ref), True)
        check("deleted record is gone", store.get_procurement(first.ref), None)
        check("its findings went too", len(store.list_findings(first.ref)), 0)
        check("delete is idempotent", store.delete_procurement(first.ref), False)
        created.remove(first.ref)

    finally:
        for ref in created:
            try:
                store.delete_procurement(ref)
            except Exception as exc:  # noqa: BLE001
                print(f"  warning: could not clean up {ref}: {exc}")
        if os.environ.get("STORE_BACKEND") == "firestore":
            _drop(prefix, "knowledge", "counters")

    print(f"\n{PASSED} checks passed against "
          f"{os.environ.get('STORE_BACKEND', 'memory')}.")


def _drop(prefix: str, *collections: str) -> None:
    """
    Collections the Store contract has no delete method for. Clearing them
    keeps the run self-contained, so it is safe to point at a real database.
    """
    try:
        from google.cloud import firestore

        db = firestore.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT") or None)
        batch = db.batch()
        for name in collections:
            for doc in db.collection(f"{prefix}{name}").stream():
                batch.delete(doc.reference)
        batch.commit()
    except Exception as exc:  # noqa: BLE001
        print(f"  warning: could not clean up {', '.join(collections)}: {exc}")


if __name__ == "__main__":
    main()
