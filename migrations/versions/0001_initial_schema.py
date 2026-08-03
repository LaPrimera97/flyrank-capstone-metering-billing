"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("api_key", sa.String(), nullable=False, unique=True),
        sa.Column("plan", sa.String(), nullable=False, server_default="free"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("stripe_customer_id", sa.String(), unique=True, nullable=True),
        sa.Column("stripe_subscription_id", sa.String(), unique=True, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "usage_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("usage_type", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("token_breakdown", sa.JSON(), nullable=True),
        sa.Column("cost_micros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("billing_period", sa.String(), nullable=False),
        sa.Column("response_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_tenant_idempotency_key"),
    )
    op.create_index("ix_usage_events_tenant_period", "usage_events", ["tenant_id", "billing_period"])

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("stripe_event_id", sa.String(), nullable=False, unique=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_index("ix_usage_events_tenant_period", table_name="usage_events")
    op.drop_table("usage_events")
    op.drop_table("tenants")
