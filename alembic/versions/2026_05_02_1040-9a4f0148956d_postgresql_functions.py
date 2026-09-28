"""postgresql_functions

Revision ID: 9a4f0148956d
Revises: a82420ec4a56
Create Date: 2026-05-02 10:40:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a4f0148956d'
down_revision: Union[str, None] = 'a82420ec4a56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute("""
    CREATE OR REPLACE FUNCTION consume_credits(
        p_user_id UUID,
        p_amount  INTEGER,
        p_job_id  UUID
    ) RETURNS BOOLEAN
    LANGUAGE plpgsql
    AS $$
    DECLARE
        v_total_remaining INTEGER;
        v_to_consume      INTEGER;
        v_taken           INTEGER;
        v_balance_after   INTEGER;
        v_batch           RECORD;
    BEGIN
        IF p_amount <= 0 THEN
            RAISE EXCEPTION 'Amount phải > 0, got %', p_amount;
        END IF;

        -- Lock tất cả batch còn credit trước (row-level lock, KHÔNG aggregate)
        PERFORM 1
          FROM credit_batches
         WHERE user_id = p_user_id
           AND remaining_credits > 0
           AND (expires_at IS NULL OR expires_at > NOW())
         FOR UPDATE;

        -- Tính tổng sau khi đã lock
        SELECT COALESCE(SUM(remaining_credits), 0)
          INTO v_total_remaining
          FROM credit_batches
         WHERE user_id = p_user_id
           AND remaining_credits > 0
           AND (expires_at IS NULL OR expires_at > NOW());

        IF v_total_remaining < p_amount THEN
            RETURN FALSE;
        END IF;

        v_to_consume := p_amount;

        FOR v_batch IN
            SELECT id, remaining_credits
              FROM credit_batches
             WHERE user_id = p_user_id
               AND remaining_credits > 0
               AND (expires_at IS NULL OR expires_at > NOW())
             ORDER BY
                CASE WHEN expires_at IS NULL THEN 1 ELSE 0 END,
                expires_at ASC NULLS LAST,
                created_at ASC
        LOOP
            EXIT WHEN v_to_consume <= 0;

            v_taken := LEAST(v_batch.remaining_credits, v_to_consume);

            UPDATE credit_batches
               SET remaining_credits = remaining_credits - v_taken,
                   updated_at        = NOW()
             WHERE id = v_batch.id;

            v_balance_after := v_total_remaining - (p_amount - v_to_consume) - v_taken;

            INSERT INTO credit_transactions (
                id, user_id, batch_id, amount, transaction_type,
                render_job_id, balance_after, description, created_at
            ) VALUES (
                gen_random_uuid(), p_user_id, v_batch.id, -v_taken, 'CONSUME',
                p_job_id, v_balance_after, 'Job render consume', NOW()
            );

            v_to_consume := v_to_consume - v_taken;
        END LOOP;

        RETURN TRUE;

    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE 'consume_credits idempotent skip: job_id=%', p_job_id;
            RETURN TRUE;
    END;
    $$
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION refund_credits(
        p_user_id UUID,
        p_amount  INTEGER,
        p_job_id  UUID
    ) RETURNS VOID
    LANGUAGE plpgsql
    AS $$
    DECLARE
        v_consume         RECORD;
        v_balance_after   INTEGER;
    BEGIN
        IF p_amount <= 0 THEN
            RAISE EXCEPTION 'Amount phải > 0, got %', p_amount;
        END IF;

        FOR v_consume IN
            SELECT batch_id, amount
              FROM credit_transactions
             WHERE render_job_id    = p_job_id
               AND user_id          = p_user_id
               AND transaction_type = 'CONSUME'
               AND batch_id IS NOT NULL
        LOOP
            UPDATE credit_batches
               SET remaining_credits = LEAST(
                       remaining_credits + ABS(v_consume.amount),
                       total_credits
                   ),
                   updated_at = NOW()
             WHERE id = v_consume.batch_id;
        END LOOP;

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
            gen_random_uuid(), p_user_id, NULL, p_amount, 'REFUND',
            p_job_id, v_balance_after, 'Refund job thất bại', NOW()
        );
    END;
    $$
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS global_cap_state (
        id              SMALLINT     PRIMARY KEY DEFAULT 1,
        date_bucket     DATE         NOT NULL,
        current_count   INTEGER      NOT NULL DEFAULT 0,
        max_per_day     INTEGER      NOT NULL DEFAULT 1000,
        updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        CONSTRAINT chk_singleton CHECK (id = 1)
    )
    """)

    op.execute("""
    INSERT INTO global_cap_state (id, date_bucket, current_count, max_per_day)
    VALUES (1, CURRENT_DATE, 0, 1000)
    ON CONFLICT (id) DO NOTHING
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION check_and_increment_global_cap()
    RETURNS BOOLEAN
    LANGUAGE plpgsql
    AS $$
    DECLARE
        v_state RECORD;
    BEGIN
        SELECT * INTO v_state
          FROM global_cap_state
         WHERE id = 1
         FOR UPDATE;

        IF v_state.date_bucket < CURRENT_DATE THEN
            UPDATE global_cap_state
               SET date_bucket   = CURRENT_DATE,
                   current_count = 0,
                   updated_at    = NOW()
             WHERE id = 1;
            v_state.current_count := 0;
        END IF;

        IF v_state.current_count >= v_state.max_per_day THEN
            RETURN FALSE;
        END IF;

        UPDATE global_cap_state
           SET current_count = current_count + 1,
               updated_at    = NOW()
         WHERE id = 1;

        RETURN TRUE;
    END;
    $$
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS check_and_increment_global_cap()")
    op.execute("DROP TABLE IF EXISTS global_cap_state")
    op.execute("DROP FUNCTION IF EXISTS refund_credits(UUID, INTEGER, UUID)")
    op.execute("DROP FUNCTION IF EXISTS consume_credits(UUID, INTEGER, UUID)")