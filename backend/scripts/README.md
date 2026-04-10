# Backend Scripts

Reusable utility scripts for development and testing.

## Available Scripts

### generate_jwt_token.py

Generates JWT tokens for testing authenticated API endpoints.

```bash
python scripts/generate_jwt_token.py
python scripts/generate_jwt_token.py --user-id "admin@example.com" --roles "user,admin"
```

### preview_playbook_export.py

Generates the playbook static site from local DB and serves it for browser preview.

```bash
python scripts/preview_playbook_export.py
```

### seed_audit_findings.py

Seeds the Audit Findings Register (registry type, tree node, and 19 translated rows) into the ISO Docs system. Idempotent.

```bash
cd backend && python -m scripts.seed_audit_findings
```
