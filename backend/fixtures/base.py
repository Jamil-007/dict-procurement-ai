"""A clean, internally consistent procurement packet.

This is the control case. Every document below agrees with every other one:
the quantities in the contract match the delivery receipt, the arithmetic
reconciles, the dates run in order and every signature block is signed. A
clean packet must produce no high-severity findings -- that assertion is as
important as catching the defects, because a checker that flags everything
is as useless as one that flags nothing.

The shape and vocabulary follow the real DICT GECS procurement in `docs/`,
but the figures, names and reference numbers here are invented. No real
supplier or officer is named.
"""

from __future__ import annotations

import copy
from typing import Dict, List

PROJECT = (
    "Supply, Delivery and Installation of Government Emergency "
    "Communications System (GECS) Equipment"
)
ENTITY = "Department of Information and Communications Technology"
SUPPLIER = "Northbridge Telecom Solutions, Inc."
CONTRACT_NO = "DICT-GECS-2024-001"
PR_NO = "PR-2024-0142"
PO_NO = "PO-2024-0089"
ORS_NO = "ORS-2024-101-0356"
DV_NO = "DV-2024-11-0412"
INVOICE_NO = "SI-20418"

# The three line items, carried identically through every document in the
# packet. The consistency engine's whole job is noticing when they stop
# agreeing, so they are defined once here.
ITEMS: List[Dict] = [
    {
        "line_no": "1",
        "description": "VHF Base Radio Transceiver, 50W, with power supply",
        "qty": 25.0,
        "unit": "unit",
        "unit_price": 145000.00,
        "amount": 3625000.00,
        "serial_numbers": ["NBT-VHF-24001", "NBT-VHF-24002", "NBT-VHF-24003"],
        "page": 1,
    },
    {
        "line_no": "2",
        "description": "Portable VHF Handheld Radio, IP67, with spare battery",
        "qty": 60.0,
        "unit": "unit",
        "unit_price": 32500.00,
        "amount": 1950000.00,
        "serial_numbers": ["NBT-HH-24101", "NBT-HH-24102"],
        "page": 1,
    },
    {
        "line_no": "3",
        "description": "Repeater Station with Antenna System and Mast",
        "qty": 5.0,
        "unit": "set",
        "unit_price": 285000.00,
        "amount": 1425000.00,
        "serial_numbers": ["NBT-RPT-24201"],
        "page": 2,
    },
]

CONTRACT_TOTAL = 7000000.00  # 3,625,000 + 1,950,000 + 1,425,000
ABC = 7200000.00
WITHHOLDING_TAX = 375000.00
RETENTION = 70000.00
NET_DUE = 6555000.00  # 7,000,000 - 375,000 - 70,000
NET_IN_WORDS = "SIX MILLION FIVE HUNDRED FIFTY FIVE THOUSAND PESOS ONLY"

DELIVERY_PERIOD = "Ninety (90) calendar days from receipt of the Notice to Proceed"
WARRANTY_PERIOD = "One (1) year from the date of acceptance"

# The same warehouse, written the way each form has room for it. The clean
# controls depend on these three agreeing: a checker that reads them as three
# different addresses would report every correct delivery as misdelivered.
DELIVERY_PLACE = (
    "DICT Central Office Warehouse, C.P. Garcia Avenue, Diliman, Quezon City"
)
DELIVERY_PLACE_SHORT = "DICT Central Office Warehouse, Diliman, Q.C."
DELIVERY_PLACE_ALT = "DICT Central Office Wh., C.P. Garcia Ave., Diliman, QC"

# The supplier's assigned team, named in the contract and expected to be the
# same people who appear on the inspection report.
PERSONNEL = [
    "Engr. Ramon T. Ilagan (Project Manager)",
    "Engr. Cielo M. Bautista (RF Systems Engineer)",
    "Mr. Dante P. Rivera (Installation Supervisor)",
]

DATES = {
    "pr": "June 12, 2024",
    "bid_opening": "August 6, 2024",
    "noa": "September 3, 2024",
    "contract_signed": "September 10, 2024",
    "ntp": "September 16, 2024",
    "delivery_due": "December 15, 2024",
    "delivery": "November 8, 2024",
    "invoice": "November 8, 2024",
    "inspection": "November 12, 2024",
    "acceptance": "November 14, 2024",
    "payment": "December 4, 2024",
}


def _signatory(role: str, name: str, position: str, date: str, page: int = 1) -> Dict:
    return {
        "role": role,
        "name": name,
        "position": position,
        "signed": True,
        "date": date,
        "page": page,
    }


