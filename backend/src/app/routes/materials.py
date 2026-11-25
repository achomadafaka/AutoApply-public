from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import zipfile
from xml.sax.saxutils import escape as _xml_escape

from ..db import db_conn
from ..repo import get_material, delete_material
from ..schemas import MaterialOut


router = APIRouter(tags=["materials"])


@router.get("/materials/{material_id}", response_model=MaterialOut)
def materials_get(material_id: str):
    with db_conn() as conn:
        material = get_material(conn, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


@router.delete("/materials/{material_id}", response_model=MaterialOut)
def materials_delete(material_id: str):
    with db_conn() as conn:
        deleted = delete_material(conn, material_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Material not found")
    (Path("artifacts/materials") / f"{Path(material_id).name}.docx").unlink(missing_ok=True)
    return deleted


def _write_docx_from_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lines = text.splitlines() if text else [""]
    paragraphs = []
    for line in lines:
        safe = _xml_escape(line)
        paragraphs.append(f"<w:p><w:r><w:t>{safe}</w:t></w:r></w:p>")
    body = "".join(paragraphs)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/></w:sectPr></w:body>"
        "</w:document>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    doc_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", doc_rels_xml)


@router.get("/materials/{material_id}/file")
def materials_file(material_id: str):
    with db_conn() as conn:
        material = get_material(conn, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    out_dir = Path("artifacts/materials")
    out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = out_dir / f"{material_id}.docx"
    if not path.exists():
        _write_docx_from_text(material.get("content_text") or "", path)
    return FileResponse(path, filename=path.name,
                        headers={"X-Content-Type-Options": "nosniff"})
