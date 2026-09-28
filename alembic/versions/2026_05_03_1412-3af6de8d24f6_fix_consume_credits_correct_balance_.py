"""fix_consume_credits_correct_balance_after

Revision ID: 3af6de8d24f6
Revises: 06fbe57b5a4f
Create Date: 2026-05-03 14:12:31.330128

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3af6de8d24f6'
down_revision: Union[str, Sequence[str], None] = '06fbe57b5a4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
