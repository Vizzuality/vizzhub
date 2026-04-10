"""Seed the Audit Findings Register from the Excel import.

Reads translated data from the Spanish Excel and creates:
1. Registry type with schema definition
2. Tree node under Records > Audits
3. 19 translated finding rows for audit cycle 2025

Usage:
    cd backend && python -m scripts.seed_audit_findings

Idempotent — skips creation if the registry type already exists.
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

import structlog

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from sqlalchemy import select

from app.database import async_session_maker
from app.core.models.user import UserDB  # noqa: F401 — register users table for FK resolution
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.iso_docs.models.registry_type import RegistryTypeDB

logger = structlog.get_logger()

REGISTRY_TYPE_NAME = "Audit Findings Register"
REGISTRY_TYPE_SLUG = "audit-findings-register"
REGISTRY_TYPE_DESCRIPTION = (
    "Tracks observations and improvement opportunities identified during "
    "internal and external audits, including actions taken and resolution "
    "status. Key fields: audit source (internal/external phase), finding "
    "type (observation or improvement opportunity), description, corrective "
    "actions, and completion status. Per ISO 9001 \u00a710.1 / ISO 27001 \u00a710.1."
)

SCHEMA = [
    {
        "key": "source",
        "label": "Source",
        "type": "select",
        "required": True,
        "width": 180,
        "options": [
            "Internal Audit",
            "External Audit Phase I",
            "External Audit Phase II",
        ],
        "option_colors": {
            "Internal Audit": "#3b82f6",
            "External Audit Phase I": "#f59e0b",
            "External Audit Phase II": "#8b5cf6",
        },
    },
    {
        "key": "source_date",
        "label": "Source Date",
        "type": "date",
        "required": True,
        "width": 120,
    },
    {
        "key": "type",
        "label": "Type",
        "type": "select",
        "required": True,
        "width": 160,
        "options": ["Observation", "Improvement Opportunity"],
        "option_colors": {
            "Observation": "#f59e0b",
            "Improvement Opportunity": "#3b82f6",
        },
    },
    {
        "key": "description",
        "label": "Description",
        "type": "string",
        "required": True,
        "width": 350,
    },
    {
        "key": "actions_taken",
        "label": "Actions Taken",
        "type": "string",
        "required": False,
        "width": 350,
    },
    {
        "key": "status",
        "label": "Status",
        "type": "select",
        "required": True,
        "width": 130,
        "options": ["Pending", "In Progress", "Completed"],
        "option_colors": {
            "Pending": "#ef4444",
            "In Progress": "#f59e0b",
            "Completed": "#22c55e",
        },
    },
    {
        "key": "remarks",
        "label": "Remarks",
        "type": "string",
        "required": False,
        "width": 200,
    },
]

SEED_YEAR = 2025

# Translated rows from temp/iso/REGISTROS/10. MEJORA/RESUMEN OBSERVACIONES_OPORTUNIDADES.xlsx
# Original: Spanish, 19 rows from sheet "2025-2026", data rows 6-24
ROWS = [
    # --- Internal Audit (AI), 18/02/2025 — 4 observations ---
    {
        "source": "Internal Audit",
        "source_date": "2025-02-18",
        "type": "Observation",
        "description": (
            "Climate change is not evidenced as an element to analyze "
            "in the organizational context."
        ),
        "actions_taken": "Climate-related aspects have been included in the SWOT analysis.",
        "status": "Completed",
    },
    {
        "source": "Internal Audit",
        "source_date": "2025-02-18",
        "type": "Observation",
        "description": (
            "Although document control is established through a master list, "
            "it is not up to date."
        ),
        "actions_taken": "System procedures have been added to the document list.",
        "status": "Completed",
    },
    {
        "source": "Internal Audit",
        "source_date": "2025-02-18",
        "type": "Observation",
        "description": (
            "Risk treatment plans are not correctly updated in some cases."
        ),
        "actions_taken": "Updates have been included in the Risk Analysis.",
        "status": "Completed",
    },
    {
        "source": "Internal Audit",
        "source_date": "2025-02-18",
        "type": "Observation",
        "description": (
            "Although disaster scenarios and their respective drill tests are "
            "defined (A5.29), a correct relationship cannot be evidenced across "
            "all proposed scenarios."
        ),
        "actions_taken": "The scenarios have been analyzed and corrected.",
        "status": "Completed",
    },
    # --- External Audit Phase I (AE I), 06/03/2025 — 2 observations ---
    {
        "source": "External Audit Phase I",
        "source_date": "2025-03-06",
        "type": "Observation",
        "description": (
            "The Observations Summary register does not record the actions "
            "taken regarding the improvement opportunities identified in the "
            "internal audit report."
        ),
        "actions_taken": (
            "Observations and actions derived from the internal audit "
            "have been included."
        ),
        "status": "Completed",
    },
    {
        "source": "External Audit Phase I",
        "source_date": "2025-03-06",
        "type": "Observation",
        "description": (
            "Regarding monitoring, measurement, analysis and evaluation: "
            "the frequency set as annual for some indicators should be reviewed "
            "so that trends can be appreciated."
        ),
        "actions_taken": (
            "The frequency has been reviewed and the relevant changes "
            "have been made."
        ),
        "status": "Completed",
    },
    # --- External Audit Phase II (AE II), 25/03/2025 — 13 findings ---
    {
        "source": "External Audit Phase II",
        "source_date": "2025-03-25",
        "type": "Improvement Opportunity",
        "description": (
            "Standardization of the Management Review: it is recommended to "
            "structure the Management Review report under a uniform format that "
            "includes: data evaluated, Management's assessment, and actions "
            "and decisions. This will facilitate traceability and strategic "
            "decision-making."
        ),
        "actions_taken": (
            "In response to the identified improvement opportunity, a structure "
            "has been adopted that: presents each required input as an independent "
            "block, systematically includes the data evaluated (SWOT analysis, "
            "objectives, indicators, etc.), Management's assessment and diagnosis, "
            "and derived actions and decisions (future plans, follow-up, etc.)."
        ),
        "status": "Completed",
    },
    {
        "source": "External Audit Phase II",
        "source_date": "2025-03-25",
        "type": "Improvement Opportunity",
        "description": (
            "Evaluation of opportunities using an effort-benefit matrix: it is "
            "suggested to replace the current opportunity evaluation criteria "
            "with an effort-benefit matrix for more effective prioritization."
        ),
        "actions_taken": "The evaluation has been changed to an ICE scoring model.",
        "status": "Completed",
    },
    {
        "source": "External Audit Phase II",
        "source_date": "2025-03-25",
        "type": "Improvement Opportunity",
        "description": (
            "Linking actions to management system objectives: it is recommended "
            "to reflect risk and opportunity actions directly in the system "
            "objectives sheet to avoid duplication."
        ),
        "actions_taken": (
            "Risks and opportunities have been linked to the system objectives "
            "table."
        ),
        "status": "Completed",
    },
    {
        "source": "External Audit Phase II",
        "source_date": "2025-03-25",
        "type": "Improvement Opportunity",
        "description": (
            "Alignment of the service delivery procedure with the process map: "
            "it is recommended to review and adjust the procedure to ensure "
            "consistency with the current process map."
        ),
        "actions_taken": (
            "Support processes have been adjusted to better reflect what is "
            "described in the service delivery procedure."
        ),
        "status": "Completed",
    },
    {
        "source": "External Audit Phase II",
        "source_date": "2025-03-25",
        "type": "Improvement Opportunity",
        "description": (
            "Development of performance indicators: it is suggested to include "
            "technical description, formula, and calculation methodology for "
            "each KPI, for more precise and traceable measurement."
        ),
        "actions_taken": None,
        "status": "Pending",
    },
    {
        "source": "External Audit Phase II",
        "source_date": "2025-03-25",
        "type": "Improvement Opportunity",
        "description": (
            "Data extraction for KPIs from operational tools: it is proposed "
            "to extract data from Jira and GitHub to identify useful KPIs for "
            "operational monitoring."
        ),
        "actions_taken": None,
        "status": "Pending",
    },
    {
        "source": "External Audit Phase II",
        "source_date": "2025-03-25",
        "type": "Improvement Opportunity",
        "description": (
            "Clarity in change management within the service delivery procedure: "
            "it is suggested to specify whether change management tools are used "
            "and how they operate."
        ),
        "actions_taken": (
            "The change management section has been reviewed, adding details "
            "about tools and management processes."
        ),
        "status": "Completed",
    },
    {
        "source": "External Audit Phase II",
        "source_date": "2025-03-25",
        "type": "Improvement Opportunity",
        "description": "Develop a RACI matrix for segregation of duties.",
        "actions_taken": "Included in the Service Delivery Procedure.",
        "status": "Completed",
    },
    {
        "source": "External Audit Phase II",
        "source_date": "2025-03-25",
        "type": "Observation",
        "description": (
            "Information security risk treatment \u2014 non-applied controls: "
            "the applicability of controls 8.11 Data Masking and 8.30 "
            "Outsourced Development should be reviewed (\u00a76.1.3)."
        ),
        "actions_taken": (
            "Applicability has been reviewed in the SOA and in the documents: "
            "PR10 - Acquisition, Development and Maintenance of Information "
            "Systems."
        ),
        "status": "Completed",
    },
    {
        "source": "External Audit Phase II",
        "source_date": "2025-03-25",
        "type": "Observation",
        "description": (
            "Document control \u2014 pending update: modifications to the manual "
            "and document edition status have not been recorded following the "
            "non-conformities observed in Phase I. The organization indicated "
            "these would be implemented after Phase II (\u00a77.5)."
        ),
        "actions_taken": "Records have been registered and updated.",
        "status": "Completed",
    },
    {
        "source": "External Audit Phase II",
        "source_date": "2025-03-25",
        "type": "Observation",
        "description": (
            "Operational planning and control: "
            "a) 5.8 Information security in project management: security risks "
            "should be evaluated in early stages also for non-development projects. "
            "b) 5.25 Security event assessment: incident classification is "
            "inconsistent between the policy and the corresponding register. "
            "c) 5.30 Business continuity: include scenarios such as unavailability "
            "of people, suppliers, and premises. "
            "d) 6.3 Information security training: the 2025 training plan is missing. "
            "e) 7.9 Security of off-site equipment: only new devices are under "
            "MDM; all should be included. "
            "f) 8.23 Web filtering: strengthen access controls to external websites "
            "to reduce exposure to malicious content (\u00a78.1)."
        ),
        "actions_taken": (
            "a) Reviewed in SOA and Service Delivery Procedure. "
            "b) Security Incident Management Policy and register have been revised. "
            "c) Business Continuity Plan reviewed. "
            "d) Included. "
            "e) All devices included. "
            "f) SOA text on application in Communication Security reviewed."
        ),
        "status": "Completed",
    },
    {
        "source": "External Audit Phase II",
        "source_date": "2025-03-25",
        "type": "Observation",
        "description": (
            "Responsibilities in contracts and proposals: the service delivery "
            "procedure does not clearly specify the responsibilities and "
            "authorities for contract and proposal review and approval. This "
            "is not documented elsewhere in the system either (\u00a78.2)."
        ),
        "actions_taken": (
            "This has been reflected in the Service Delivery Procedure."
        ),
        "status": "Completed",
    },
    {
        "source": "External Audit Phase II",
        "source_date": "2025-03-25",
        "type": "Observation",
        "description": (
            "Lack of document control in a project: the document "
            '"Unilever NDPE Story \u2014 Phase II: Business Need (Roles and '
            'Responsibilities)" does not indicate version status, although '
            "according to the schedule it should be finalized (\u00a77.5)."
        ),
        "actions_taken": "This has been corrected.",
        "status": "Completed",
    },
]

AUDITS_GROUP_SLUG = "audits"
NODE_TITLE = "Audit Findings Register"


async def _find_audits_group(db) -> IsoDocNodeDB | None:
    """Find the Audits group node in the ISO Docs tree."""
    result = await db.execute(
        select(IsoDocNodeDB).where(
            IsoDocNodeDB.slug == AUDITS_GROUP_SLUG,
            IsoDocNodeDB.type == "group",
        )
    )
    return result.scalar_one_or_none()


async def _find_or_create_registry_type(db) -> RegistryTypeDB:
    """Find existing or create the Audit Findings Register type."""
    result = await db.execute(
        select(RegistryTypeDB).where(RegistryTypeDB.slug == REGISTRY_TYPE_SLUG)
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.info(
            "registry_type_exists",
            type_id=str(existing.id),
            name=REGISTRY_TYPE_NAME,
        )
        return existing

    rt = RegistryTypeDB(
        name=REGISTRY_TYPE_NAME,
        slug=REGISTRY_TYPE_SLUG,
        description=REGISTRY_TYPE_DESCRIPTION,
        is_yearly=True,
        schema=SCHEMA,
    )
    db.add(rt)
    await db.flush()
    await db.refresh(rt)
    logger.info(
        "registry_type_created",
        type_id=str(rt.id),
        name=REGISTRY_TYPE_NAME,
    )
    return rt


async def _find_or_create_node(db, registry_type: RegistryTypeDB, parent_id) -> IsoDocNodeDB:
    """Find existing or create the registry node under the Audits group."""
    result = await db.execute(
        select(IsoDocNodeDB).where(
            IsoDocNodeDB.registry_type_id == registry_type.id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.info(
            "registry_node_exists",
            node_id=str(existing.id),
            title=existing.title,
        )
        return existing

    from app.modules.iso_docs.services.tree_service import (
        ensure_unique_slug,
        generate_slug,
        get_next_position,
    )

    slug = generate_slug(NODE_TITLE)
    slug = await ensure_unique_slug(db, slug)
    position = await get_next_position(db, parent_id)

    node = IsoDocNodeDB(
        title=NODE_TITLE,
        slug=slug,
        type="registry",
        parent_id=parent_id,
        position=position,
        registry_type_id=registry_type.id,
    )
    db.add(node)
    await db.flush()
    await db.refresh(node)

    db.add(IsoDocMetadataDB(node_id=node.id))
    await db.flush()

    logger.info(
        "registry_node_created",
        node_id=str(node.id),
        title=NODE_TITLE,
        parent_id=str(parent_id) if parent_id else None,
    )
    return node


async def _seed_rows(db, node_id, year: int) -> int:
    """Insert finding rows if none exist for the given year."""
    result = await db.execute(
        select(RegistryRowDB).where(
            RegistryRowDB.node_id == node_id,
            RegistryRowDB.year == year,
        ).limit(1)
    )
    if result.scalar_one_or_none():
        logger.info(
            "registry_rows_exist",
            node_id=str(node_id),
            year=year,
        )
        return 0

    for idx, row_data in enumerate(ROWS):
        db.add(
            RegistryRowDB(
                node_id=node_id,
                year=year,
                row_index=idx,
                data={k: v for k, v in row_data.items() if v is not None},
            )
        )

    await db.flush()
    logger.info(
        "registry_rows_seeded",
        node_id=str(node_id),
        year=year,
        count=len(ROWS),
    )
    return len(ROWS)


async def main() -> None:
    async with async_session_maker() as db:
        audits_group = await _find_audits_group(db)
        if not audits_group:
            print("ERROR: 'Audits' group node not found in ISO Docs tree.")
            print("Create it first via the UI or check the slug.")
            sys.exit(1)

        print(f"Found Audits group: {audits_group.id}")

        rt = await _find_or_create_registry_type(db)
        print(f"Registry type: {rt.name} ({rt.id})")

        node = await _find_or_create_node(db, rt, audits_group.id)
        print(f"Registry node: {node.title} ({node.id})")

        count = await _seed_rows(db, node.id, SEED_YEAR)
        if count:
            print(f"Seeded {count} rows for year {SEED_YEAR}")
        else:
            print(f"Rows already exist for year {SEED_YEAR}, skipped")

        await db.commit()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
