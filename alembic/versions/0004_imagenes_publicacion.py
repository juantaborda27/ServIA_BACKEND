"""imagenes de publicaciones almacenadas en S3

Revision ID: 0004_imagenes_publicacion
Revises: 0003_ubicacion_prestador
Create Date: 2026-11-23
"""

from alembic import op


revision = "0004_imagenes_publicacion"
down_revision = "0003_ubicacion_prestador"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS publicacion_imagenes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            publicacion_id UUID NOT NULL REFERENCES publicaciones(id) ON DELETE CASCADE,
            s3_key TEXT NOT NULL UNIQUE,
            content_type VARCHAR(50) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_publicacion_imagenes_publicacion_id
        ON publicacion_imagenes(publicacion_id)
    """)


def downgrade():
    op.drop_index(
        "ix_publicacion_imagenes_publicacion_id",
        table_name="publicacion_imagenes",
    )
    op.drop_table("publicacion_imagenes")
