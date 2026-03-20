"""Import legacy VizzTracker data into vizzhub tracker module.

Reads from legacy DB (vizz_trackr_development), writes to vizzhub DB (scorecard).
Idempotent: can be re-run safely (uses ON CONFLICT DO NOTHING / upserts).

Usage:
    cd backend
    python scripts/import_vizztracker.py [--legacy-db URL] [--target-db URL] [--dry-run]

Both --legacy-db and --target-db are required.
"""

import argparse
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import psycopg2
import psycopg2.extras

psycopg2.extras.register_uuid()


def connect(url: str):
    return psycopg2.connect(url)


def clean_tracker_data(target):
    """Remove previously imported tracker data for idempotent re-import.

    Deletes in reverse dependency order. Preserves pre-existing vizzhub
    projects/users that were not imported from tracker.
    """
    cur = target.cursor()
    tables = [
        "links",
        "report_parts",
        "progress_reports",
        "non_staff_costs",
        "reports",
        "invoices",
        "budget_lines",
        "tracker_project_settings",
        "reporting_periods",
    ]
    for table in tables:
        cur.execute(f"DELETE FROM {table}")
        print(f"    cleaned {table}: {cur.rowcount} rows")

    # Clean programs (CASCADE will SET NULL on projects.program_id)
    cur.execute("DELETE FROM programs")
    print(f"    cleaned programs: {cur.rowcount} rows")

    cur.close()


def build_mappings(legacy, target):
    """Build all mapping tables (legacy bigint ID -> new UUID)."""
    maps = {}

    # functional_areas (from legacy roles)
    maps['functional_areas'] = import_functional_areas(legacy, target)
    print(f"  functional_areas: {len(maps['functional_areas'])} mapped")

    # rates
    maps['rates'] = import_rates(legacy, target)
    print(f"  rates: {len(maps['rates'])} mapped")

    # programs (from legacy projects with 2+ contracts)
    maps['programs'] = import_programs(legacy, target)
    print(f"  programs: {len(maps['programs'])} mapped")

    # users
    maps['users'] = import_users(legacy, target, maps)
    print(f"  users: {len(maps['users'])} mapped")

    # projects (from legacy contracts)
    maps['projects'] = import_projects(legacy, target, maps)
    print(f"  projects: {len(maps['projects'])} mapped")

    # tracker_project_settings
    count = import_tracker_project_settings(legacy, target, maps)
    print(f"  tracker_project_settings: {count} imported")

    # reporting_periods
    maps['reporting_periods'] = import_reporting_periods(legacy, target)
    print(f"  reporting_periods: {len(maps['reporting_periods'])} mapped")

    # budget_lines
    count = import_budget_lines(legacy, target, maps)
    print(f"  budget_lines: {count} imported")

    # invoices
    count = import_invoices(legacy, target, maps)
    print(f"  invoices: {count} imported")

    # non_staff_costs
    count = import_non_staff_costs(legacy, target, maps)
    print(f"  non_staff_costs: {count} imported")

    # reports
    maps['reports'] = import_reports(legacy, target, maps)
    print(f"  reports: {len(maps['reports'])} mapped")

    # report_parts
    count = import_report_parts(legacy, target, maps)
    print(f"  report_parts: {count} imported")

    # progress_reports
    count = import_progress_reports(legacy, target, maps)
    print(f"  progress_reports: {count} imported")

    # links (from legacy project_links)
    count = import_links(legacy, target, maps)
    print(f"  links: {count} imported")

    return maps


def import_functional_areas(legacy, target):
    """Import legacy roles -> functional_areas."""
    mapping = {}
    cur_l = legacy.cursor()
    cur_t = target.cursor()

    cur_l.execute("SELECT id, name, created_at FROM roles ORDER BY id")
    for row in cur_l.fetchall():
        legacy_id, name, created_at = row
        new_id = uuid.uuid4()
        cur_t.execute(
            "INSERT INTO functional_areas (id, name, created_at) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
            "RETURNING id",
            (new_id, name, created_at),
        )
        actual_id = cur_t.fetchone()[0]
        mapping[legacy_id] = actual_id

    cur_l.close()
    cur_t.close()
    return mapping


