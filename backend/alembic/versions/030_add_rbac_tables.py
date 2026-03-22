"""Add RBAC tables (roles, user_roles) and drop users.role.

Revision ID: 030_add_rbac_tables
Revises: 029_add_project_manager
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "030_add_rbac_tables"
down_revision: str = "029_add_project_manager"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create roles table
    op.create_table(
        "roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # 2. Seed canonical roles
    op.execute("""
        INSERT INTO roles (id, name, description) VALUES
        (gen_random_uuid(), 'user', 'Default role for all users'),
        (gen_random_uuid(), 'manager', 'Tracker management (invoices, progress, periods, budgets)'),
        (gen_random_uuid(), 'admin', 'Full system access')
    """)

    # 3. Create user_roles join table
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    # 4. Populate user_roles from the legacy users.role column.
    # Every existing user receives the 'user' role.
    op.execute("""
        INSERT INTO user_roles (user_id, role_id)
        SELECT u.id, r.id
        FROM users u
        CROSS JOIN roles r
        WHERE r.name = 'user'
    """)
    # Users with role='admin' additionally receive the 'admin' role.
    op.execute("""
        INSERT INTO user_roles (user_id, role_id)
        SELECT u.id, r.id
        FROM users u
        CROSS JOIN roles r
        WHERE u.role = 'admin' AND r.name = 'admin'
    """)

    # 5. Drop legacy role column now that data has been migrated
    op.drop_column("users", "role")


def downgrade() -> None:
    # Restore the legacy role column with a safe default
    op.add_column(
        "users",
        sa.Column("role", sa.String(50), nullable=False, server_default="user"),
    )

    # Promote users who held the 'admin' role back to 'admin'
    op.execute("""
        UPDATE users u SET role = 'admin'
        WHERE EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = u.id AND r.name = 'admin'
        )
    """)

    op.drop_table("user_roles")
    op.drop_table("roles")
