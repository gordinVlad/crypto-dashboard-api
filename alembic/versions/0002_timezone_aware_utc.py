"""Make stored datetime columns timezone-aware UTC.

Revision ID: 0002_timezone_aware_utc
Revises: 0001_initial
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_timezone_aware_utc"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DATETIME_COLUMNS = {
    "users": ("created_at",),
    "cryptocurrencies": ("last_updated_at",),
    "price_history": ("timestamp",),
    "watchlist_items": ("added_at",),
}


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        return

    inspector = sa.inspect(connection)
    for table_name, column_names in _DATETIME_COLUMNS.items():
        columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        for column_name in column_names:
            if columns[column_name]["type"].timezone:
                continue
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(),
                type_=sa.DateTime(timezone=True),
                postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
            )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        return

    inspector = sa.inspect(connection)
    for table_name, column_names in _DATETIME_COLUMNS.items():
        columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        for column_name in column_names:
            if not columns[column_name]["type"].timezone:
                continue
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(timezone=True),
                type_=sa.DateTime(),
                postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
            )
