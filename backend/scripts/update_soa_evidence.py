"""Update SOA evidence fields with proper links to ISO docs in VizzHub.

Maps Spanish document references from the Excel to actual DB documents with
markdown links in the format: [CODE - Title](/iso/docs?page=slug)

Run: python -m scripts.update_soa_evidence
"""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import Base  # noqa: F401
from app.core.models.user import UserDB  # noqa: F401
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB

logger = structlog.get_logger()


def _link(code: str, title: str, slug: str) -> str:
    return f"[{code} - {title}](/iso/docs?page={slug})"


# Document references mapped to VizzHub links
POL02 = _link("POL02", "Employee Security Policy", "employee-security-policy-acceptable-use")
POL03 = _link("POL03", "Information Classification Policy", "information-classification-policy")
POL04 = _link("POL04", "Access Control Policy", "access-control-policy")
POL05 = _link("POL05", "Cloud Usage Policy", "cloud-usage-policy")
POL06 = _link("POL06", "Security Incident Management Policy", "security-incident-management-policy")
POL07 = _link("POL07", "Business Continuity Plan", "business-continuity-plan")
POL08 = _link("POL08", "Capacity Management Policy", "capacity-management-policy")
POL09 = _link("POL09", "Cryptographic Controls Policy", "cryptographic-controls-policy")
POL10 = _link("POL10", "Secure Development Policy", "secure-development-policy")
POL11 = _link("POL11", "Change Management Policy", "change-management-policy")
POL12 = _link("POL12", "Secure Erasure Policy", "secure-erasure-policy")

PR02 = _link("PR02", "Supplier Relationship Procedure", "supplier-relationship-procedure")
PR03 = _link("PR03", "People Controls Procedure", "people-controls-procedure")
PR04 = _link("PR04", "Teleworking Policy", "teleworking-policy")
PR05 = _link("PR05", "Physical Controls", "physical-controls")
PR06 = _link("PR06", "Secure Software Development Procedure", "secure-software-development-procedure")
PR07 = _link("PR07", "Security Configuration Procedure", "security-configuration-procedure")
PR08 = _link("PR08", "Operations Security Procedure", "operations-security-procedure")
PR09 = _link("PR09", "Communications Security", "communications-security")
PR10 = _link("PR10", "IS Acquisition, Development and Maintenance", "is-acquisition-development-and-maintenance-procedure")
PR11 = _link("PR11", "Data Leakage Prevention Procedure", "data-leakage-prevention-procedure")

RE01 = _link("RE01", "Authorities Contact Register", "authorities-contact-register")
RE02 = _link("RE02", "Threat Monitoring Register", "threat-monitoring-register")
RE03 = _link("RE03", "Authorization Matrix", "authorization-matrix")
RE04 = _link("RE04", "Asset Inventory", "asset-inventory-equipments")
RE05 = _link("RE05", "Supplier Register", "supplier-register")
RE06 = _link("RE06", "Supplier Evaluation Register", "supplier-evaluation-register")
RE07 = _link("RE07-B", "Security Incident Register", "security-incident-register")
RE08 = _link("RE08", "Test Calendar", "test-calendar")
RE10 = _link("RE10", "Change Management Register", "change-management-register")
RE11 = _link("RE11", "Document Control Register", "document-control-register")
RE16 = _link("RE16", "Legal & Regulatory Register", "legal-regulatory-register")

DOC02 = _link("DOC02", "Equipment Handover Form", "equipment-handover-form")

# Evidence mapping: control_id → evidence text with markdown links
EVIDENCE_EN: dict[str, str] = {
    "A.5.5": RE01,
    "A.5.7": RE02,
    "A.5.9": RE04,
    "A.5.11": DOC02,
    "A.5.12": POL03,
    "A.5.15": f"{POL04}, {RE03}",
    "A.5.19": f"{PR02}, {RE05}, {RE06}",
    "A.5.23": POL05,
    "A.5.24": f"{POL06}, {RE07}",
    "A.5.29": POL07,
    "A.5.30": RE08,
    "A.5.31": f"{RE16}, {RE11}",
    "A.5.32": RE04,
    "A.5.33": f"{POL03}, {POL04}, {POL07}, {PR08}",
    "A.6.1": PR03,
    "A.6.2": PR03,
    "A.6.3": PR03,
    "A.6.4": f"{PR03}, {POL02}",
    "A.6.5": PR03,
    "A.6.6": f"{PR03}, {POL02}",
    "A.6.7": f"{PR03}, {PR04}",
    "A.6.8": f"{POL06}, {POL02}",
    "A.7.1": PR05,
    "A.7.2": PR05,
    "A.7.3": PR05,
    "A.7.4": PR05,
    "A.7.5": PR05,
    "A.7.6": PR05,
    "A.7.7": f"{PR05}, {POL02}",
    "A.7.8": PR05,
    "A.7.9": f"{PR05}, {POL02}",
    "A.7.10": f"{PR05}, {POL02}",
    "A.7.11": PR05,
    "A.7.12": PR05,
    "A.7.13": PR05,
    "A.7.14": PR05,
    "A.8.1": POL02,
    "A.8.2": POL04,
    "A.8.3": f"{RE03}, {POL04}",
    "A.8.4": POL10,
    "A.8.5": POL04,
    "A.8.6": POL08,
    "A.8.7": PR08,
    "A.8.8": PR08,
    "A.8.9": PR07,
    "A.8.10": POL12,
    "A.8.11": f"{POL12}, {PR10}",
    "A.8.12": PR11,
    "A.8.13": PR08,
    "A.8.14": PR08,
    "A.8.15": PR08,
    "A.8.16": PR08,
    "A.8.17": PR08,
    "A.8.18": PR08,
    "A.8.19": PR08,
    "A.8.20": PR09,
    "A.8.21": PR09,
    "A.8.22": PR09,
    "A.8.23": f"{PR09}, {POL02}",
    "A.8.24": POL09,
    "A.8.25": POL10,
    "A.8.26": POL10,
    "A.8.27": PR10,
    "A.8.28": PR06,
    "A.8.29": PR10,
    "A.8.30": PR10,
    "A.8.31": PR10,
    "A.8.32": f"{POL11}, {RE10}",
}


async def update(db_url: str | None = None) -> int:
    url = db_url or get_settings().database_url
    engine = create_async_engine(url)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    updated = 0
    async with session_maker() as db:
        node = (await db.execute(
            select(IsoDocNodeDB).where(
                IsoDocNodeDB.slug == "statement-of-applicability"
            )
        )).scalar_one_or_none()

        if not node:
            print("  ERROR: SOA node not found")
            await engine.dispose()
            return 0

        rows = (await db.execute(
            select(RegistryRowDB).where(RegistryRowDB.node_id == node.id)
            .order_by(RegistryRowDB.row_index)
        )).scalars().all()

        for row in rows:
            control_id = row.data["control_id"]
            if control_id in EVIDENCE_EN:
                data = dict(row.data)
                data["evidence"] = EVIDENCE_EN[control_id]
                row.data = data
                updated += 1

        await db.commit()

    await engine.dispose()
    return updated


async def main() -> None:
    print("Updating SOA evidence with document links...")
    count = await update()
    print(f"Done. Updated {count} rows.")


if __name__ == "__main__":
    asyncio.run(main())