def import_rates(legacy, target):
    """Import legacy rates."""
    mapping = {}
    cur_l = legacy.cursor()
    cur_t = target.cursor()

    cur_l.execute("SELECT id, code, value, created_at FROM rates ORDER BY id")
    for row in cur_l.fetchall():
        legacy_id, code, value, created_at = row
        new_id = uuid.uuid4()
        cur_t.execute(
            "INSERT INTO rates (id, code, value, created_at) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (code) DO UPDATE SET code = EXCLUDED.code "
            "RETURNING id",
            (new_id, code, Decimal(str(value)), created_at),
        )
        actual_id = cur_t.fetchone()[0]
        mapping[legacy_id] = actual_id

    cur_l.close()
    cur_t.close()
    return mapping


def import_programs(legacy, target):
    """Import legacy projects with 2+ contracts as programs."""
    mapping = {}
    cur_l = legacy.cursor()
    cur_t = target.cursor()

    cur_l.execute("""
        SELECT p.id, p.name, p.created_at, COUNT(c.id) AS contract_count
        FROM projects p
        LEFT JOIN contracts c ON c.project_id = p.id
        GROUP BY p.id
        HAVING COUNT(c.id) >= 2
        ORDER BY p.id
    """)
    for row in cur_l.fetchall():
        legacy_id, name, created_at, _ = row
        new_id = uuid.uuid4()
        cur_t.execute(
            "INSERT INTO programs (id, name, created_at) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
            "RETURNING id",
            (new_id, name, created_at),
        )
        actual_id = cur_t.fetchone()[0]
        mapping[legacy_id] = actual_id

    cur_l.close()
    cur_t.close()
    return mapping


def import_users(legacy, target, maps):
    """Import legacy users, matching by email."""
    mapping = {}
    cur_l = legacy.cursor()
    cur_t = target.cursor()

    cur_l.execute(
        "SELECT id, email, name, role_id, rate_id, dedication, active, created_at "
        "FROM users ORDER BY id"
    )
    for row in cur_l.fetchall():
        legacy_id, email, name, role_id, rate_id, dedication, active, created_at = row

        fa_id = maps['functional_areas'].get(role_id)
        r_id = maps['rates'].get(rate_id)
        ded = Decimal(str(dedication)) if dedication is not None else None

        # Check if user exists in target
        cur_t.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing = cur_t.fetchone()

        if existing:
            target_id = existing[0]
            cur_t.execute(
                "UPDATE users SET name = %s, functional_area_id = %s, "
                "rate_id = %s, dedication = %s, active = %s "
                "WHERE id = %s",
                (name, fa_id, r_id, ded, active, target_id),
            )
        else:
            target_id = uuid.uuid4()
            cur_t.execute(
                "INSERT INTO users (id, email, name, functional_area_id, rate_id, "
                "dedication, active, role, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, 'user', %s)",
                (target_id, email, name, fa_id, r_id, ded, active, created_at),
            )

        mapping[legacy_id] = target_id

    cur_l.close()
    cur_t.close()
    return mapping


PRODUCTION_OVERRIDES = {
    'AGORA Paraguay': 'Agora Paraguay WB',
    'Amazonia360 - Beta version 2': 'AmazoniaForever360+',
    'FHWPC Implementation phase': 'FHWPC',
    'Forest Innovation Platform - Phase I': 'Forest Innovation Platform (FIP)',
    'GMW Phase 8': 'Global Mangrove Watch Phase 8',
    'HE MIRACA': 'Miraca',
    'ICIMOD Web Overhaul (Phase 2)': 'ICIMOD',
}


def _sanitize_date(d):
    """Return None for dates before year 2000."""
    if d and d.year < 2000:
        return None
    return d


def _find_existing_project(cur_t, name):
    """Find an existing project by name (with production override)."""
    prod_name = PRODUCTION_OVERRIDES.get(name)
    lookup_name = prod_name if prod_name else name
    cur_t.execute("SELECT id FROM projects WHERE TRIM(name) = %s", (lookup_name,))
    existing = cur_t.fetchone()
    return existing, prod_name


