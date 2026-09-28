"""add_render_queued_status

Revision ID: 131873dd9865
Revises: f687e35c8ae9
Create Date: 2026-06-13 04:18:46.899103

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '131873dd9865'
down_revision: Union[str, Sequence[str], None] = 'f687e35c8ae9'

def upgrade():
    # Postgres không cho ALTER TYPE ... ADD VALUE trong transaction block (trước PG12)
    # PG12+ cho phép nhưng phải tách autocommit
    op.execute("COMMIT")  # kết thúc transaction hiện tại của Alembic
    op.execute("ALTER TYPE render_job_status ADD VALUE IF NOT EXISTS 'RENDER_QUEUED'")

def downgrade():
    # Postgres không hỗ trợ DROP VALUE từ enum — downgrade là no-op
    pass
