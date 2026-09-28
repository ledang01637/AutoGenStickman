"""fix_refund_credits_use_active_batch

Revision ID: 06fbe57b5a4f
Revises: b8056687c55d
Create Date: 2026-05-03 13:51:18.613953

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06fbe57b5a4f'
down_revision: Union[str, Sequence[str], None] = 'b8056687c55d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS refund_credits(UUID, INTEGER, UUID)")

    op.execute("""
    CREATE FUNCTION refund_credits(
        p_user_id UUID,
        p_amount  INTEGER,
        p_job_id  UUID
    ) RETURNS VOID
    LANGUAGE plpgsql
    AS $$
    DECLARE
        v_target_batch_id UUID;
        v_balance_after   INTEGER;
    BEGIN
        IF p_amount <= 0 THEN
            RAISE EXCEPTION 'Amount phai > 0, got %', p_amount;
        END IF;

        IF EXISTS (
            SELECT 1 FROM credit_transactions
             WHERE render_job_id    = p_job_id
               AND transaction_type = 'REFUND'
        ) THEN
            RAISE NOTICE 'refund_credits idempotent skip: job_id=%', p_job_id;
            RETURN;
        END IF;

        SELECT id INTO v_target_batch_id
          FROM credit_batches
         WHERE user_id = p_user_id
           AND (expires_at IS NULL OR expires_at > NOW())
         ORDER BY
            CASE WHEN expires_at IS NULL THEN 0 ELSE 1 END,
            created_at DESC
         LIMIT 1
           FOR UPDATE;

        IF v_target_batch_id IS NULL THEN
            v_target_batch_id := gen_random_uuid();
            INSERT INTO credit_batches (
                id, user_id, total_credits, remaining_credits,
                source, expires_at, created_at, updated_at
            ) VALUES (
                v_target_batch_id, p_user_id, p_amount, p_amount,
                'REFUND', NULL, NOW(), NOW()
            );
        ELSE
            UPDATE credit_batches
               SET remaining_credits = remaining_credits + p_amount,
                   total_credits     = total_credits     + p_amount,
                   updated_at        = NOW()
             WHERE id = v_target_batch_id;
        END IF;

        SELECT COALESCE(SUM(remaining_credits), 0)
          INTO v_balance_after
          FROM credit_batches
         WHERE user_id = p_user_id
           AND remaining_credits > 0
           AND (expires_at IS NULL OR expires_at > NOW());

        INSERT INTO credit_transactions (
            id, user_id, batch_id, amount, transaction_type,
            render_job_id, balance_after, description, created_at
        ) VALUES (
            gen_random_uuid(), p_user_id, v_target_batch_id, p_amount, 'REFUND',
            p_job_id, v_balance_after, 'Refund job that bai', NOW()
        );
    END;
    $$
    """)


def downgrade() -> None:
    pass