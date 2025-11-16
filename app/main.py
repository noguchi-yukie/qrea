
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, date
from typing import Optional

from .db import (
    SessionLocal,
    init_db,
    Document,
    get_by_qr_id,
    get_settings,
    EXTRA_FIELD_RANGE,
    DEFAULT_FIELD_LABELS,
)

app = FastAPI(title="QR Linker App")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def _format_dt_seconds(value):
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


templates.env.filters["dtsec"] = _format_dt_seconds

def _default_label(idx: int) -> str:
    return DEFAULT_FIELD_LABELS[idx - 1]


def _build_extra_field_meta(settings, doc=None):
    fields = []
    for idx in EXTRA_FIELD_RANGE:
        label_attr = f"field{idx}_label"
        label = getattr(settings, label_attr) or _default_label(idx)
        attr_name = f"field{idx}_value"
        fields.append(
            {
                "index": idx,
                "label": label,
                "attr": attr_name,
                "name": f"field{idx}",
                "value": getattr(doc, attr_name) if doc and hasattr(doc, attr_name) else "",
            }
        )
    return fields


def _assign_extra_values(target: Document, values: list[str | None]) -> None:
    for idx, value in enumerate(values, start=1):
        setattr(target, f"field{idx}_value", value or None)


def _build_label_fields(settings):
    return [
        {
            "index": idx,
            "name": f"field{idx}_label",
            "value": getattr(settings, f"field{idx}_label") or _default_label(idx),
            "placeholder": _default_label(idx),
        }
        for idx in EXTRA_FIELD_RANGE
    ]


def _datetime_input_value(value: Optional[datetime]) -> str:
    if not value:
        return ""
    return value.replace(microsecond=0).isoformat(timespec="seconds")


# --- DB session dep

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/scan", response_class=HTMLResponse)
def scan(request: Request, mode: str = "assign"):
    if mode not in ("assign", "return"):
        mode = "assign"
    return templates.TemplateResponse("scan.html", {"request": request, "mode": mode})


@app.get("/assign/{qr_id}", response_class=HTMLResponse)
def assign_form(request: Request, qr_id: str, db: Session = Depends(get_db)):
    doc = get_by_qr_id(db, qr_id)
    settings = get_settings(db)
    extra_fields = _build_extra_field_meta(settings, doc)
    return templates.TemplateResponse(
        "assign_form.html",
        {
            "request": request,
            "qr_id": qr_id,
            "doc": doc,
            "extra_fields": extra_fields,
            "settings": settings,
            "distributed_value": _datetime_input_value(doc.distributed_at if doc else None),
            "due_value": doc.due_date.isoformat() if doc and doc.due_date else "",
        },
    )


