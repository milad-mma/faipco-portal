"""Per-bank digit lengths; prior values and validation defaults are preserved."""
from alembic import op
import sqlalchemy as sa

revision = "157"
down_revision = "156"
branch_labels = None
depends_on = None

fields = (("account_number", 20, 32), ("sheba", 26, 34), ("card_number", 16, 32))


def upgrade():
    for field, _, size in fields:
        op.add_column("bank_definitions", sa.Column(field + "_digits", sa.Integer()))
        op.alter_column("employee_bank_accounts", field, type_=sa.String(size))


def downgrade():
    for field, size, _ in fields:
        # PostgreSQL can truncate on an explicit varchar cast; refuse a lossy downgrade.
        too_long = op.get_bind().scalar(sa.text(
            f"SELECT EXISTS (SELECT 1 FROM employee_bank_accounts WHERE length({field}) > :size)"
        ), {"size": size})
        if too_long:
            raise RuntimeError(f"Cannot downgrade: stored {field} exceeds the former length")
    for field, size, _ in fields:
        op.alter_column("employee_bank_accounts", field, type_=sa.String(size))
        op.drop_column("bank_definitions", field + "_digits")
