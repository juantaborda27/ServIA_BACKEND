"""finalizacion del servicio en dos pasos

Revision ID: 0002_finalizacion_dos_pasos
Revises: 0001_ciclo_servicio
Create Date: 2026-11-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_finalizacion_dos_pasos"
down_revision: Union[str, Sequence[str], None] = "0001_ciclo_servicio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE estado_publicacion "
            "ADD VALUE IF NOT EXISTS 'pendiente_confirmacion'"
        )
    op.execute(
        "ALTER TABLE publicaciones ADD COLUMN IF NOT EXISTS "
        "completion_requested_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE publicaciones DROP COLUMN IF EXISTS completion_requested_at"
    )
    # PostgreSQL no permite eliminar un valor ENUM de forma segura sin recrear el tipo.
