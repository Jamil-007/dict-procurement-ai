"""The two matchers that compare people and places.

Both exist because `fuzzy` gets these wrong in both directions. A name is
written "JUAN D. CRUZ" on one form and "Cruz, Juan D." on the next, which
string similarity scores low; and "Juan D. Cruz" against "Juan D. Cruzada",
which it scores high. An address is written at whatever length the form
allows. Getting either wrong is expensive in opposite ways -- a false
positive teaches a committee to ignore the checker, and a false negative is
a payment to the wrong person or goods at the wrong address.
"""

from __future__ import annotations

import pytest

from consistency.matchers import address_equivalent, person_name

NO_PARAMS: dict = {}


# -- person_name -----------------------------------------------------------


@pytest.mark.parametrize(
    "left,right",
    [
        ("Juan D. Cruz", "JUAN D. CRUZ"),
        ("Juan D. Cruz", "Cruz, Juan D."),
        ("L. Bermudez", "Bermudez, Luisa M."),
        ("Engr. Ramon T. Ilagan", "Ramon Ilagan"),
        ("Maria Santos-Reyes Jr.", "maria santos reyes"),
        ("J. D. Cruz", "Juan Dela Cruz"),
    ],
)
def test_the_same_person_written_differently_agrees(left, right):
    assert person_name(left, right, NO_PARAMS).agree


@pytest.mark.parametrize(
    "left,right",
    [
        ("Juan D. Cruz", "Maria D. Cruz"),
        ("L. Bermudez", "Navarro, Fidel C."),
        ("Engr. Cielo M. Bautista", "Engr. Feliza O. Mendrez"),
    ],
)
def test_different_people_disagree(left, right):
    assert not person_name(left, right, NO_PARAMS).agree


def test_a_surname_typo_is_not_a_different_person():
    """One transcription slip off a scan must not read as a substitution."""
    assert person_name("Bermudez, Luisa", "Bermudes, Luisa", NO_PARAMS).agree


def test_a_longer_surname_is_a_different_person():
    """The tolerance for typos must not swallow a genuinely different name."""
    assert not person_name("Juan D. Cruz", "Juan D. Cruzada", NO_PARAMS).agree


def test_an_absent_name_is_not_a_discrepancy():
    result = person_name("Juan D. Cruz", None, NO_PARAMS)
    assert not result.comparable


def test_a_name_of_nothing_but_honorifics_is_not_comparable():
    assert not person_name("Mr.", "Juan D. Cruz", NO_PARAMS).comparable


# -- address_equivalent ----------------------------------------------------


@pytest.mark.parametrize(
    "left,right",
    [
        (
            "DICT Central Office Warehouse, C.P. Garcia Avenue, Diliman, Quezon City",
            "DICT Central Office Wh., C.P. Garcia Ave., Diliman, QC",
        ),
        (
            "DICT Central Office Warehouse, C.P. Garcia Avenue, Diliman, Quezon City",
            "DICT Central Office Warehouse, Diliman, Q.C.",
        ),
        ("3rd Floor, DICT Building, Diliman", "3F DICT Bldg., Diliman"),
        ("Brgy. Holy Spirit, Quezon City", "Barangay Holy Spirit, Quezon City"),
    ],
)
def test_the_same_place_written_differently_agrees(left, right):
    assert address_equivalent(left, right, NO_PARAMS).agree


@pytest.mark.parametrize(
    "left,right",
    [
        (
            "DICT Central Office Warehouse, C.P. Garcia Avenue, Diliman, Quezon City",
            "DICT Regional Office IV-A, National Highway, Calamba, Laguna",
        ),
        ("DICT Building, Diliman, Quezon City", "Cebu Provincial Capitol, Cebu City"),
    ],
)
def test_a_different_place_disagrees(left, right):
    assert not address_equivalent(left, right, NO_PARAMS).agree


@pytest.mark.parametrize(
    "left,right",
    [
        (
            "Unit 304, DICT Building, C.P. Garcia Avenue, Diliman, Quezon City",
            "Unit 907, DICT Building, C.P. Garcia Avenue, Diliman, Quezon City",
        ),
        # An ordinal floor has to reach the same number as a bare one, or
        # "3rd Floor" and "5th Floor" read as the same room.
        ("3rd Floor, DICT Building, Diliman", "5th Floor, DICT Building, Diliman"),
        ("3rd Floor, DICT Building, Diliman", "5F DICT Bldg., Diliman"),
    ],
)
def test_a_different_unit_or_floor_is_a_different_address(left, right):
    """Everything else matching is exactly when the number matters most."""
    result = address_equivalent(left, right, NO_PARAMS)
    assert not result.agree
    assert "numbers do not match" in result.detail


def test_an_absent_place_is_not_a_discrepancy():
    assert not address_equivalent("DICT Building, Diliman", "", NO_PARAMS).comparable