def _update_existing_project(cur_t, target_id, prod_name, program_id, code,
                             is_billable, currency, notes, summary,
                             start_date, end_date, status, finished_at):
    """Update an existing project (production override or regular match)."""
    if prod_name:
        cur_t.execute(
            "UPDATE projects SET program_id = %s, code = %s, "
            "is_billable = %s, currency = %s, notes = %s, summary = %s "
            "WHERE id = %s",
            (program_id, code, is_billable, currency, notes, summary,
             target_id),
        )
    else:
        cur_t.execute(
            "UPDATE projects SET program_id = %s, code = %s, is_billable = %s, "
            "currency = %s, notes = %s, summary = %s, start_date = %s, "
            "end_date = %s, status = %s, finished_at = %s "
            "WHERE id = %s",
            (program_id, code, is_billable, currency, notes, summary,
             start_date, end_date, status, finished_at, target_id),
        )


def _insert_new_project(cur_t, name, program_id, code, is_billable, currency,
                        notes, summary, start_date, end_date, status,
                        finished_at, created_at):
    """Insert a new project and return its UUID."""
    target_id = uuid.uuid4()
    cur_t.execute(
        "INSERT INTO projects (id, name, program_id, code, is_billable, "
        "currency, notes, summary, start_date, end_date, status, "
        "finished_at, created_at, has_scorecard, has_dependabot_alerts, "
        "has_budget_alerts) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
        "false, false, false)",
        (target_id, name, program_id, code, is_billable, currency,
         notes, summary, start_date, end_date, status, finished_at,
         created_at),
    )
    return target_id


def import_projects(legacy, target, maps):
    """Import legacy contracts as projects."""
    mapping = {}
    cur_l = legacy.cursor()
    cur_t = target.cursor()

    cur_l.execute("""
        SELECT c.id, c.name, c.code, c.start_date, c.end_date, c.aasm_state,
               c.notes, c.summary, c.created_at,
               p.id AS legacy_project_id, p.is_billable
        FROM contracts c
        JOIN projects p ON p.id = c.project_id
        ORDER BY c.id
    """)
    for row in cur_l.fetchall():
        (legacy_id, name, code, start_date, end_date, aasm_state,
         notes, summary, created_at, legacy_proj_id, is_billable) = row

        name = name.strip() if name else name
        end_date = _sanitize_date(end_date)
        start_date = _sanitize_date(start_date)
        program_id = maps['programs'].get(legacy_proj_id)
        status = "finished" if aasm_state == "finished" else "live"
        finished_at = end_date if status == "finished" else None

        cur_l.execute(
            "SELECT currency FROM invoices WHERE contract_id = %s "
            "AND currency IS NOT NULL LIMIT 1",
            (legacy_id,),
        )
        currency_row = cur_l.fetchone()
        currency = currency_row[0] if currency_row else None

        existing, prod_name = _find_existing_project(cur_t, name)

        if existing:
            target_id = existing[0]
            _update_existing_project(
                cur_t, target_id, prod_name, program_id, code,
                is_billable, currency, notes, summary,
                start_date, end_date, status, finished_at,
            )
        else:
            target_id = _insert_new_project(
                cur_t, name, program_id, code, is_billable, currency,
                notes, summary, start_date, end_date, status,
                finished_at, created_at,
            )

        mapping[legacy_id] = target_id

    cur_l.close()
    cur_t.close()
    return mapping


def import_tracker_project_settings(legacy, target, maps):
    """Import contract rate as tracker_project_settings, budget goes to projects."""
    cur_l = legacy.cursor()
    cur_t = target.cursor()
    count = 0

    cur_l.execute(
        "SELECT id, budget, contract_rate FROM contracts ORDER BY id"
    )
    for row in cur_l.fetchall():
        legacy_id, budget, contract_rate = row
        project_id = maps['projects'].get(legacy_id)
        if not project_id:
            continue

        budget_dec = Decimal(str(budget)) if budget is not None else None
        rate_dec = Decimal(str(contract_rate)) if contract_rate else Decimal("175.00")

        # Budget lives on projects table
        if budget_dec is not None:
            cur_t.execute(
                "UPDATE projects SET budget = %s WHERE id = %s",
                (budget_dec, project_id),
            )

        cur_t.execute(
            "INSERT INTO tracker_project_settings (id, project_id, contract_rate) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (project_id) DO UPDATE "
            "SET contract_rate = EXCLUDED.contract_rate",
            (uuid.uuid4(), project_id, rate_dec),
        )
        count += 1

    cur_l.close()
    cur_t.close()
    return count


