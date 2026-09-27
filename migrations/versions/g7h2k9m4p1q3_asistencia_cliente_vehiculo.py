"""asistencias_emergencia: vincular cliente y vehiculo (idempotente, SQLite seguro)

Motivo (fase 26.6): las solicitudes de asistencia de emergencia se guardaban
sin relacion con el cliente ni con el vehiculo, por lo que el personal del
taller veia unicamente "Solicitud #12" sin contexto.

Se agregan dos columnas NUEVAS y NULLABLE mas sus indices. No se modifica ni
borra ninguna columna o fila existente: los registros historicos quedan con
cliente_id/vehiculo_id en NULL y siguen funcionando.

Revision ID: g7h2k9m4p1q3
Revises: 006_ubicaciones
Create Date: 2026-09-26 00:00:00.000000
"""
import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

logger = logging.getLogger("alembic.fase26_asistencia_contexto")


revision = "g7h2k9m4p1q3"
down_revision = "006_ubicaciones"
branch_labels = None
depends_on = None


TABLA = "asistencias_emergencia"
COLUMNAS = (
    ("cliente_id", "clientes"),
    ("vehiculo_id", "vehiculos"),
)


def _columnas() -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(TABLA)}


def _indices() -> set[str]:
    return {ix["name"] for ix in inspect(op.get_bind()).get_indexes(TABLA)}


def _fks() -> set[str]:
    inspector = inspect(op.get_bind())
    return {
        fk.get("constrained_columns", [None])[0] if isinstance(fk, dict) else None
        for fk in inspector.get_foreign_keys(TABLA)
    }


def _indice(columna: str) -> str:
    return f"ix_{TABLA}_{columna}"


def upgrade():
    existentes = _columnas()

    # 1. Columnas nuevas. aditivas y nullable: ningun registro existente se toca.
    for columna, _ in COLUMNAS:
        if columna not in existentes:
            op.add_column(TABLA, sa.Column(columna, sa.Integer(), nullable=True))

    # 2. Indices para los consultas del panel del taller.
    for columna, _ in COLUMNAS:
        nombre = _indice(columna)
        if nombre not in _indices():
            op.create_index(nombre, TABLA, [columna], unique=False)

    # 3. Claves foraneas. En SQLite anadir FK a una tabla existente exige
    #    recrearla; si el motor no lo permite se omite sin romper el despliegue
    #    (las columnas y los indices ya quedan operativos).
    for columna, referenciada in COLUMNAS:
        if columna in _fks():
            continue
        try:
            with op.batch_alter_table(TABLA, schema=None) as batch_op:
                batch_op.create_foreign_key(
                    f"fk_{TABLA}_{columna}", referenciada, [columna], ["id"]
                )
        except Exception as exc:  # pragma: no cover - depende del motor
            logger.warning(
                "No se pudo crear la FK %s.%s -> %s.id: %s", TABLA, columna, referenciada, exc
            )


def downgrade():
    for columna, _ in reversed(COLUMNAS):
        if columna in _fks():
            try:
                with op.batch_alter_table(TABLA, schema=None) as batch_op:
                    batch_op.drop_constraint(f"fk_{TABLA}_{columna}", type_="foreignkey")
            except Exception as exc:  # pragma: no cover - depende del motor
                logger.warning("No se pudo eliminar la FK %s: %s", columna, exc)

    for columna, _ in reversed(COLUMNAS):
        nombre = _indice(columna)
        if nombre in _indices():
            op.drop_index(nombre, table_name=TABLA)
        if columna in _columnas():
            op.drop_column(TABLA, columna)
