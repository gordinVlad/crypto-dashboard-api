"""Create the initial application schema.

Revision ID: 0001_initial
Revises:
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cryptocurrencies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("external_provider_id", sa.String(), nullable=False),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("market_cap", sa.Float(), nullable=True),
        sa.Column("price_change_percentage_24h", sa.Float(), nullable=True),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cryptocurrencies_external_provider_id",
        "cryptocurrencies",
        ["external_provider_id"],
        unique=True,
    )
    op.create_index("ix_cryptocurrencies_id", "cryptocurrencies", ["id"])
    op.create_index("ix_cryptocurrencies_symbol", "cryptocurrencies", ["symbol"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id", "users", ["id"])

    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cryptocurrency_id", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cryptocurrency_id"], ["cryptocurrencies.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cryptocurrency_id", "timestamp", name="uq_coin_history_timestamp"
        ),
    )
    op.create_index(
        "ix_price_history_cryptocurrency_id",
        "price_history",
        ["cryptocurrency_id"],
    )
    op.create_index("ix_price_history_id", "price_history", ["id"])
    op.create_index("ix_price_history_timestamp", "price_history", ["timestamp"])

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("cryptocurrency_id", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["cryptocurrency_id"], ["cryptocurrencies.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "cryptocurrency_id", name="uq_user_coin_watchlist"
        ),
    )
    op.create_index(
        "ix_watchlist_items_cryptocurrency_id",
        "watchlist_items",
        ["cryptocurrency_id"],
    )
    op.create_index("ix_watchlist_items_id", "watchlist_items", ["id"])
    op.create_index("ix_watchlist_items_user_id", "watchlist_items", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_watchlist_items_user_id", table_name="watchlist_items")
    op.drop_index("ix_watchlist_items_id", table_name="watchlist_items")
    op.drop_index("ix_watchlist_items_cryptocurrency_id", table_name="watchlist_items")
    op.drop_table("watchlist_items")
    op.drop_index("ix_price_history_timestamp", table_name="price_history")
    op.drop_index("ix_price_history_id", table_name="price_history")
    op.drop_index("ix_price_history_cryptocurrency_id", table_name="price_history")
    op.drop_table("price_history")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_cryptocurrencies_symbol", table_name="cryptocurrencies")
    op.drop_index("ix_cryptocurrencies_id", table_name="cryptocurrencies")
    op.drop_index(
        "ix_cryptocurrencies_external_provider_id", table_name="cryptocurrencies"
    )
    op.drop_table("cryptocurrencies")
