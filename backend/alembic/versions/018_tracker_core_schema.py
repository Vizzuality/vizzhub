"""Tracker core schema: functional_areas, rates, programs, links, extend users/projects

Revision ID: 018_tracker_core
Revises: 017_unify_tokens
Create Date: 2026-03-14

New core tables for tracker module: functional_areas, rates, programs, links.
Extends users with name, functional_area_id, rate_id, dedication, active.
Extends projects with program_id, code, is_billable, currency, notes, summary.
Adds CHECK constraint on projects for end_date > start_date.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "018_tracker_core"
down_revision: Union[str, None] = "017_unify_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. functional_areas
    op.create_table(
        "functional_areas",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # 2. rates
    op.create_table(
        "rates",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("value", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # 3. programs
    op.create_table(
        "programs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # 4. Extend users
    op.add_column("users", sa.Column("name", sa.String(255), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "functional_area_id",
            UUID(as_uuid=True),
            sa.ForeignKey("functional_areas.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "rate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rates.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column("dedication", sa.Numeric(3, 2), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_index("ix_users_functional_area_id", "users", ["functional_area_id"])
    op.create_index("ix_users_rate_id", "users", ["rate_id"])

    # 5. Extend projects
    op.add_column(
        "projects",
        sa.Column(
            "program_id",
            UUID(as_uuid=True),
            sa.ForeignKey("programs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("projects", sa.Column("code", sa.String(100), nullable=True))
    op.add_column(
        "projects",
        sa.Column("is_billable", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column("projects", sa.Column("currency", sa.String(20), nullable=True))
    op.add_column("projects", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("summary", sa.Text(), nullable=True))
    op.create_index(
        "ix_projects_program_id",
        "projects",
        ["program_id"],
        postgresql_where=sa.text("program_id IS NOT NULL"),
    )
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_is_billable", "projects", ["is_billable"])
    op.create_check_constraint(
        "ck_projects_end_after_start",
        "projects",
        "end_date IS NULL OR start_date IS NULL OR end_date > start_date",
    )

    # 6. links (depends on programs and projects)
    op.create_table(
        "links",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "program_id",
            UUID(as_uuid=True),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("link_type", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "(program_id IS NOT NULL AND project_id IS NULL) "
            "OR (program_id IS NULL AND project_id IS NOT NULL)",
            name="ck_links_exactly_one_parent",
        ),
    )
    op.create_index(
        "ix_links_program_id",
        "links",
        ["program_id"],
        postgresql_where=sa.text("program_id IS NOT NULL"),
    )
    op.create_index(
        "ix_links_project_id",
        "links",
        ["project_id"],
        postgresql_where=sa.text("project_id IS NOT NULL"),
    )


def downgrade() -> None:
    # links
    op.drop_index("ix_links_project_id", table_name="links")
    op.drop_index("ix_links_program_id", table_name="links")
    op.drop_table("links")

    # projects extensions
    op.drop_constraint("ck_projects_end_after_start", "projects", type_="check")
    op.drop_index("ix_projects_is_billable", table_name="projects")
    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_program_id", table_name="projects")
    op.drop_column("projects", "summary")
    op.drop_column("projects", "notes")
    op.drop_column("projects", "currency")
    op.drop_column("projects", "is_billable")
    op.drop_column("projects", "code")
    op.drop_column("projects", "program_id")

    # users extensions
    op.drop_index("ix_users_rate_id", table_name="users")
    op.drop_index("ix_users_functional_area_id", table_name="users")
    op.drop_column("users", "active")
    op.drop_column("users", "dedication")
    op.drop_column("users", "rate_id")
    op.drop_column("users", "functional_area_id")
    op.drop_column("users", "name")

    # new tables
    op.drop_table("programs")
    op.drop_table("rates")
    op.drop_table("functional_areas")
