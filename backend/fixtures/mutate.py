"""Fixture generator: injects labelled defects into the clean packet.

Each mutation below takes the clean packet from `base.py`, breaks exactly one
thing, and records which rule (or which cross-document comparison) is
supposed to catch it. That label is the ground truth the tests measure
against, which is what makes "did we catch it" a measurable question rather
than a judgement call.

    python -m fixtures.mutate            # regenerate fixtures/cases/*.json
    python -m fixtures.mutate --list     # show the case inventory

One defect per case, deliberately. A case with five defects tells you the
engine found something; a case with one tells you which check is broken.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from fixtures.base import (
    CONTRACT_PACKET,
    FULL_PACKET,
    PAYMENT_PACKET,
    PLANNING_PACKET,
    clean_packet,
)

CASES_DIR = Path(__file__).parent / "cases"


@dataclass
class Case:
    """One fixture: a packet, a defect, and what must be reported for it."""

    id: str
    task: str
    description: str
    docs: List[str]
    # Rule ids from `rules/packs/*.yaml` that must fire on this packet.
    expect_rules: List[str] = field(default_factory=list)
    # Field paths the consistency engine must flag as disagreeing.
    expect_discrepancies: List[str] = field(default_factory=list)
    # Rule ids that must NOT fire -- used where a mutation is close to a
    # different defect and we want to prove the two are distinguished.
    forbid_rules: List[str] = field(default_factory=list)
    # None for the clean control cases.
    mutate: Optional[Callable[[Dict[str, Dict]], None]] = None
    # Highest severity tolerated. Clean packets must stay quiet.
    max_severity: Optional[str] = None

    def build(self) -> Dict:
        packet = clean_packet()
        if self.mutate is not None:
            self.mutate(packet)
        return {
            "id": self.id,
            "task": self.task,
            "description": self.description,
            "expect_rules": self.expect_rules,
            "expect_discrepancies": self.expect_discrepancies,
            "forbid_rules": self.forbid_rules,
            "max_severity": self.max_severity,
            "documents": [packet[key] for key in self.docs],
        }


# -- helpers ---------------------------------------------------------------


def _signatory(packet: Dict, doc: str, role_fragment: str) -> Dict:
    for entry in packet[doc]["signatories"]:
        if role_fragment.lower() in entry["role"].lower():
            return entry
    raise KeyError(f"{doc} has no signatory matching '{role_fragment}'")


def _drop_signatory(packet: Dict, doc: str, role_fragment: str) -> None:
    packet[doc]["signatories"] = [
        entry
        for entry in packet[doc]["signatories"]
        if role_fragment.lower() not in entry["role"].lower()
    ]


# -- T1: payment and disbursement voucher ----------------------------------

CASES: List[Case] = [
    Case(
        id="clean_payment_packet",
        task="T1",
        description="A complete, correct payment packet. Nothing should be flagged.",
        docs=PAYMENT_PACKET,
        max_severity="low",
    ),
    Case(
        id="dv_missing_payee",
        task="T1",
        description="The voucher's payee field was left blank.",
        docs=["dv"],
        expect_rules=["dv.required_fields"],
        mutate=lambda p: p["dv"].update(payee=None),
    ),
    Case(
        id="dv_words_figures_mismatch",
        task="T1",
        description=(
            "The amount in words reads six million five hundred thousand while "
            "the figures read 6,555,000.00. Under IRR 61.2.3 the words control, "
            "so this changes what the voucher directs to be paid."
        ),
        docs=["dv"],
        expect_rules=["dv.amount_in_words_matches_figures"],
        mutate=lambda p: p["dv"].update(
            amount_in_words="SIX MILLION FIVE HUNDRED THOUSAND PESOS ONLY"
        ),
    ),
    Case(
        id="dv_net_arithmetic_error",
        task="T1",
        description=(
            "Net amount due is overstated by 70,000.00 -- the retention was "
            "deducted on paper but not taken off the net."
        ),
        docs=["dv"],
        expect_rules=["dv.net_amount_reconciles"],
        mutate=lambda p: p["dv"]["amounts"].update(net=6625000.00),
    ),
    Case(
        id="dv_unsigned_certification",
        task="T1",
        description=(
            "The Chief Accountant's certification box carries a printed name "
            "but no signature."
        ),
        docs=["dv"],
        expect_rules=["dv.required_signatories"],
        mutate=lambda p: _signatory(p, "dv", "Certified").update(signed=False),
    ),
    Case(
        id="dv_approval_before_certification",
        task="T1",
        description=(
            "The approving officer signed on 17 November, two days before the "
            "Accountant certified the funds available."
        ),
        docs=["dv"],
        expect_rules=["dv.signatory_dates_in_order"],
        mutate=lambda p: _signatory(p, "dv", "Approved").update(date="November 17, 2024"),
    ),
    Case(
        id="dv_missing_attachments",
        task="T1",
        description=(
            "The voucher references only the invoice and the delivery receipt. "
            "The IAR, PAR, warranty and tax receipt required by COA Circular "
            "2023-004 section 9.3.1 are not attached."
        ),
        docs=["dv"],
        expect_rules=["dv.supporting_documents_goods"],
        mutate=lambda p: p["dv"].update(
            attachments_referenced=["Sales Invoice", "Delivery Receipt"]
        ),
    ),
    Case(
        id="dv_paid_before_acceptance",
        task="T1",
        description=(
            "The voucher is dated 10 November but acceptance was not until "
            "14 November -- payment was prepared for goods not yet accepted."
        ),
        docs=["dv"],
        expect_rules=["dv.payment_date_sequence"],
        mutate=lambda p: p["dv"]["dates"].update(document="November 10, 2024"),
    ),
    Case(
        id="invoice_extension_error",
        task="T1",
        description=(
            "Line 2 of the invoice is extended as 1,995,000.00 where 60 x "
            "32,500.00 is 1,950,000.00 -- a 45,000.00 overcharge."
        ),
        docs=["invoice"],
        expect_rules=["payment.invoice_arithmetic"],
        mutate=lambda p: p["invoice"]["items"][1].update(amount=1995000.00),
    ),
    Case(
        id="invoice_total_mismatch",
        task="T1",
        description=(
            "The invoice total is stated as 7,100,000.00 but the line items "
            "sum to 7,000,000.00."
        ),
        docs=["invoice"],
        expect_rules=["payment.invoice_total_matches_items"],
        mutate=lambda p: p["invoice"]["amounts"].update(total=7100000.00),
    ),
    Case(
        id="dr_unacknowledged",
        task="T1",
        description=(
            "The delivery receipt has no 'Received by' signature -- there is no "
            "evidence the agency ever took the goods."
        ),
        docs=["delivery_receipt"],
        expect_rules=["payment.delivery_receipt_acknowledged"],
        mutate=lambda p: _drop_signatory(p, "delivery_receipt", "Received"),
    ),
    Case(
        id="iar_unsigned_inspector",
        task="T1",
        description="The property inspector's block on the IAR is unsigned.",
        docs=["iar"],
        expect_rules=["payment.iar_inspected_and_accepted"],
        mutate=lambda p: _signatory(p, "iar", "Inspected").update(signed=False),
    ),
    Case(
        id="iar_acceptance_before_inspection",
        task="T1",
        description=(
            "The IAR records acceptance on 10 November and inspection on "
            "12 November: the goods were accepted before they were inspected."
        ),
        docs=["iar"],
        expect_rules=["payment.iar_date_sequence"],
        mutate=lambda p: p["iar"]["dates"].update(acceptance="November 10, 2024"),
    ),
    Case(
        id="par_missing_serials",
        task="T1",
        description=(
            "No serial numbers were recorded on the PAR, so the property on "
            "the books cannot be traced to the units delivered."
        ),
        docs=["par"],
        expect_rules=["payment.par_serial_numbers"],
        mutate=lambda p: [item.update(serial_numbers=[]) for item in p["par"]["items"]],
    ),
    Case(
        id="par_no_custodian",
        task="T1",
        description="The PAR names no accountable officer.",
        docs=["par"],
        expect_rules=["payment.par_accountable_officer", "complete.par_core"],
        mutate=lambda p: p["par"].update(recipient=None),
    ),

    # -- T2: RA 12009 compliance -------------------------------------------

    Case(
        id="clean_planning_packet",
        task="T2",
        description="A complete, correct planning packet. Nothing should be flagged.",
        docs=PLANNING_PACKET,
        max_severity="low",
    ),
    Case(
        id="obsolete_mode_of_procurement",
        task="T2",
        description=(
            "The PR states 'Shopping', a mode carried over from RA 9184. "
            "RA 12009 section 26 does not include it."
        ),
        docs=["pr"],
        expect_rules=["ra12009.recognised_mode_of_procurement"],
        mutate=lambda p: p["pr"].update(mode_of_procurement="Shopping"),
    ),
    Case(
        id="brand_name_specification",
        task="T2",
        description=(
            "The TOR specifies a Motorola transceiver by name, which restricts "
            "competition to one manufacturer."
        ),
        docs=["tor"],
        expect_rules=["ra12009.no_brand_name_specification"],
        mutate=lambda p: p["tor"]["items"][0].update(
            description="Motorola VHF Base Radio Transceiver, 50W, with power supply"
        ),
    ),
    Case(
        id="tor_missing_delivery_period",
        task="T2",
        description=(
            "The TOR states no delivery period, so there is no basis for "
            "computing liquidated damages."
        ),
        docs=["tor"],
        expect_rules=["ra12009.delivery_period_stated", "complete.tor_core"],
        mutate=lambda p: p["tor"].update(delivery_period=None),
    ),
    Case(
        id="bidding_docs_no_eligibility",
        task="T2",
        description=(
            "The bidding documents publish no eligibility requirements, so no "
            "bidder can lawfully be declared ineligible."
        ),
        docs=["bidding_docs"],
        expect_rules=["ra12009.eligibility_requirements_stated"],
        mutate=lambda p: p["bidding_docs"].update(eligibility_requirements=[]),
    ),
    Case(
        id="dcb_total_mismatch",
        task="T2",
        description=(
            "The cost breakdown totals 7,000,000.00 in its line items but "
            "states 6,800,000.00 as the total."
        ),
        docs=["dcb"],
        expect_rules=["ra12009.cost_total_matches_items"],
        mutate=lambda p: p["dcb"]["amounts"].update(total=6800000.00),
    ),
    Case(
        id="pr_unquantified_items",
        task="T2",
        description=(
            "Two requirement lines on the PR carry no quantity or unit, so "
            "bidders cannot price them consistently."
        ),
        docs=["pr"],
        expect_rules=["ra12009.items_quantified"],
        mutate=lambda p: [
            item.update(qty=None, unit=None) for item in p["pr"]["items"][:2]
        ],
    ),
    Case(
        id="pr_no_funds_certification",
        task="T2",
        description=(
            "The PR carries no certification of availability of funds; "
            "procurement was started without one."
        ),
        docs=["pr"],
        expect_rules=["ra12009.pr_funds_certified"],
        mutate=lambda p: _drop_signatory(p, "pr", "Certified"),
    ),

    # -- T3: completeness --------------------------------------------------

    Case(
        id="clean_full_packet",
        task="T3",
        description=(
            "The entire fourteen-document transaction, clean. This is the "
            "false-positive control for all three rulepacks at once."
        ),
        docs=FULL_PACKET,
        max_severity="low",
    ),
    Case(
        id="undated_and_unnumbered",
        task="T3",
        description=(
            "The contract carries neither a reference number nor a date, so it "
            "cannot be tied to any other document in the packet."
        ),
        docs=["contract"],
        expect_rules=["complete.document_identified", "complete.document_dated"],
        mutate=lambda p: p["contract"].update(
            doc_number=None,
            dates={"contract_signed": None, "document": None},
        ),
    ),
    Case(
        id="unclassified_document",
        task="T3",
        description=(
            "A file the classifier could not recognise. It must be surfaced "
            "rather than silently passing with no checks applied."
        ),
        docs=["invoice"],
        expect_rules=["complete.document_classified"],
        mutate=lambda p: p["invoice"].update(doc_type="other", doc_type_confidence=0.2),
    ),
    Case(
        id="market_study_single_source",
        task="T3",
        description=(
            "The market study cites one supplier. A single quotation does not "
            "establish that the ABC is reasonable."
        ),
        docs=["market_study"],
        expect_rules=["complete.market_study_sources"],
        mutate=lambda p: p["market_study"].update(items=p["market_study"]["items"][:1]),
    ),
    Case(
        id="contract_no_schedule_of_requirements",
        task="T3",
        description=(
            "The contract enumerates nothing, so there is no schedule of "
            "requirements to check any delivery against."
        ),
        docs=["contract"],
        expect_rules=["complete.contract_items"],
        mutate=lambda p: p["contract"].update(items=[]),
    ),
    # -- T4: contract-to-payment consistency -------------------------------

    Case(
        id="clean_contract_to_payment",
        task="T4",
        description="Contract and payment packet agree on every compared field.",
        docs=CONTRACT_PACKET + PAYMENT_PACKET,
        max_severity="low",
    ),
    Case(
        id="delivered_quantity_short_of_contract",
        task="T4",
        description=(
            "The contract covers 25 base transceivers; only 20 were delivered, "
            "inspected and paid for. For goods this requires an Amendment to "
            "Order under IRR 71.1.1, not a variation order."
        ),
        docs=CONTRACT_PACKET + PAYMENT_PACKET,
        expect_discrepancies=["items[].qty"],
        mutate=lambda p: [
            p[doc]["items"][0].update(qty=20.0, amount=2900000.00)
            for doc in ("delivery_receipt", "iar", "par", "invoice")
        ],
    ),
    Case(
        id="payment_exceeds_contract_amount",
        task="T4",
        description=(
            "The voucher's gross is 7,350,000.00 against a contract amount of "
            "7,000,000.00 -- a 350,000.00 payment with no contractual basis."
        ),
        docs=CONTRACT_PACKET + PAYMENT_PACKET,
        expect_discrepancies=["amounts.contract_amount"],
        mutate=lambda p: p["dv"]["amounts"].update(
            gross=7350000.00, contract_amount=7350000.00, net=6905000.00
        ),
    ),
    Case(
        id="contract_number_mismatch_on_voucher",
        task="T4",
        description=(
            "The voucher cites contract DICT-GECS-2024-007; the contract is "
            "DICT-GECS-2024-001. The payment cannot be tied to its obligation."
        ),
        docs=CONTRACT_PACKET + PAYMENT_PACKET,
        expect_discrepancies=["contract_no"],
        mutate=lambda p: p["dv"].update(contract_no="DICT-GECS-2024-007"),
    ),
    Case(
        id="delivery_after_contractual_due_date",
        task="T4",
        description=(
            "Delivery on 20 December against a contractual due date of "
            "15 December: five days of liquidated damages that no document "
            "in the packet accounts for."
        ),
        docs=CONTRACT_PACKET + PAYMENT_PACKET,
        expect_discrepancies=["dates.delivery"],
        mutate=lambda p: [
            p[doc]["dates"].update(delivery="December 20, 2024")
            for doc in ("delivery_receipt", "iar", "dv")
        ],
    ),

    Case(
        id="personnel_substituted_without_approval",
        task="T4",
        description=(
            "The contract names Engr. Cielo M. Bautista as RF Systems "
            "Engineer; the inspection report records someone else in the "
            "role. The bid was evaluated on the named team, so the "
            "substitution needed approval before the work was done."
        ),
        docs=CONTRACT_PACKET + PAYMENT_PACKET,
        expect_discrepancies=["personnel"],
        mutate=lambda p: p["iar"].update(
            personnel=[
                "Engr. Ramon T. Ilagan (Project Manager)",
                "Engr. Feliza O. Mendrez (RF Systems Engineer)",
                "Mr. Dante P. Rivera (Installation Supervisor)",
            ]
        ),
    ),
    Case(
        id="delivered_to_address_outside_the_contract",
        task="T4",
        description=(
            "The contract specifies the DICT Central Office warehouse in "
            "Diliman; the delivery receipt records delivery to the Region "
            "IV-A office in Calamba. The goods are not where the contract "
            "put them and the agency has no record of custody."
        ),
        docs=CONTRACT_PACKET + PAYMENT_PACKET,
        expect_discrepancies=["delivery_place"],
        mutate=lambda p: p["delivery_receipt"].update(
            delivery_place="DICT Regional Office IV-A, National Highway, Calamba, Laguna"
        ),
    ),

    # -- T5: delivery and acceptance cross-check ---------------------------

    Case(
        id="clean_delivery_acceptance",
        task="T5",
        description="DR, IAR, PAR and warranty agree on items, serials and dates.",
        docs=["delivery_receipt", "iar", "par", "warranty"],
        max_severity="low",
    ),
    Case(
        id="serial_numbers_differ_dr_vs_par",
        task="T5",
        description=(
            "The serials on the PAR do not appear on the delivery receipt: the "
            "units booked as property are not the units recorded as delivered."
        ),
        docs=["delivery_receipt", "iar", "par", "warranty"],
        expect_discrepancies=["items[].serial_numbers"],
        mutate=lambda p: p["par"]["items"][0].update(
            serial_numbers=["NBT-VHF-24501", "NBT-VHF-24502", "NBT-VHF-24503"]
        ),
    ),
    Case(
        id="description_differs_dr_vs_iar",
        task="T5",
        description=(
            "The IAR describes a 25W transceiver where the delivery receipt "
            "and the contract specify 50W -- a different item was accepted."
        ),
        docs=["delivery_receipt", "iar", "par", "warranty"],
        expect_discrepancies=["items[].description"],
        mutate=lambda p: p["iar"]["items"][0].update(
            description="VHF Base Radio Transceiver, 25W, with power supply"
        ),
    ),
    Case(
        id="quantity_differs_dr_vs_iar",
        task="T5",
        description=(
            "60 handhelds were delivered but only 55 inspected and accepted; "
            "five units are unaccounted for."
        ),
        docs=["delivery_receipt", "iar", "par", "warranty"],
        expect_discrepancies=["items[].qty"],
        mutate=lambda p: p["iar"]["items"][1].update(qty=55.0),
    ),
    Case(
        id="acceptance_predates_delivery_across_documents",
        task="T5",
        description=(
            "The IAR records acceptance on 5 November; the delivery receipt is "
            "dated 8 November. Goods were accepted three days before arrival."
        ),
        docs=["delivery_receipt", "iar", "par", "warranty"],
        expect_discrepancies=["dates.acceptance"],
        mutate=lambda p: p["iar"]["dates"].update(acceptance="November 5, 2024"),
    ),
    Case(
        id="receiving_officer_differs_dr_vs_iar",
        task="T5",
        description=(
            "The delivery receipt is signed for by L. Bermudez; the "
            "acceptance report records a different officer receiving the "
            "same consignment. One of the two documents does not describe "
            "the handover that happened."
        ),
        docs=["delivery_receipt", "iar", "par", "warranty"],
        expect_discrepancies=["recipient"],
        mutate=lambda p: p["iar"].update(recipient="Navarro, Fidel C."),
    ),
    Case(
        id="warranty_covers_different_contract",
        task="T5",
        description=(
            "The warranty certificate cites a different contract number, so it "
            "does not cover the delivered equipment."
        ),
        docs=["delivery_receipt", "iar", "par", "warranty"],
        expect_discrepancies=["contract_no"],
        mutate=lambda p: p["warranty"].update(contract_no="DICT-GECS-2023-018"),
    ),

    # -- T6: planning document alignment -----------------------------------

    Case(
        id="clean_planning_alignment",
        task="T6",
        description="Market study, TOR, DCB and bidding documents all agree.",
        docs=PLANNING_PACKET,
        max_severity="low",
    ),
    Case(
        id="quantity_differs_tor_vs_dcb",
        task="T6",
        description=(
            "The TOR asks for 25 base transceivers; the cost breakdown prices "
            "30. The ABC was computed against a quantity nobody asked for."
        ),
        docs=PLANNING_PACKET,
        expect_discrepancies=["items[].qty"],
        mutate=lambda p: p["dcb"]["items"][0].update(qty=30.0, amount=4350000.00),
    ),
    Case(
        id="specification_differs_tor_vs_bidding_docs",
        task="T6",
        description=(
            "The bidding documents publish an IP54 handheld where the TOR "
            "requires IP67 -- bidders are being asked for the wrong item."
        ),
        docs=PLANNING_PACKET,
        expect_discrepancies=["items[].description"],
        mutate=lambda p: p["bidding_docs"]["items"][1].update(
            description="Portable VHF Handheld Radio, IP54, with spare battery"
        ),
    ),
    Case(
        id="abc_differs_dcb_vs_bidding_docs",
        task="T6",
        description=(
            "The ABC in the bidding documents is 7,500,000.00; the approved "
            "cost breakdown supports 7,200,000.00."
        ),
        docs=PLANNING_PACKET,
        expect_discrepancies=["amounts.abc"],
        mutate=lambda p: p["bidding_docs"]["amounts"].update(abc=7500000.00),
    ),
    Case(
        id="timeline_differs_tor_vs_bidding_docs",
        task="T6",
        description=(
            "The TOR allows ninety calendar days for delivery; the bidding "
            "documents say sixty. Bidders will price against the shorter one "
            "and the contract will be enforced against the longer."
        ),
        docs=PLANNING_PACKET,
        expect_discrepancies=["delivery_period"],
        mutate=lambda p: p["bidding_docs"].update(
            delivery_period="Sixty (60) calendar days from receipt of the Notice to Proceed"
        ),
    ),
    Case(
        id="deliverables_dropped_from_bidding_docs",
        task="T6",
        description=(
            "Operator training and as-built documentation are in the TOR but "
            "absent from the bidding documents, so they were never procured."
        ),
        docs=PLANNING_PACKET,
        expect_discrepancies=["deliverables"],
        mutate=lambda p: p["bidding_docs"].update(
            deliverables=["Delivery of all equipment to the DICT Central Office warehouse"]
        ),
    ),
]


def build_all(out_dir: Path = CASES_DIR) -> List[Path]:
    """Write every case to disk as JSON."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for case in CASES:
        path = out_dir / f"{case.id}.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(case.build(), fh, indent=2, ensure_ascii=False)
        written.append(path)
    return written


def _main() -> None:
    parser = argparse.ArgumentParser(description="Generate the fixture suite.")
    parser.add_argument("--out", type=Path, default=CASES_DIR)
    parser.add_argument("--list", action="store_true", help="List cases and exit.")
    args = parser.parse_args()

    if args.list:
        by_task: Dict[str, List[Case]] = {}
        for case in CASES:
            by_task.setdefault(case.task, []).append(case)
        for task in sorted(by_task):
            print(f"\n{task}")
            for case in by_task[task]:
                labels = case.expect_rules + case.expect_discrepancies
                target = ", ".join(labels) if labels else "(clean control)"
                print(f"  {case.id:44s} -> {target}")
        print(f"\n{len(CASES)} cases.")
        return

    written = build_all(args.out)
    print(f"Wrote {len(written)} fixture case(s) to {args.out}")


if __name__ == "__main__":
    _main()
