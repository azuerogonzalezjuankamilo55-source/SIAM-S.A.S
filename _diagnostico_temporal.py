"""Diagnóstico temporal del esquema SIAM (se elimina después)."""
import os
os.environ["FLASK_ENV"] = "development"

from app import create_app
from database.db import db

app = create_app()
with app.app_context():
    # Columnas de usuarios
    rows = db.session.execute(
        db.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='usuarios' ORDER BY ordinal_position"
        )
    ).fetchall()
    print("COLUMNAS usuarios:", [r[0] for r in rows])

    # Columnas de configuracion_taller
    rows2 = db.session.execute(
        db.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='configuracion_taller' ORDER BY ordinal_position"
        )
    ).fetchall()
    print("COLUMNAS configuracion_taller:", [r[0] for r in rows2])

    # Índices citas
    rows3 = db.session.execute(
        db.text(
            "SELECT indexname FROM pg_indexes WHERE tablename='citas' ORDER BY indexname"
        )
    ).fetchall()
    print("INDICES citas:", [r[0] for r in rows3])

    # Índices recordatorios
    rows4 = db.session.execute(
        db.text(
            "SELECT indexname FROM pg_indexes WHERE tablename='recordatorios' ORDER BY indexname"
        )
    ).fetchall()
    print("INDICES recordatorios:", [r[0] for r in rows4])

    db.session.remove()
print("DIAGNOSTICO-OK")