def import_reporting_periods(legacy, target):
    """Import reporting_periods."""
    mapping = {}
    cur_l = legacy.cursor()
    cur_t = target.cursor()

    cur_l.execute(
        "SELECT id, date, base_rate, aasm_state, created_at "
        "FROM reporting_periods ORDER BY id"
    )
    for row in cur_l.fetchall():
        legacy_id, date_val, base_rate, aasm_state, created_at = row

        rate_dec = Decimal(str(base_rate)) if base_rate else Decimal("175.00")
        status = aasm_state or "unstarted"

        new_id = uuid.uuid4()
        cur_t.execute(
            "INSERT INTO reporting_periods (id, date, base_rate, status, created_at) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (date) DO UPDATE SET date = EXCLUDED.date "
            "RETURNING id",
            (new_id, date_val, rate_dec, status, created_at),
        )
        actual_id = cur_t.fetchone()[0]
        mapping[legacy_id] = actual_id

    cur_l.close()
    cur_t.close()
    return mapping


def pct_to_decimal(value):
    """Convert 0-100 percentage to 0-1 decimal."""
    if value is None:
        return None
    return Decimal(str(value)) / Decimal("100")


def float_to_decimal(value, precision=2):
    """Convert float to Decimal with given precision."""
    if value is None:
        return None
    return round(Decimal(str(value)), precision)


def import_budget_lines(legacy, target, maps):
    """Import budget_lines."""
    cur_l = legacy.cursor()
    cur_t = target.cursor()
    count = 0

    cur_l.execute(
        "SELECT id, contract_id, role_id, days, adjusted_days, percentage, "
        "details, created_at FROM budget_lines ORDER BY id"
    )
    for row in cur_l.fetchall():
        (legacy_id, contract_id, role_id, days, adjusted_days,
         percentage, details, created_at) = row

        project_id = maps['projects'].get(contract_id)
        if not project_id:
            continue

        fa_id = maps['functional_areas'].get(role_id)
        migrated_days = float_to_decimal(adjusted_days) if adjusted_days is not None else days

        cur_t.execute(
            "INSERT INTO budget_lines (id, project_id, functional_area_id, days, "
            "percentage, details, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (uuid.uuid4(), project_id, fa_id, migrated_days,
             pct_to_decimal(percentage), details, created_at),
        )
        count += 1

    cur_l.close()
    cur_t.close()
    return count


def import_invoices(legacy, target, maps):
    """Import invoices."""
    cur_l = legacy.cursor()
    cur_t = target.cursor()
    count = 0

    cur_l.execute(
        "SELECT id, contract_id, code, amount, due_date, extended_date, "
        "invoiced_on, milestone, observations, aasm_state "
        "FROM invoices ORDER BY id"
    )
    for row in cur_l.fetchall():
        (legacy_id, contract_id, code, amount, due_date, extended_date,
         invoiced_on, milestone, observations, aasm_state) = row

        project_id = maps['projects'].get(contract_id)
        if not project_id:
            continue

        status = aasm_state or "scheduled"

        cur_t.execute(
            "INSERT INTO invoices (id, project_id, code, amount, due_date, "
            "extended_date, invoiced_on, milestone, observations, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (uuid.uuid4(), project_id, code, float_to_decimal(amount),
             due_date, extended_date, invoiced_on,
             milestone or "N/A", observations, status),
        )
        count += 1

    cur_l.close()
    cur_t.close()
    return count


def import_non_staff_costs(legacy, target, maps):
    """Import non_staff_costs."""
    cur_l = legacy.cursor()
    cur_t = target.cursor()
    count = 0

    cur_l.execute(
        "SELECT id, contract_id, reporting_period_id, cost, cost_type, "
        "details, created_at FROM non_staff_costs ORDER BY id"
    )
    for row in cur_l.fetchall():
        (legacy_id, contract_id, rp_id, cost, cost_type,
         details, created_at) = row

        project_id = maps['projects'].get(contract_id)
        period_id = maps['reporting_periods'].get(rp_id)
        if not project_id or not period_id:
            continue

        cur_t.execute(
            "INSERT INTO non_staff_costs (id, project_id, reporting_period_id, "
            "cost, cost_type, details, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (uuid.uuid4(), project_id, period_id, float_to_decimal(cost),
             cost_type, details, created_at),
        )
        count += 1

    cur_l.close()
    cur_t.close()
    return count


