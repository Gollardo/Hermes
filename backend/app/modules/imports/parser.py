"""Bounded, non-executing readers. XLSX numeric XML stays decimal text."""

import base64
import csv
import hashlib
import io
import posixpath
import re
import zipfile
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

from app.modules.imports.schemas import FileRequest, Mapping

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MAX_ROWS = 2000


def xml(raw: bytes) -> ET.Element:
    if b"\x00" in raw or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("Unsafe XML")
    return ET.fromstring(raw)


def read_file(request: FileRequest) -> tuple[str, list[str], list[list[str]]]:
    try:
        raw = base64.b64decode(request.content, validate=True)
        if len(raw) > 5_000_000:
            raise ValueError("File exceeds 5 MB")
        digest = hashlib.sha256(raw).hexdigest()
        if request.filename.lower().endswith(".csv"):
            text = raw.decode(request.mapping.encoding)
            delimiter: str = request.mapping.delimiter
            if not delimiter:
                try:
                    delimiter = csv.Sniffer().sniff(text[:8192], delimiters=",;\t").delimiter
                except csv.Error:
                    delimiter = ";"
            rows = []
            for row in csv.reader(io.StringIO(text), delimiter=delimiter):
                rows.append(row)
                if len(rows) > MAX_ROWS:
                    raise ValueError("Too many rows")
            sheets = ["CSV"]
        elif request.filename.lower().endswith(".xlsx"):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if (
                    len(archive.infolist()) > 1000
                    or sum(i.file_size for i in archive.infolist()) > 20_000_000
                ):
                    raise ValueError("Expanded workbook exceeds limit")
                names = archive.namelist()
                if any("externalLinks/" in name or "vbaProject" in name for name in names):
                    raise ValueError("External links and macros are unsupported")
                workbook = xml(archive.read("xl/workbook.xml"))
                relations = {
                    r.attrib["Id"]: posixpath.normpath(
                        r.attrib["Target"].lstrip("/")
                        if r.attrib["Target"].startswith("/")
                        else "xl/" + r.attrib["Target"]
                    )
                    for r in xml(archive.read("xl/_rels/workbook.xml.rels"))
                    if r.attrib.get("TargetMode") != "External"
                }
                sheet_nodes = workbook.findall("m:sheets/m:sheet", NS)
                sheets = [s.attrib["name"] for s in sheet_nodes]
                selected = request.mapping.sheet or sheets[0]
                node = next(s for s in sheet_nodes if s.attrib["name"] == selected)
                target = relations[
                    node.attrib[
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                    ]
                ]
                target = target.lstrip("/")
                strings = []
                if "xl/sharedStrings.xml" in names:
                    strings = [
                        "".join(n.itertext())
                        for n in xml(archive.read("xl/sharedStrings.xml")).findall("m:si", NS)
                    ]
                rows = []
                for xml_row in xml(archive.read(target)).findall("m:sheetData/m:row", NS):
                    number = int(xml_row.attrib["r"])
                    if number > MAX_ROWS:
                        raise ValueError("Too many rows")
                    while len(rows) < number:
                        rows.append([])
                    for cell in xml_row:
                        letters = re.sub(r"[0-9]", "", cell.attrib["r"])
                        col = 0
                        for letter in letters:
                            col = col * 26 + ord(letter) - 64
                        if col > 100:
                            raise ValueError("Too many columns")
                        while len(rows[number - 1]) < col:
                            rows[number - 1].append("")
                        value = cell.findtext("m:v", default="", namespaces=NS)
                        if cell.find("m:f", NS) is not None:
                            value = "[formula unsupported]"
                        elif cell.attrib.get("t") == "s":
                            value = strings[int(value)]
                        elif cell.attrib.get("t") == "inlineStr":
                            value = "".join(cell.itertext())
                        rows[number - 1][col - 1] = value
        else:
            raise ValueError("Only CSV and XLSX are supported")
        if not rows or any(len(r) > 100 or any(len(c) > 4000 for c in r) for r in rows):
            raise ValueError("Invalid table size")
        return digest, sheets, rows
    except (
        KeyError,
        StopIteration,
        IndexError,
        UnicodeError,
        zipfile.BadZipFile,
        ET.ParseError,
        csv.Error,
    ) as error:
        raise ValueError("Invalid statement file") from error


def number(value: str, mapping: Mapping) -> Decimal:
    value = re.sub(r"[\s\u00a0\u202f]", "", value)
    if mapping.decimal_separator == ",":
        value = value.replace(",", ".")
    if not re.fullmatch(r"[+-]?\d+(?:\.\d{1,4})?", value):
        raise ValueError("Invalid exact amount")
    try:
        amount = Decimal(value)
        if abs(amount) >= Decimal("10000000000000000"):
            raise ValueError("Amount exceeds supported precision")
        return amount
    except InvalidOperation as error:
        raise ValueError("Invalid amount") from error


def normalize(row: list[str], mapping: Mapping) -> tuple[str, str, str, str]:
    def cell(index: int | None) -> str:
        return row[index].strip() if index is not None and index < len(row) else ""

    if mapping.debit is not None or mapping.credit is not None:
        debit = number(cell(mapping.debit) or "0", mapping)
        credit = number(cell(mapping.credit) or "0", mapping)
        if debit < 0 or credit < 0 or (debit > 0) == (credit > 0):
            raise ValueError("Expected either debit or credit")
        amount = credit - debit
        kind = "income" if amount > 0 else "expense"
    else:
        amount = number(cell(mapping.amount), mapping)
        if mapping.direction is None:
            kind = "income" if amount > 0 else "expense"
        else:
            direction = cell(mapping.direction).casefold()
            if direction in [s.strip().casefold() for s in mapping.expense_values.split(",")]:
                kind = "expense"
            elif direction in [s.strip().casefold() for s in mapping.income_values.split(",")]:
                kind = "income"
            else:
                raise ValueError("Unknown direction")
    if amount == 0:
        raise ValueError("Zero amount")
    currency = cell(mapping.currency).upper()
    return (
        kind,
        str(abs(amount)),
        cell(mapping.description),
        "RUB" if currency == "RUR" else currency,
    )
