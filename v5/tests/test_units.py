import pytest

from hth.domain.units import UnitError, compatible_units, convert, family, format_qty, normalize


def test_normalize_aliases():
    assert normalize(" kgs ") == "KG" and normalize("gm") == "G" and normalize("quintal") == "QTL"
    assert normalize("Ltr.") == "LTR" and normalize("nos") == "PCS" and normalize("") == ""


def test_families_and_compatibility():
    assert family("KG") == "mass" and family("ML") == "volume" and family("BAG") is None
    assert compatible_units("KG") == ["KG", "G", "QTL"]
    assert compatible_units("G") == ["G", "KG", "QTL"]
    assert compatible_units("BAG") == ["BAG"]


@pytest.mark.parametrize(
    "qty,src,dst,expected",
    [
        (100, "G", "KG", 0.1),
        (2, "QTL", "KG", 200),
        (250, "KG", "QTL", 2.5),
        (1500, "ML", "LTR", 1.5),
        (3, "KG", "KG", 3),
    ],
)
def test_convert(qty, src, dst, expected):
    assert convert(qty, src, dst) == pytest.approx(expected)


def test_convert_incompatible():
    with pytest.raises(UnitError):
        convert(1, "KG", "LTR")
    with pytest.raises(UnitError):
        convert(1, "BAG", "PCS")


def test_format_qty():
    assert format_qty(0.1, "KG") == "0.1 KG"
    assert format_qty(1234, "KG") == "1,234 KG"
    assert format_qty(2.5, "QTL") == "2.5 QTL"
    assert format_qty(0.125, "") == "0.125"