def import_reports(legacy, target, maps):
    """Import reports (one per user per period, skip duplicates)."""
    mapping = {}
    cur_l = legacy.cursor()
    cur_t = target.cursor()
    seen = set()

    cur_l.execute(
        "SELECT r.id, r.user_id, r.reporting_period_id, r.estimated, r.created_at, "
        "(SELECT COUNT(*) FROM report_parts WHERE report_id = r.id) AS parts_count "
        "FROM reports r ORDER BY r.id"
    )
    for row in cur_l.fetchall():
        legacy_id, user_id, rp_id, estimated, created_at, parts_count = row

        user_uuid = maps['users'].get(user_id)
        period_uuid = maps['reporting_periods'].get(rp_id)
        if not user_uuid or not period_uuid:
            continue

        # Skip duplicates (keep the one with more parts)
        key = (user_uuid, period_uuid)
        if key in seen and parts_count == 0:
            continue
        seen.add(key)

        new_id = uuid.uuid4()
        cur_t.execute(
            "INSERT INTO reports (id, user_id, reporting_period_id, estimated, created_at) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (user_id, reporting_period_id) DO UPDATE "
            "SET estimated = EXCLUDED.estimated "
            "RETURNING id",
            (new_id, user_uuid, period_uuid, estimated or False, created_at),
        )
        actual_id = cur_t.fetchone()[0]
        mapping[legacy_id] = actual_id

    cur_l.close()
    cur_t.close()
    return mapping


def import_report_parts(legacy, target, maps):
    """Import report_parts."""
    cur_l = legacy.cursor()
    cur_t = target.cursor()
    count = 0
    skipped = 0

    cur_l.execute(
        "SELECT id, report_id, contract_id, role_id, percentage, days, cost, "
        "created_at FROM report_parts ORDER BY id"
    )
    for row in cur_l.fetchall():
        (legacy_id, report_id, contract_id, role_id, percentage,
         days, cost, created_at) = row

        report_uuid = maps['reports'].get(report_id)
        project_uuid = maps['projects'].get(contract_id)
        if not report_uuid or not project_uuid:
            skipped += 1
            continue

        fa_id = maps['functional_areas'].get(role_id)

        cur_t.execute(
            "INSERT INTO report_parts (id, report_id, project_id, functional_area_id, "
            "percentage, days, cost, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (project_id, report_id, functional_area_id) DO NOTHING",
            (uuid.uuid4(), report_uuid, project_uuid, fa_id,
             pct_to_decimal(percentage), float_to_decimal(days, 4),
             float_to_decimal(cost), created_at),
        )
        count += 1

    if skipped:
        print(f"    (skipped {skipped} report_parts with unmapped FKs)")

    cur_l.close()
    cur_t.close()
    return count


def import_progress_reports(legacy, target, maps):
    """Import progress_reports."""
    cur_l = legacy.cursor()
    cur_t = target.cursor()
    count = 0

    cur_l.execute(
        "SELECT id, reporting_period_id, contract_id, percentage, delta, created_at "
        "FROM progress_reports ORDER BY id"
    )
    for row in cur_l.fetchall():
        _, rp_id, contract_id, percentage, delta, created_at = row

        period_uuid = maps['reporting_periods'].get(rp_id)
        project_uuid = maps['projects'].get(contract_id)
        if not period_uuid or not project_uuid:
            continue

        cur_t.execute(
            "INSERT INTO progress_reports (id, reporting_period_id, project_id, "
            "percentage, delta, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (reporting_period_id, project_id) DO NOTHING",
            (uuid.uuid4(), period_uuid, project_uuid,
             pct_to_decimal(percentage), pct_to_decimal(delta),
             created_at),
        )
        count += 1

    cur_l.close()
    cur_t.close()
    return count