@app.post("/assign/{qr_id}")
def assign_save(
    qr_id: str,
    recipient: str = Form(...),
    distributed_by: Optional[str] = Form(None),
    distributed_at: Optional[str] = Form(None),
    due_date: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    field1: Optional[str] = Form(None),
    field2: Optional[str] = Form(None),
    field3: Optional[str] = Form(None),
    field4: Optional[str] = Form(None),
    field5: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    doc = get_by_qr_id(db, qr_id)
    if not doc:
        doc = Document(qr_id=qr_id)
        db.add(doc)

    doc.title = title or doc.title
    doc.recipient = recipient
    doc.distributed_by = distributed_by
    doc.distributed_at = (
        datetime.fromisoformat(distributed_at) if distributed_at else datetime.utcnow()
    )
    doc.due_date = date.fromisoformat(due_date) if due_date else None
    doc.status = "assigned"
    doc.notes = notes
    _assign_extra_values(doc, [field1, field2, field3, field4, field5])

    db.commit()
    return RedirectResponse(url=f"/detail/{qr_id}", status_code=303)


@app.get("/return/{qr_id}", response_class=HTMLResponse)
def return_form(request: Request, qr_id: str, db: Session = Depends(get_db)):
    doc = get_by_qr_id(db, qr_id)
    if not doc:
        # Not registered before; allow creating a stub then mark return
        doc = Document(qr_id=qr_id, status="assigned")
        db.add(doc)
        db.commit()
        db.refresh(doc)
    return templates.TemplateResponse("return_form.html", {"request": request, "qr_id": qr_id, "doc": doc})


@app.post("/return/{qr_id}")
def return_save(
    qr_id: str,
    returned_by: Optional[str] = Form(None),
    returned_at: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    doc = get_by_qr_id(db, qr_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Unknown QR ID")

    doc.returned_by = returned_by
    doc.returned_at = (
        datetime.fromisoformat(returned_at) if returned_at else datetime.utcnow()
    )
    doc.status = "returned"
    if notes:
        doc.notes = (doc.notes + "\n" if doc.notes else "") + notes

    db.commit()
    return RedirectResponse(url=f"/detail/{qr_id}", status_code=303)


@app.get("/list", response_class=HTMLResponse)
def list_view(
    request: Request,
    q: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    stmt = select(Document)
    if status in ("new", "assigned", "returned"):
        stmt = stmt.where(Document.status == status)
    docs = db.execute(stmt).scalars().all()
    # simple client-side filter for q (title/recipient/qr_id)
    settings = get_settings(db)
    extra_fields = _build_extra_field_meta(settings)
    return templates.TemplateResponse(
        "list.html",
        {
            "request": request,
            "docs": docs,
            "q": q or "",
            "status": status or "",
            "extra_fields": extra_fields,
        },
    )


@app.get("/detail/{qr_id}", response_class=HTMLResponse)
def detail_view(request: Request, qr_id: str, db: Session = Depends(get_db)):
    doc = get_by_qr_id(db, qr_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Unknown QR ID")
    settings = get_settings(db)
    extra_fields = _build_extra_field_meta(settings, doc)
    return templates.TemplateResponse(
        "detail.html",
        {
            "request": request,
            "doc": doc,
            "extra_fields": extra_fields,
        },
    )


@app.get("/export.csv")
def export_csv(db: Session = Depends(get_db)):
    import csv
    from io import StringIO

    settings = get_settings(db)
    extra_fields = _build_extra_field_meta(settings)

    output = StringIO()
    writer = csv.writer(output)
    header = [
        "qr_id",
        "title",
        "recipient",
        "distributed_by",
        "distributed_at",
        "due_date",
        "returned_by",
        "returned_at",
        "status",
    ] + [field["label"] for field in extra_fields] + ["notes"]
    writer.writerow(header)
    for d in db.query(Document).all():
        row = [
            d.qr_id,
            d.title or "",
            d.recipient or "",
            d.distributed_by or "",
            d.distributed_at.replace(microsecond=0).isoformat(timespec="seconds") if d.distributed_at else "",
            d.due_date.isoformat() if d.due_date else "",
            d.returned_by or "",
            d.returned_at.replace(microsecond=0).isoformat(timespec="seconds") if d.returned_at else "",
            d.status,
        ]
        row.extend((getattr(d, field["attr"]) or "") for field in extra_fields)
        row.append((d.notes or "").replace("\n", " "))
        writer.writerow(row)
    output.seek(0)
    return Response(content=output.read(), media_type="text/csv")


@app.get("/settings", response_class=HTMLResponse)
def settings_form(request: Request, saved: Optional[str] = None, db: Session = Depends(get_db)):
    settings = get_settings(db)
    label_fields = _build_label_fields(settings)
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "settings": settings, "label_fields": label_fields, "saved": saved},
    )


@app.post("/settings")
def settings_save(
    request: Request,
    db: Session = Depends(get_db),
    field1_label: str = Form(""),
    field2_label: str = Form(""),
    field3_label: str = Form(""),
    field4_label: str = Form(""),
    field5_label: str = Form(""),
):
    settings = get_settings(db)
    labels = [field1_label, field2_label, field3_label, field4_label, field5_label]
    for idx, label in enumerate(labels, start=1):
        cleaned = (label or "").strip() or _default_label(idx)
        setattr(settings, f"field{idx}_label", cleaned)
    db.commit()
    return RedirectResponse(url="/settings?saved=1", status_code=303)
