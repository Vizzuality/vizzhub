"""Create devstack_entries and devstack_user_prefs tables.

Revision ID: 057_devstack
Revises: 056_est_true
"""

from alembic import op

revision = "057_devstack"
down_revision = "056_est_true"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS devstack_entries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            description TEXT NOT NULL,
            type VARCHAR(20) NOT NULL,
            install_method VARCHAR(20) NOT NULL,
            url TEXT,
            package VARCHAR(200),
            package_version VARCHAR(50),
            required BOOLEAN NOT NULL DEFAULT false,
            origin VARCHAR(20) NOT NULL DEFAULT 'internal',
            tech JSONB DEFAULT '[]'::jsonb,
            active BOOLEAN NOT NULL DEFAULT true,
            created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            updated_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_devstack_entries_name UNIQUE (name),
            CONSTRAINT ck_devstack_entries_type CHECK (
                type IN ('skill', 'command', 'plugin', 'config', 'agent')
            ),
            CONSTRAINT ck_devstack_entries_install_method CHECK (
                install_method IN ('github', 'npm')
            ),
            CONSTRAINT ck_devstack_entries_origin CHECK (
                origin IN ('internal', 'external')
            ),
            CONSTRAINT ck_devstack_entries_github_url CHECK (
                install_method != 'github' OR url IS NOT NULL
            ),
            CONSTRAINT ck_devstack_entries_npm_package CHECK (
                install_method != 'npm' OR package IS NOT NULL
            )
        )
    """)

    op.execute(
        "INSERT INTO roles (id, name)"
        " VALUES (gen_random_uuid(), 'devstack_manager')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM roles WHERE name = 'devstack_manager'")

    op.execute("DROP TABLE IF EXISTS devstack_entries")