def _source(filename: str, pages: int = 2) -> Dict:
    return {
        "file": f"fixtures/{filename}",
        "filename": filename,
        "total_pages": pages,
        "pages_read": pages,
        "skipped_pages": [],
        "ingest_source": "fixture",
    }


def _doc(**overrides) -> Dict:
    """A fact record with the fields every document in this packet shares."""
    base = {
        "doc_type": "other",
        "doc_type_confidence": 0.95,
        "project_title": PROJECT,
        "entity_name": ENTITY,
        "extraction_confidence": 0.9,
    }
    base.update(overrides)
    return base


def clean_packet() -> Dict[str, Dict]:
    """The full clean packet, keyed by a short handle per document."""

    purchase_request = _doc(
        doc_type="pr",
        doc_number=PR_NO,
        pr_no=PR_NO,
        end_user="Emergency Communications Service, DICT",
        mode_of_procurement="Competitive Bidding",
        amounts={"abc": ABC, "total": CONTRACT_TOTAL},
        items=copy.deepcopy(ITEMS),
        dates={"document": DATES["pr"], "pr": DATES["pr"]},
        signatories=[
            _signatory("Requested by", "A. Dimasalang", "Service Director", DATES["pr"]),
            _signatory("Funds Certified Available by", "R. Villanueva", "Chief Accountant", "June 14, 2024"),
            _signatory("Approved by", "M. Santiago", "Undersecretary", "June 17, 2024"),
        ],
        source=_source("01 Purchase Request.pdf", 1),
    )

    terms_of_reference = _doc(
        doc_type="tor",
        doc_number="TOR-GECS-2024-001",
        mode_of_procurement="Competitive Bidding",
        amounts={"abc": ABC},
        items=copy.deepcopy(ITEMS),
        delivery_period=DELIVERY_PERIOD,
        warranty_period=WARRANTY_PERIOD,
        deliverables=[
            "Delivery of all equipment to the DICT Central Office warehouse",
            "Installation and commissioning of five (5) repeater stations",
            "Two (2) days of operator training for twenty (20) personnel",
            "Submission of as-built documentation and frequency coordination records",
        ],
        milestones=[
            "Delivery within ninety (90) calendar days from NTP",
            "Installation and commissioning within thirty (30) days from delivery",
        ],
        dates={"document": "June 20, 2024"},
        source=_source("02 Terms of Reference.pdf", 8),
    )

    market_study = _doc(
        doc_type="market_study",
        doc_number="MR-GECS-2024-001",
        amounts={"total": ABC},
        items=[
            {
                "line_no": "1",
                "description": "VHF Base Radio Transceiver - Supplier A quotation",
                "qty": 25.0,
                "unit": "unit",
                "unit_price": 148000.00,
                "amount": 3700000.00,
                "page": 1,
            },
            {
                "line_no": "2",
                "description": "VHF Base Radio Transceiver - Supplier B quotation",
                "qty": 25.0,
                "unit": "unit",
                "unit_price": 143500.00,
                "amount": 3587500.00,
                "page": 1,
            },
            {
                "line_no": "3",
                "description": "VHF Base Radio Transceiver - PhilGEPS reference price",
                "qty": 25.0,
                "unit": "unit",
                "unit_price": 146000.00,
                "amount": 3650000.00,
                "page": 2,
            },
        ],
        dates={"document": "June 18, 2024"},
        source=_source("03 Market Research.pdf", 4),
    )

    cost_breakdown = _doc(
        doc_type="dcb",
        doc_number="DCB-GECS-2024-001",
        amounts={"abc": ABC, "total": CONTRACT_TOTAL},
        items=copy.deepcopy(ITEMS),
        dates={"document": "June 19, 2024"},
        source=_source("04 Detailed Cost Breakdown.pdf", 2),
    )

    bidding_docs = _doc(
        doc_type="bidding_docs",
        doc_number="ITB-GECS-2024-001",
        mode_of_procurement="Competitive Bidding",
        amounts={"abc": ABC},
        items=copy.deepcopy(ITEMS),
        delivery_period=DELIVERY_PERIOD,
        warranty_period=WARRANTY_PERIOD,
        eligibility_requirements=[
            "PhilGEPS Certificate of Registration (Platinum Membership)",
            "Valid Mayor's or Business Permit",
            "Income and Business Tax Returns for the preceding year",
            "Statement of all ongoing and completed government and private contracts",
            "Single Largest Completed Contract of at least 50% of the ABC",
            "Net Financial Contracting Capacity at least equal to the ABC",
            "Omnibus Sworn Statement",
        ],
        deliverables=[
            "Delivery of all equipment to the DICT Central Office warehouse",
            "Installation and commissioning of five (5) repeater stations",
            "Two (2) days of operator training for twenty (20) personnel",
            "Submission of as-built documentation and frequency coordination records",
        ],
        milestones=[
            "Delivery within ninety (90) calendar days from NTP",
            "Installation and commissioning within thirty (30) days from delivery",
        ],
        dates={"document": "July 16, 2024", "bid_opening": DATES["bid_opening"]},
        source=_source("05 Bidding Documents.pdf", 62),
    )

    contract = _doc(
        doc_type="contract",
        doc_number=CONTRACT_NO,
        contract_no=CONTRACT_NO,
        po_no=PO_NO,
        supplier=SUPPLIER,
        mode_of_procurement="Competitive Bidding",
        amounts={"contract_amount": CONTRACT_TOTAL, "total": CONTRACT_TOTAL},
        items=copy.deepcopy(ITEMS),
        delivery_period=DELIVERY_PERIOD,
        warranty_period=WARRANTY_PERIOD,
        delivery_place=DELIVERY_PLACE,
        personnel=list(PERSONNEL),
        dates={
            "document": DATES["contract_signed"],
            "contract_signed": DATES["contract_signed"],
            "noa": DATES["noa"],
            "ntp": DATES["ntp"],
            "delivery_due": DATES["delivery_due"],
        },
        signatories=[
            _signatory(
                "For the Procuring Entity",
                "M. Santiago",
                "Undersecretary",
                DATES["contract_signed"],
            ),
            _signatory(
                "For the Supplier",
                "J. Ocampo",
                "President and General Manager",
                DATES["contract_signed"],
            ),
        ],
        source=_source("06 Contract Agreement.pdf", 12),
    )

    notice_of_award = _doc(
        doc_type="noa",
        doc_number="NOA-GECS-2024-001",
        contract_no=CONTRACT_NO,
        supplier=SUPPLIER,
        amounts={"contract_amount": CONTRACT_TOTAL},
        dates={"document": DATES["noa"], "noa": DATES["noa"]},
        signatories=[
            _signatory("Approved by", "M. Santiago", "Undersecretary", DATES["noa"]),
        ],
        source=_source("07 Notice of Award.pdf", 1),
    )

    invoice = _doc(
        doc_type="invoice",
        doc_number=INVOICE_NO,
        invoice_no=INVOICE_NO,
        contract_no=CONTRACT_NO,
        po_no=PO_NO,
        supplier=SUPPLIER,
        amounts={"total": CONTRACT_TOTAL},
        items=copy.deepcopy(ITEMS),
        dates={"document": DATES["invoice"], "invoice": DATES["invoice"]},
        source=_source("08 Sales Invoice.pdf", 1),
    )

    delivery_receipt = _doc(
        doc_type="delivery_receipt",
        doc_number="DR-11284",
        contract_no=CONTRACT_NO,
        po_no=PO_NO,
        supplier=SUPPLIER,
        recipient="L. Bermudez",
        delivery_place=DELIVERY_PLACE_ALT,
        items=copy.deepcopy(ITEMS),
        dates={"document": DATES["delivery"], "delivery": DATES["delivery"]},
        signatories=[
            _signatory(
                "Delivered by", "R. Cruz", "Logistics Officer, Northbridge", DATES["delivery"]
            ),
            _signatory(
                "Received by", "L. Bermudez", "Supply Officer III", DATES["delivery"]
            ),
        ],
        source=_source("09 Delivery Receipt.pdf", 1),
    )

    iar = _doc(
        doc_type="iar",
        doc_number="IAR-2024-0311",
        contract_no=CONTRACT_NO,
        po_no=PO_NO,
        supplier=SUPPLIER,
        items=copy.deepcopy(ITEMS),
        # Written differently from the delivery receipt on purpose, and
        # naming the same officer in the reversed form the IAR uses.
        delivery_place=DELIVERY_PLACE_SHORT,
        recipient="Bermudez, Luisa M.",
        personnel=list(PERSONNEL),
        dates={
            "document": DATES["acceptance"],
            "delivery": DATES["delivery"],
            "inspection": DATES["inspection"],
            "acceptance": DATES["acceptance"],
        },
        signatories=[
            _signatory(
                "Inspected by", "E. Pascual", "Property Inspector", DATES["inspection"]
            ),
            _signatory(
                "Accepted by", "L. Bermudez", "Supply Officer III", DATES["acceptance"]
            ),
        ],
        source=_source("10 Inspection and Acceptance Report.pdf", 2),
    )

    par = _doc(
        doc_type="par",
        doc_number="PAR-2024-0498",
        contract_no=CONTRACT_NO,
        recipient="T. Aguilar",
        items=copy.deepcopy(ITEMS),
        amounts={"total": CONTRACT_TOTAL},
        dates={"document": DATES["acceptance"], "received": DATES["acceptance"]},
        signatories=[
            _signatory(
                "Issued by", "L. Bermudez", "Supply Officer III", DATES["acceptance"]
            ),
            _signatory(
                "Received by", "T. Aguilar", "Network Engineer II", DATES["acceptance"]
            ),
        ],
        source=_source("11 Property Acknowledgement Receipt.pdf", 2),
    )

    warranty = _doc(
        doc_type="warranty_certificate",
        doc_number="WC-NBT-2024-0087",
        contract_no=CONTRACT_NO,
        supplier=SUPPLIER,
        warranty_period="One (1) year from the date of acceptance",
        items=copy.deepcopy(ITEMS),
        dates={
            "document": DATES["acceptance"],
            "warranty_start": DATES["acceptance"],
            "warranty_end": "November 14, 2025",
        },
        signatories=[
            _signatory(
                "Issued by", "J. Ocampo", "President and General Manager", DATES["acceptance"]
            ),
        ],
        source=_source("12 Warranty Certificate.pdf", 1),
    )

    disbursement_voucher = _doc(
        doc_type="disbursement_voucher",
        doc_number=DV_NO,
        dv_no=DV_NO,
        ors_no=ORS_NO,
        contract_no=CONTRACT_NO,
        po_no=PO_NO,
        payee=SUPPLIER,
        supplier=SUPPLIER,
        amounts={
            "gross": CONTRACT_TOTAL,
            "tax": WITHHOLDING_TAX,
            "retention": RETENTION,
            "net": NET_DUE,
            "contract_amount": CONTRACT_TOTAL,
        },
        amount_in_words=NET_IN_WORDS,
        items=copy.deepcopy(ITEMS),
        attachments_referenced=[
            "Purchase Request",
            "Sales Invoice",
            "Delivery Receipt",
            "Inspection and Acceptance Report",
            "Property Acknowledgement Receipt",
            "Warranty Certificate",
            "BIR Tax Receipt",
        ],
        dates={
            "document": "November 20, 2024",
            "delivery": DATES["delivery"],
            "inspection": DATES["inspection"],
            "acceptance": DATES["acceptance"],
            "payment": DATES["payment"],
        },
        signatories=[
            _signatory("Prepared by", "C. Reyes", "Accounting Staff", "November 18, 2024"),
            _signatory(
                "Certified by", "R. Villanueva", "Chief Accountant", "November 19, 2024"
            ),
            _signatory(
                "Approved for Payment by", "M. Santiago", "Undersecretary", "November 20, 2024"
            ),
            _signatory(
                "Received Payment by", "J. Ocampo", "President and General Manager",
                DATES["payment"],
            ),
        ],
        page_refs={
            "amounts.net": 1,
            "amount_in_words": 1,
            "payee": 1,
            "dv_no": 1,
        },
        source=_source("13 Disbursement Voucher.pdf", 1),
    )

    tax_receipt = _doc(
        doc_type="tax_receipt",
        doc_number="BIR-2306-2024-11-0412",
        supplier=SUPPLIER,
        amounts={"total": WITHHOLDING_TAX},
        dates={"document": DATES["payment"]},
        source=_source("14 BIR Form 2306.pdf", 1),
    )

    return {
        "pr": purchase_request,
        "tor": terms_of_reference,
        "market_study": market_study,
        "dcb": cost_breakdown,
        "bidding_docs": bidding_docs,
        "contract": contract,
        "noa": notice_of_award,
        "invoice": invoice,
        "delivery_receipt": delivery_receipt,
        "iar": iar,
        "par": par,
        "warranty": warranty,
        "dv": disbursement_voucher,
        "tax_receipt": tax_receipt,
    }


# The documents that make up each workflow, so a mutation can be scoped to
# just the packet it is about.
PAYMENT_PACKET = ["dv", "invoice", "delivery_receipt", "iar", "par", "warranty", "tax_receipt"]
PLANNING_PACKET = ["pr", "tor", "market_study", "dcb", "bidding_docs"]
CONTRACT_PACKET = ["contract", "noa"]
FULL_PACKET = PLANNING_PACKET + CONTRACT_PACKET + PAYMENT_PACKET
