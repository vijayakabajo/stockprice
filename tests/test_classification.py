import pytest

from market.classification import display_name, sector_name, title_case, unique_slug


@pytest.mark.parametrize(
    "raw, expected",
    [
        # The prototype's sample, and the names it shows.
        ("Agilent Technologies Inc.", "Agilent Technologies"),
        ("Alcoa Corp", "Alcoa"),
        ("Applied Optoelectronics, Inc.", "Applied Optoelectronics"),
        ("American Airlines Group Inc.", "American Airlines"),
        ("Aaon Inc", "Aaon"),
        ("Ares Acquisition Corporation III", "Ares Acquisition III"),
        ("Abony Acquisition Corp I Class A Ordinary Shares", "Abony Acquisition I"),
        ("Apogee Acquisition Corp Class A Ordinary Shares", "Apogee Acquisition"),
        ("ATA Creativity Global American Depositary Shares", "ATA Creativity Global"),
        # Beyond the sample.
        ("Broadcom Inc. Common Stock", "Broadcom"),
        ("ABBVIE INC.", "Abbvie"),
        ("AT&T INC.", "AT&T"),
        ("Bank of America Corporation", "Bank of America"),
        ("Inc", "Inc"),
        ("", ""),
    ],
)
def test_display_name(raw, expected):
    assert display_name(raw) == expected


def test_title_case_keeps_acronyms_and_apostrophes():
    assert (
        sector_name("AIRCRAFT PARTS & AUXILIARY EQUIPMENT, NEC")
        == "Aircraft Parts & Auxiliary Equipment, NEC"
    )
    assert title_case("WOMEN'S, MISSES' OUTERWEAR") == "Women's, Misses' Outerwear"


def test_unique_slug_falls_back_on_collision():
    assert unique_slug("Blank Checks", set(), "6770") == "blank-checks"
    assert unique_slug("Blank Checks", {"blank-checks"}, "6770") == "blank-checks-6770"
