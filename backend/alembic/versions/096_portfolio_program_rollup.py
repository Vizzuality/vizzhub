"""Roll project-anchored portfolio data up to programs (data-only, F2).

F2 makes the program the portfolio unit. Probed 2026-07-06: all 64
project-anchored profiles and all 231 project-anchored terms belong to
projects inside a program; 1 program collides (has both its own profile and
project-anchored ones inside); 8 exact duplicate (program, term) pairs.
Dual-anchor schema stays — this only moves rows. Revert path: RDS snapshot.
"""

from alembic import op

revision = "096_portfolio_program_rollup"
down_revision = "095_retire_overview_importer"
branch_labels = None
depends_on = None

ROLLUP_STATEMENTS = [
    # 1. Promote the latest project profile to program anchor where the
    #    program has no profile of its own.
    """
    UPDATE portfolio_profile pp
    SET program_id = w.program_id, project_id = NULL
    FROM (
        SELECT DISTINCT ON (p.program_id) pj.id, p.program_id
        FROM portfolio_profile pj
        JOIN projects p ON p.id = pj.project_id
        WHERE p.program_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM portfolio_profile x WHERE x.program_id = p.program_id
          )
        ORDER BY p.program_id, pj.updated_at DESC
    ) w
    WHERE pp.id = w.id
    """,
    # 2. Merge remaining project profiles into the program's profile:
    #    program value wins, NULLs filled from the latest project profile.
    """
    UPDATE portfolio_profile tgt
    SET objective = COALESCE(tgt.objective, src.objective),
        short_description = COALESCE(tgt.short_description, src.short_description),
        web_copy = COALESCE(tgt.web_copy, src.web_copy),
        impact_story = COALESCE(tgt.impact_story, src.impact_story),
        stage = COALESCE(tgt.stage, src.stage),
        main_partner = COALESCE(tgt.main_partner, src.main_partner),
        on_website = tgt.on_website OR src.on_website
    FROM (
        SELECT DISTINCT ON (p.program_id) p.program_id, pj.objective,
               pj.short_description, pj.web_copy, pj.impact_story, pj.stage,
               pj.main_partner, pj.on_website
        FROM portfolio_profile pj
        JOIN projects p ON p.id = pj.project_id
        WHERE p.program_id IS NOT NULL
        ORDER BY p.program_id, pj.updated_at DESC
    ) src
    WHERE tgt.program_id = src.program_id
    """,
    # 3. Delete the now-merged project-anchored profiles.
    """
    DELETE FROM portfolio_profile pj
    USING projects p
    WHERE pj.project_id = p.id AND p.program_id IS NOT NULL
    """,
    # 4. Demote project primaries whose program already has a primary in the
    #    same taxonomy (partial unique index would reject the re-anchor).
    """
    UPDATE entity_terms et
    SET is_primary = FALSE
    FROM projects p
    WHERE et.project_id = p.id AND p.program_id IS NOT NULL AND et.is_primary
      AND EXISTS (
          SELECT 1 FROM entity_terms e2
          WHERE e2.program_id = p.program_id
            AND e2.taxonomy_id = et.taxonomy_id AND e2.is_primary
      )
    """,
    # 5. Among sibling project primaries mapping to the same (program,
    #    taxonomy), keep the earliest, demote the rest.
    """
    UPDATE entity_terms et
    SET is_primary = FALSE
    FROM entity_terms keeper, projects p, projects p2
    WHERE et.project_id = p.id
      AND keeper.project_id = p2.id
      AND p.program_id IS NOT NULL
      AND p.program_id = p2.program_id
      AND et.taxonomy_id = keeper.taxonomy_id
      AND et.is_primary AND keeper.is_primary
      AND et.id <> keeper.id
      AND (keeper.assigned_at < et.assigned_at
           OR (keeper.assigned_at = et.assigned_at AND keeper.id < et.id))
    """,
    # 6. Drop project terms that duplicate an existing program term.
    """
    DELETE FROM entity_terms et
    USING projects p
    WHERE et.project_id = p.id AND p.program_id IS NOT NULL
      AND EXISTS (
          SELECT 1 FROM entity_terms e2
          WHERE e2.program_id = p.program_id AND e2.term_id = et.term_id
      )
    """,
    # 7. Among sibling project terms mapping to the same (program, term),
    #    keep the earliest, drop the rest.
    """
    DELETE FROM entity_terms et
    USING entity_terms keeper, projects p, projects p2
    WHERE et.project_id = p.id
      AND keeper.project_id = p2.id
      AND p.program_id IS NOT NULL
      AND p.program_id = p2.program_id
      AND et.term_id = keeper.term_id
      AND et.id <> keeper.id
      AND (keeper.assigned_at < et.assigned_at
           OR (keeper.assigned_at = et.assigned_at AND keeper.id < et.id))
    """,
    # 8. Re-anchor everything that remains.
    """
    UPDATE entity_terms et
    SET program_id = p.program_id, project_id = NULL
    FROM projects p
    WHERE et.project_id = p.id AND p.program_id IS NOT NULL
    """,
]


def upgrade() -> None:
    for statement in ROLLUP_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    # Data migration — revert path is the pre-deploy RDS snapshot.
    pass
