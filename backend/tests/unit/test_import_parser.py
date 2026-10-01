import base64
import io
import zipfile
from decimal import Decimal

import pytest

from app.modules.imports.parser import normalize, number, read_file, xml
from app.modules.imports.schemas import FileRequest, Mapping


def file_request(text: str, mapping: Mapping | None = None) -> FileRequest:
    return FileRequest(
        filename="statement.csv",
        content=base64.b64encode(text.encode()).decode(),
        mapping=mapping or Mapping(amount=0, description=1, direction=None, currency=None),
    )


def test_csv_preserves_all_statuses_and_blank_rows() -> None:
    _, sheets, rows = read_file(
        file_request("amount;description;status\n-283;Coffee;pending\n-2500;Transfer;done\n;;\n")
    )
    assert sheets == ["CSV"]
    assert len(rows) == 4
    assert rows[1][2] == "pending"
    assert (
        normalize(rows[1], Mapping(amount=0, description=1, direction=None, currency=None))[1]
        == "283"
    )


@pytest.mark.parametrize(
    "value,separator,expected",
    [
        ("9 999 999 999 999,9999", ",", "9999999999999.9999"),
        ("84.99", ".", "84.99"),
        ("1\u202f283,50", ",", "1283.50"),
    ],
)
def test_exact_amount(value: str, separator: str, expected: str) -> None:
    mapping = Mapping.model_validate({"decimal_separator": separator})
    assert number(value, mapping) == Decimal(expected)


@pytest.mark.parametrize(
    "value", ["nan", "inf", "1e5", "1.00001", "1,234", "10000000000000000", "=SUM(A1)"]
)
def test_invalid_amount(value: str) -> None:
    with pytest.raises(ValueError):
        number(value, Mapping())


def test_split_columns_and_currency_alias() -> None:
    mapping = Mapping(debit=0, credit=1, description=2, currency=3)
    assert normalize(["84.99", "", "Shop", "RUR"], mapping) == ("expense", "84.99", "Shop", "RUB")
    with pytest.raises(ValueError):
        normalize(["5", "2"], mapping)


def test_xlsx_reads_numeric_xml_without_float_and_never_evaluates_formula() -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            "<sheets>"
            '<sheet name="Data" r:id="r1"/>'
            "</sheets>"
            "</workbook>",
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            "<Relationships>"
            '<Relationship Id="r1" Target="/xl/worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        z.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheetData>"
            '<row r="1">'
            '<c r="A1">'
            "<v>9999999999999999.9999</v>"
            "</c>"
            '<c r="B1">'
            "<f>1+1</f>"
            "<v>2</v>"
            "</c>"
            "</row>"
            '<row r="3">'
            '<c r="A3" t="inlineStr">'
            "<is>"
            "<t>pending</t>"
            "</is>"
            "</c>"
            "</row>"
            "</sheetData>"
            "</worksheet>",
        )
    request = FileRequest(
        filename="test.xlsx", content=base64.b64encode(stream.getvalue()).decode()
    )
    _, sheets, rows = read_file(request)
    assert sheets == ["Data"]
    assert rows == [["9999999999999999.9999", "[formula unsupported]"], [], ["pending"]]


def test_file_bounds_and_unsupported_format() -> None:
    with pytest.raises(ValueError):
        xml(b'<!DOCTYPE root [<!ENTITY x "unsafe">]><root>&x;</root>')
    with pytest.raises(ValueError):
        xml("<root/>".encode("utf-16"))
    with pytest.raises(ValueError):
        read_file(file_request("x\n" * 2001))
    with pytest.raises(ValueError):
        read_file(FileRequest(filename="test.pdf", content=""))


def workbook_reference(cell: str, row: str = "1") -> FileRequest:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Data" r:id="r1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="r1" '
            'Target="/xl/worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData><row r="{row}"><c r="{cell}"><v>1.0001</v></c></row>'
            "</sheetData></worksheet>",
        )
    return FileRequest(
        filename="malformed.xlsx", content=base64.b64encode(stream.getvalue()).decode()
    )


@pytest.mark.parametrize(
    "cell,row",
    [
        ("A" * 1_000_000 + "1", "1"),
        ("a1", "1"),
        ("A0", "1"),
        ("A01", "1"),
        ("A2", "1"),
        ("CW1", "1"),
        ("1", "1"),
        ("A1", "0"),
        ("A1", "1" * 100_000),
        ("A2001", "2001"),
    ],
)
def test_xlsx_rejects_long_malformed_and_out_of_range_coordinates(cell: str, row: str) -> None:
    with pytest.raises(ValueError):
        read_file(workbook_reference(cell, row))


def test_xlsx_last_supported_column_and_row_preserve_exact_text() -> None:
    _, _, rows = read_file(workbook_reference("CV2000", "2000"))
    assert len(rows) == 2000
    assert len(rows[-1]) == 100
    assert rows[-1][-1] == "1.0001"
