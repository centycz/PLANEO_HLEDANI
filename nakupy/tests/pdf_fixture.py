"""Minimalni generator PDF pro testy - bez dalsich zavislosti."""
from __future__ import annotations

from pathlib import Path


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def write_pdf(path: str | Path, pages: list[list[str]]) -> Path:
    """Vytvori jednoduche textove PDF; kazda stranka je seznam radku."""
    path = Path(path)
    objects: list[bytes] = []

    page_ids = [3 + index * 2 for index, _ in enumerate(pages)]
    font_id = 3 + len(pages) * 2

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("latin-1"))

    for index, lines in enumerate(pages):
        content_id = page_ids[index] + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Contents {content_id} 0 R "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>"
            ).encode("latin-1")
        )
        body = "BT /F1 11 Tf 40 800 Td 16 TL\n"
        for line in lines:
            body += f"({_escape(line)}) Tj T*\n"
        body += "ET"
        stream = body.encode("latin-1", "replace")
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, payload in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + payload + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode()

    path.write_bytes(bytes(out))
    return path
