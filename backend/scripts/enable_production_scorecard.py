"""Enable scorecard/alerts flags for production projects.

Run after deploying migrations 021+022. Idempotent.

Usage:
    cd backend
    python scripts/enable_production_scorecard.py [--db URL]
"""

import argparse
import psycopg2

PRODUCTION_PROJECTS = [
    'Open Earth Monitor',
    'FIP',
    'GMW Phase 8',
    'FHWPC Implementation phase',
    'ICIMOD Web Overhaul (Phase 2)',
    'CATALYSE',
    'HE MIRACA',
    'Amazonia360 - Beta version 2',
    'ECCC HJBL',
    'AGORA Paraguay',
    '4Growth',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--db',
        default='postgresql://scorecard:scorecard@localhost:5432/scorecard',
    )
    args = parser.parse_args()

    conn = psycopg2.connect(args.db)
    cur = conn.cursor()

    for name in PRODUCTION_PROJECTS:
        cur.execute(
            "UPDATE projects "
            "SET has_scorecard = true, has_dependabot_alerts = true, has_budget_alerts = true "
            "WHERE TRIM(name) = %s "
            "RETURNING name",
            (name,),
        )
        row = cur.fetchone()
        if row:
            print(f"  OK: {row[0]}")
        else:
            print(f"  NOT FOUND: {name}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone. {len(PRODUCTION_PROJECTS)} projects processed.")


if __name__ == '__main__':
    main()