def import_links(legacy, target, maps):
    """Import legacy project_links as links."""
    cur_l = legacy.cursor()
    cur_t = target.cursor()
    count = 0

    # Get contract counts per legacy project
    cur_l.execute("""
        SELECT p.id, COUNT(c.id) AS cc
        FROM projects p LEFT JOIN contracts c ON c.project_id = p.id
        GROUP BY p.id
    """)
    contract_counts = {row[0]: row[1] for row in cur_l.fetchall()}

    cur_l.execute(
        "SELECT id, project_id, title, url, link_type, created_at "
        "FROM project_links ORDER BY id"
    )
    for row in cur_l.fetchall():
        _, legacy_proj_id, title, url, link_type, created_at = row

        cc = contract_counts.get(legacy_proj_id, 0)
        if cc == 0:
            continue

        program_id = None
        project_id = None

        if cc >= 2:
            # Multi-contract project -> program
            program_id = maps['programs'].get(legacy_proj_id)
        else:
            # Single-contract project -> find the one project
            cur_l_inner = legacy.cursor()
            cur_l_inner.execute(
                "SELECT id FROM contracts WHERE project_id = %s LIMIT 1",
                (legacy_proj_id,),
            )
            contract_row = cur_l_inner.fetchone()
            cur_l_inner.close()
            if contract_row:
                project_id = maps['projects'].get(contract_row[0])

        if not program_id and not project_id:
            continue

        cur_t.execute(
            "INSERT INTO links (id, program_id, project_id, title, url, "
            "link_type, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (uuid.uuid4(), program_id, project_id, title, url,
             link_type, created_at),
        )
        count += 1

    cur_l.close()
    cur_t.close()
    return count


def _validate_count_checks(cur_l, cur_t, errors):
    """Validate row counts match between legacy and target tables."""
    checks = [
        ("functional_areas", "SELECT COUNT(*) FROM roles",
         "SELECT COUNT(*) FROM functional_areas"),
        ("rates", "SELECT COUNT(*) FROM rates",
         "SELECT COUNT(*) FROM rates"),
        ("reporting_periods", "SELECT COUNT(*) FROM reporting_periods",
         "SELECT COUNT(*) FROM reporting_periods"),
        ("budget_lines", "SELECT COUNT(*) FROM budget_lines",
         "SELECT COUNT(*) FROM budget_lines"),
        ("invoices", "SELECT COUNT(*) FROM invoices",
         "SELECT COUNT(*) FROM invoices"),
        ("non_staff_costs", "SELECT COUNT(*) FROM non_staff_costs",
         "SELECT COUNT(*) FROM non_staff_costs"),
        ("progress_reports", "SELECT COUNT(*) FROM progress_reports",
         "SELECT COUNT(*) FROM progress_reports"),
    ]
    for name, q_legacy, q_target in checks:
        cur_l.execute(q_legacy)
        l_count = cur_l.fetchone()[0]
        cur_t.execute(q_target)
        t_count = cur_t.fetchone()[0]
        status = "OK" if l_count == t_count else "MISMATCH"
        if status == "MISMATCH":
            errors.append(f"{name}: legacy={l_count}, target={t_count}")
        print(f"  {name}: legacy={l_count}, target={t_count} [{status}]")


def _validate_projects_and_reports(cur_l, cur_t, errors):
    """Validate project and report counts."""
    cur_l.execute("SELECT COUNT(*) FROM contracts")
    l_contracts = cur_l.fetchone()[0]
    cur_t.execute("SELECT COUNT(*) FROM projects")
    t_projects = cur_t.fetchone()[0]
    print(f"  projects: legacy_contracts={l_contracts}, target_projects={t_projects} "
          f"[{'OK' if t_projects >= l_contracts else 'MISMATCH'}]")

    cur_l.execute("SELECT COUNT(*) FROM reports")
    l_reports = cur_l.fetchone()[0]
    cur_t.execute("SELECT COUNT(*) FROM reports")
    t_reports = cur_t.fetchone()[0]
    diff = l_reports - t_reports
    status = "OK" if diff <= 1 else "MISMATCH"
    if diff > 1:
        errors.append(f"reports: legacy={l_reports}, target={t_reports}")
    print(f"  reports: legacy={l_reports}, target={t_reports} (diff={diff}) [{status}]")


