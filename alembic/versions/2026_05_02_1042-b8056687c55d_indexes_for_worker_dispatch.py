"""indexes_for_worker_dispatch

Revision ID: b8056687c55d
Revises: 9a4f0148956d
Create Date: 2026-05-02 10:42:13.731721

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8056687c55d'
down_revision: Union[str, Sequence[str], None] = '9a4f0148956d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_render_jobs_dispatch
        ON render_jobs (status, priority DESC, created_at ASC)
        WHERE deleted_at IS NULL
          AND status IN ('PENDING', 'PROCESSING', 'FAILED');
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_render_jobs_locked_at
        ON render_jobs (locked_at)
        WHERE status = 'PROCESSING' AND deleted_at IS NULL;
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_credit_batches_user_active
        ON credit_batches (user_id, expires_at NULLS LAST, created_at)
        WHERE remaining_credits > 0;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_credit_batches_user_active")
    op.execute("DROP INDEX IF EXISTS ix_render_jobs_locked_at")
    op.execute("DROP INDEX IF EXISTS ix_render_jobs_dispatch")