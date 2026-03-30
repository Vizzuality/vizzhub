#!/usr/bin/env python
"""Preview the playbook static export locally.

Generates the static site from local DB and writes to a temp directory,
then serves it with a simple HTTP server for browser preview.

Usage:
    python scripts/preview_playbook_export.py
    # Then open http://localhost:8080
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUTPUT_DIR = Path(__file__).parent.parent / "_playbook_preview"


async def generate():
    from app.database import async_session_maker
    from app.modules.playbook.services.publish_service import PublishService

    svc = PublishService()
    async with async_session_maker() as db:
        files = await svc._generate_site(db)

    OUTPUT_DIR.mkdir(exist_ok=True)
    for rel_path, content in files.items():
        out_path = OUTPUT_DIR / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(content)

    print(f"\nGenerated {len(files)} files in {OUTPUT_DIR}/")
    return len(files)


def serve():
    import http.server
    import functools

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(OUTPUT_DIR),
    )
    port = 8080
    with http.server.HTTPServer(("", port), handler) as httpd:
        print(f"Serving at http://localhost:{port}")
        print("Press Ctrl+C to stop\n")
        httpd.serve_forever()


if __name__ == "__main__":
    try:
        count = asyncio.run(generate())
        serve()
    except ValueError as e:
        print(f"\nError: {e}")
        print("Make sure you have public playbook pages in your local database.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopped.")