def _validate_financial_totals(cur_l, cur_t, errors):
    """Validate budget and invoice totals."""
    cur_l.execute("SELECT ROUND(SUM(budget)::numeric, 2) FROM contracts WHERE budget IS NOT NULL")
    l_budget = cur_l.fetchone()[0]
    cur_t.execute("SELECT ROUND(SUM(budget), 2) FROM projects WHERE budget IS NOT NULL")
    t_budget = cur_t.fetchone()[0]
    status = "OK" if l_budget == t_budget else "MISMATCH"
    if status == "MISMATCH":
        errors.append(f"budget total: legacy={l_budget}, target={t_budget}")
    print(f"  budget total: legacy={l_budget}, target={t_budget} [{status}]")

    cur_l.execute("SELECT ROUND(SUM(amount)::numeric, 2) FROM invoices WHERE amount IS NOT NULL")
    l_amount = cur_l.fetchone()[0]
    cur_t.execute("SELECT ROUND(SUM(amount), 2) FROM invoices WHERE amount IS NOT NULL")
    t_amount = cur_t.fetchone()[0]
    diff_amount = abs(l_amount - t_amount) if l_amount and t_amount else Decimal("0")
    status = "OK" if diff_amount <= Decimal("1.00") else "MISMATCH"
    if status == "MISMATCH":
        errors.append(f"invoice total: legacy={l_amount}, target={t_amount} (diff={diff_amount})")
    print(f"  invoice total: legacy={l_amount}, target={t_amount} (diff={diff_amount}) [{status}]")


def _validate_percentage_ranges(cur_t, errors):
    """Validate percentage values are within 0-1 range."""
    for table in ("report_parts", "progress_reports"):
        where = ("percentage IS NOT NULL AND (percentage < 0 OR percentage > 1)"
                 if table == "report_parts"
                 else "percentage < 0 OR percentage > 1")
        cur_t.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}")
        bad_pct = cur_t.fetchone()[0]
        if bad_pct > 0:
            errors.append(f"{table}: {bad_pct} percentages out of 0-1 range")
        print(f"  percentage range ({table}): {bad_pct} out of range "
              f"[{'OK' if bad_pct == 0 else 'FAIL'}]")


def _validate_program_children(cur_t, errors):
    """Validate programs have at least 2 child projects."""
    cur_t.execute("""
        SELECT p.name, COUNT(pr.id) AS child_count
        FROM programs p
        LEFT JOIN projects pr ON pr.program_id = p.id
        GROUP BY p.id, p.name
        HAVING COUNT(pr.id) < 2
    """)
    bad_programs = cur_t.fetchall()
    if bad_programs:
        for name, cc in bad_programs:
            errors.append(f"program '{name}' has only {cc} child projects")
        print(f"  program child counts: {len(bad_programs)} programs with <2 children [FAIL]")
    else:
        print("  program child counts: all have 2+ children [OK]")


def validate(legacy, target):
    """Post-import validation checks."""
    cur_l = legacy.cursor()
    cur_t = target.cursor()
    errors = []

    print("\n--- Validation ---")
    _validate_count_checks(cur_l, cur_t, errors)
    _validate_projects_and_reports(cur_l, cur_t, errors)
    _validate_financial_totals(cur_l, cur_t, errors)
    _validate_percentage_ranges(cur_t, errors)
    _validate_program_children(cur_t, errors)

    cur_l.close()
    cur_t.close()

    if errors:
        print(f"\n{len(errors)} validation error(s):")
        for e in errors:
            print(f"  - {e}")
        return False
    print("\nAll validations passed.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Import VizzTracker data into vizzhub")
    parser.add_argument(
        "--legacy-db",
        required=True,
    )
    parser.add_argument(
        "--target-db",
        required=True,
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Legacy DB: {args.legacy_db}")
    print(f"Target DB: {args.target_db}")
    print()

    legacy = connect(args.legacy_db)
    target = connect(args.target_db)

    try:
        print("Cleaning previous tracker data...")
        clean_tracker_data(target)
        print()

        print("Importing...")
        build_mappings(legacy, target)

        valid = validate(legacy, target)

        if args.dry_run:
            print("\n--- DRY RUN: rolling back ---")
            target.rollback()
        elif valid:
            print("\nCommitting...")
            target.commit()
            print("Done.")
        else:
            print("\nValidation failed. Rolling back.")
            target.rollback()
            sys.exit(1)
    except Exception as e:
        target.rollback()
        print(f"\nError: {e}")
        raise
    finally:
        legacy.close()
        target.close()


if __name__ == "__main__":
    main()
