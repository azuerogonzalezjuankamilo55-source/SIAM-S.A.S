"""panel de configuración centralizado

Revision ID: b5d7e9a2c1f6
Revises: a8c4d2f6e1b9
Create Date: 2026-08-14 21:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# Identificadores de Alembic
revision = "b5d7e9a2c1f6"
down_revision = "a8c4d2f6e1b9"
branch_labels = None
depends_on = None


def upgrade():
    # Configuración de citas
    op.add_column(
        "configuracion_taller",
        sa.Column(
            "citas_intervalo_min",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
        ),
    )

    op.add_column(
        "configuracion_taller",
        sa.Column(
            "citas_min_anticipacion_horas",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.add_column(
        "configuracion_taller",
        sa.Column(
            "citas_cancelar_limite_horas",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # Notificaciones
    op.add_column(
        "configuracion_taller",
        sa.Column(
            "notif_email",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    op.add_column(
        "configuracion_taller",
        sa.Column(
            "notif_sms",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.add_column(
        "configuracion_taller",
        sa.Column(
            "notif_whatsapp",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.add_column(
        "configuracion_taller",
        sa.Column(
            "notif_recordatorio_dias",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("7"),
        ),
    )

    # Inteligencia artificial
    op.add_column(
        "configuracion_taller",
        sa.Column(
            "ia_activado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade():
    op.drop_column(
        "configuracion_taller",
        "ia_activado",
    )

    op.drop_column(
        "configuracion_taller",
        "notif_recordatorio_dias",
    )

    op.drop_column(
        "configuracion_taller",
        "notif_whatsapp",
    )

    op.drop_column(
        "configuracion_taller",
        "notif_sms",
    )

    op.drop_column(
        "configuracion_taller",
        "notif_email",
    )

    op.drop_column(
        "configuracion_taller",
        "citas_cancelar_limite_horas",
    )

    op.drop_column(
        "configuracion_taller",
        "citas_min_anticipacion_horas",
    )

    op.drop_column(
        "configuracion_taller",
        "citas_intervalo_min",
    )

