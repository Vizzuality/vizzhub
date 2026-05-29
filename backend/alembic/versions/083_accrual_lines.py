"""Create accrual_lines + accrual_line_projects; key cells to lines (back-fill).

Introduces the line-based accrual model. A line is the revenue-recognition unit
(Excel row / grant / contract / manual), links to 0..N projects, and owns its
cells. This migration is the non-destructive bridge: it adds the new tables and a
``line_id`` on the existing cells, then back-fills one line per project from the
current cells (preserving every cell's frozen state). ``project_id`` is kept on
the cells as a denormalised shim during the transition; it is dropped (and the
table renamed to ``accrual_cells``) in a later cleanup migration once all
consumers read ``line_id``.

Revision ID: 083_accrual_lines
Revises: 082_accrual_resolution
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "083_accrual_lines"
down_revision: str | None = "082_accrual_resolution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_BACKFILL = """
DO $$
DECLARE
  r RECORD;
  new_id uuid;
  cmin date;
  cmax date;
  vsum numeric(14,2);
  src text;
BEGIN
  FOR r IN
    SELECT DISTINCT c.project_id AS pid, p.name AS pname, p.code AS pcode,
                    p.start_date AS pstart, p.end_date AS pend
    FROM project_accrual_cells c
    JOIN projects p ON p.id = c.project_id
  LOOP
    SELECT min(make_date(year, month, 1)),
           max(make_date(year, month, 1)),
           COALESCE(sum(amount), 0),
           CASE
             WHEN bool_or(source = 'excel') THEN 'excel'
             WHEN bool_or(source = 'team_budget') THEN 'team_budget'
             ELSE 'manual'
           END
      INTO cmin, cmax, vsum, src
      FROM project_accrual_cells
     WHERE project_id = r.pid;

    new_id := gen_random_uuid();
    INSERT INTO accrual_lines
        (id, name, source, excel_code, value_eur,
         window_start, window_end, created_at, updated_at)
      VALUES
        (new_id, r.pname, src, r.pcode, vsum,
         LEAST(r.pstart, cmin), GREATEST(r.pend, cmax), now(), now());

    INSERT INTO accrual_line_projects (line_id, project_id, created_at)
      VALUES (new_id, r.pid, now());

    UPDATE project_accrual_cells SET line_id = new_id WHERE project_id = r.pid;
  END LOOP;
END $$;
"""


def upgrade() -> None:
    op.create_table(
        "accrual_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("excel_code", sa.Text(), nullable=True),
        sa.Column(
            "import_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accrual_import_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("value_orig", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("rate", sa.Numeric(14, 6), nullable=True),
        sa.Column("value_eur", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("window_start", sa.Date(), nullable=True),
        sa.Column("window_end", sa.Date(), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_accrual_lines_excel_code", "accrual_lines", ["excel_code"])
    op.create_index("ix_accrual_lines_import_run", "accrual_lines", ["import_run_id"])
    op.execute(
        "ALTER TABLE accrual_lines ADD CONSTRAINT ck_accrual_lines_source "
        "CHECK (source IN ('excel', 'team_budget', 'manual'))"
    )
    op.execute(
        "ALTER TABLE accrual_lines ADD CONSTRAINT ck_accrual_lines_value_nonneg "
        "CHECK (value_eur >= 0)"
    )

    op.create_table(
        "accrual_line_projects",
        sa.Column(
            "line_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accrual_lines.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_accrual_line_projects_project", "accrual_line_projects", ["project_id"]
    )

    op.add_column(
        "project_accrual_cells",
        sa.Column(
            "line_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accrual_lines.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_accrual_cells_line", "project_accrual_cells", ["line_id"])

    # ``project_id`` becomes nullable: a cell on an *unlinked* line has no project.
    # The column is kept as a denormalised shim during the transition and dropped
    # in the slice-6 cleanup. The line (``line_id``) is the real owner.
    op.alter_column("project_accrual_cells", "project_id", nullable=True)

    # Drop the per-project month uniqueness: it is fundamentally incompatible with
    # the line model — a project can now carry several overlapping lines, so two
    # lines legitimately have a cell for the same (project_id, year, month).
    # Uniqueness is enforced per line instead (uq_accrual_cells_line_month).
    op.drop_constraint(
        "uq_accrual_cells_project_month", "project_accrual_cells", type_="unique"
    )

    # Back-fill: one line per project from existing cells (frozen state preserved
    # on the cells, which are re-keyed in place).
    op.execute(_BACKFILL)

    # ``line_id`` stays NULLABLE during the transition: the legacy cell writers
    # don't set it yet. It is promoted to NOT NULL in the slice-6 cleanup
    # migration once every writer keys cells to a line. The unique constraint is
    # safe meanwhile (Postgres treats NULL line_id as distinct).
    op.create_unique_constraint(
        "uq_accrual_cells_line_month",
        "project_accrual_cells",
        ["line_id", "year", "month"],
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_accrual_cells_project_month",
        "project_accrual_cells",
        ["project_id", "year", "month"],
    )
    op.drop_constraint(
        "uq_accrual_cells_line_month", "project_accrual_cells", type_="unique"
    )
    op.drop_index("ix_accrual_cells_line", table_name="project_accrual_cells")
    op.drop_column("project_accrual_cells", "line_id")
    op.drop_index("ix_accrual_line_projects_project", table_name="accrual_line_projects")
    op.drop_table("accrual_line_projects")
    op.drop_index("ix_accrual_lines_import_run", table_name="accrual_lines")
    op.drop_index("ix_accrual_lines_excel_code", table_name="accrual_lines")
    op.drop_table("accrual_lines")
