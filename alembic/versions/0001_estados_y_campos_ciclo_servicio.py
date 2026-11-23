"""estados oficiales y campos de ciclo de servicio

Revision ID: 0001_ciclo_servicio
Revises:
Create Date: 2026-11-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_ciclo_servicio"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL requiere autocommit para ALTER TYPE ... ADD VALUE
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE estado_publicacion ADD VALUE IF NOT EXISTS 'en_disputa'")
        op.execute("ALTER TYPE estado_postulacion ADD VALUE IF NOT EXISTS 'retirada'")

    # Publicaciones: nuevos campos de ciclo de vida
    op.execute("ALTER TABLE publicaciones ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ")
    op.execute("ALTER TABLE publicaciones ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE publicaciones ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ")
    op.execute("ALTER TABLE publicaciones ADD COLUMN IF NOT EXISTS cancelled_by UUID REFERENCES usuarios(id)")
    op.execute("ALTER TABLE publicaciones ADD COLUMN IF NOT EXISTS cancellation_reason TEXT")

    # Postulaciones: fecha de retirada
    op.execute("ALTER TABLE postulaciones ADD COLUMN IF NOT EXISTS retirada_at TIMESTAMPTZ")

    # Conversaciones: timestamps de creación, cierre y retención
    op.execute("ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()")
    op.execute("ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS delete_after TIMESTAMPTZ")

    # Índices
    op.execute("CREATE INDEX IF NOT EXISTS idx_publicaciones_estado ON publicaciones(estado)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_postulaciones_pub_estado ON postulaciones(publicacion_id, estado)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mensajes_conversacion ON mensajes(id_conversacion, fecha_hora)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_notificaciones_usuario ON notificaciones(usuario_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_conversaciones_delete_after ON conversaciones(estado, delete_after)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_conversaciones_delete_after")
    op.execute("DROP INDEX IF EXISTS idx_notificaciones_usuario")
    op.execute("DROP INDEX IF EXISTS idx_mensajes_conversacion")
    op.execute("DROP INDEX IF EXISTS idx_postulaciones_pub_estado")
    op.execute("DROP INDEX IF EXISTS idx_publicaciones_estado")

    op.execute("ALTER TABLE conversaciones DROP COLUMN IF EXISTS delete_after")
    op.execute("ALTER TABLE conversaciones DROP COLUMN IF EXISTS closed_at")
    op.execute("ALTER TABLE conversaciones DROP COLUMN IF EXISTS created_at")

    op.execute("ALTER TABLE postulaciones DROP COLUMN IF EXISTS retirada_at")

    op.execute("ALTER TABLE publicaciones DROP COLUMN IF EXISTS cancellation_reason")
    op.execute("ALTER TABLE publicaciones DROP COLUMN IF EXISTS cancelled_by")
    op.execute("ALTER TABLE publicaciones DROP COLUMN IF EXISTS cancelled_at")
    op.execute("ALTER TABLE publicaciones DROP COLUMN IF EXISTS completed_at")
    op.execute("ALTER TABLE publicaciones DROP COLUMN IF EXISTS started_at")
