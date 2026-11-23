"""Ubicación base privada del prestador."""

from alembic import op

revision = "0003_ubicacion_prestador"
down_revision = "0002_finalizacion_dos_pasos"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE prestadores
        ADD COLUMN IF NOT EXISTS base_latitud DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS base_longitud DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS base_direccion TEXT
    """)


def downgrade():
    op.drop_column("prestadores", "base_direccion")
    op.drop_column("prestadores", "base_longitud")
    op.drop_column("prestadores", "base_latitud")
