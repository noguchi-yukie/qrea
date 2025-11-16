
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Date,
    Text,
    UniqueConstraint,
    select,
    text,
    inspect,
)
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column

DATABASE_URL = "sqlite:///./qr_linker.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

EXTRA_FIELD_RANGE = range(1, 6)
DEFAULT_FIELD_LABELS = [f"項目{i}" for i in EXTRA_FIELD_RANGE]

class Base(DeclarativeBase):
    pass

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    qr_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # distribution
    recipient: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    distributed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    distributed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    field1_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    field2_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    field3_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    field4_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    field5_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # return
    returned_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    returned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(32), default="new", index=True)  # new|assigned|returned
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("qr_id", name="uq_documents_qr_id"),
    )


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    field1_label: Mapped[str] = mapped_column(String(255), default=DEFAULT_FIELD_LABELS[0])
    field2_label: Mapped[str] = mapped_column(String(255), default=DEFAULT_FIELD_LABELS[1])
    field3_label: Mapped[str] = mapped_column(String(255), default=DEFAULT_FIELD_LABELS[2])
    field4_label: Mapped[str] = mapped_column(String(255), default=DEFAULT_FIELD_LABELS[3])
    field5_label: Mapped[str] = mapped_column(String(255), default=DEFAULT_FIELD_LABELS[4])


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_document_extra_columns()
    with SessionLocal() as session:
        get_settings(session)


def get_by_qr_id(db, qr_id: str) -> Optional[Document]:
    stmt = select(Document).where(Document.qr_id == qr_id)
    return db.execute(stmt).scalars().first()


def get_settings(db) -> AppSettings:
    settings = db.get(AppSettings, 1)
    if not settings:
        settings = AppSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def _ensure_document_extra_columns() -> None:
    inspector = inspect(engine)
    if not inspector.has_table(Document.__tablename__):
        return
    existing = {column["name"] for column in inspector.get_columns(Document.__tablename__)}
    with engine.begin() as conn:
        for idx in EXTRA_FIELD_RANGE:
            column_name = f"field{idx}_value"
            if column_name not in existing:
                conn.execute(
                    text(f"ALTER TABLE {Document.__tablename__} ADD COLUMN {column_name} VARCHAR(255)")
                )
