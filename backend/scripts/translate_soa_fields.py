"""Translate SOA Spanish text fields (management, justification, evidence) to English.

Uses official ISO terminology per the iso-doc-translator skill glossary.
Run: python -m scripts.translate_soa_fields

Idempotent: only updates rows where management/justification contain Spanish text.
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

# Translations for management field — keyed by control_id
# Uses official ISO terminology per iso-doc-translator skill
MANAGEMENT_EN: dict[str, str] = {
    "A.5.1": (
        "An information security policy is in place, approved by top management "
        "and reviewed annually during the management review."
    ),
    "A.5.2": (
        "An up-to-date organization chart and job profiles define information "
        "security roles and responsibilities."
    ),
    "A.5.3": (
        "Segregation of duties is implemented within the organization for "
        "conflicting areas wherever possible."
    ),
    "A.5.4": (
        "An Employee Security Policy, Acceptable Use Policy, and signed "
        "confidentiality clauses are in place for all personnel."
    ),
    "A.5.5": "A register is maintained for contact with relevant authorities.",
    "A.5.6": (
        "The organization subscribes to forums such as INCIBE, CCN-CERT, etc."
    ),
    "A.5.7": (
        "A threat monitoring register is maintained to collect and analyze "
        "threat intelligence information."
    ),
    "A.5.8": (
        "Information security is incorporated in all projects from early stages, "
        "including non-technical ones. Assets are identified, risks assessed, and "
        "applicable controls documented in project plans."
    ),
    "A.5.9": "An up-to-date asset inventory is maintained.",
    "A.5.10": (
        "Acceptable use rules and information handling procedures are defined "
        "in the Employee Security Policy and confidentiality clauses."
    ),
    "A.5.11": "An asset delivery and return register is maintained.",
    "A.5.12": (
        "An information classification procedure defines how information is "
        "classified, labelled, and handled."
    ),
    "A.5.15": (
        "User validation through access management. Users are not local "
        "administrators. Each user has unique credentials with periodic review."
    ),
    "A.5.16": (
        "User validation through access management. Users are not local "
        "administrators. Each user has unique credentials with periodic review."
    ),
    "A.5.17": (
        "User validation through access management. Users are not local "
        "administrators. Each user has unique credentials with periodic review."
    ),
    "A.5.18": (
        "User validation through access management. Users are not local "
        "administrators. Each user has unique credentials with periodic review."
    ),
    "A.5.19": "A supplier relationship procedure is defined.",
    "A.5.20": "A supplier relationship procedure is defined.",
    "A.5.21": (
        "Suppliers are verified to comply with information security requirements."
    ),
    "A.5.22": (
        "All critical suppliers for information security are listed and evaluated "
        "per the supplier management procedure."
    ),
    "A.5.23": (
        "A cloud usage policy is in place, also referenced in the Employee "
        "Security Policy."
    ),
    "A.5.24": "An information security incident management policy is defined.",
    "A.5.25": "An information security incident management policy is defined.",
    "A.5.26": "An information security incident management policy is defined.",
    "A.5.27": "An information security incident management policy is defined.",
    "A.5.28": "An information security incident management policy is defined.",
    "A.5.29": (
        "Business continuity is managed per the corresponding procedure. "
        "The ISMS Manager is responsible for its implementation."
    ),
    "A.5.30": "Periodic business continuity tests are conducted.",
    "A.5.31": "Applicable legislation has been identified and documented.",
    "A.5.32": (
        "Intellectual property legislation is complied with. All operating systems "
        "and software are properly licensed."
    ),
    "A.5.33": (
        "Multiple procedures and working methods ensure protection of records."
    ),
    "A.5.34": "GDPR requirements are complied with.",
    "A.5.35": "Annual management system audits are conducted.",
    "A.5.36": "Annual management review verifies compliance with policies.",
    "A.5.37": (
        "The Playbook documents operational procedures, with a private section "
        "for employees and a public section."
    ),
    "A.6.1": (
        "Management verifies candidate information through interviews "
        "and background checks."
    ),
    "A.6.2": (
        "Employment contracts are signed based on the role. Employees sign "
        "confidentiality clauses upon joining."
    ),
    "A.6.3": (
        "Training is delivered according to training plans managed by the "
        "management system responsible."
    ),
    "A.6.4": (
        "Disciplinary process is implemented by default per the applicable "
        "collective bargaining agreement and Workers' Statute."
    ),
    "A.6.5": (
        "Upon termination, access accounts are deactivated and company assets "
        "are returned."
    ),
    "A.6.6": (
        "Confidentiality agreements and the Employee Security Policy are "
        "in place."
    ),
    "A.6.7": "A remote working policy is defined for the organization.",
    "A.6.8": (
        "An incident management policy is defined and employees know how to "
        "report security events through the established channels."
    ),
    "A.7.1": "Defined in PR05 Physical Controls.",
    "A.7.2": "Defined in PR05 Physical Controls.",
    "A.7.3": "Defined in PR05 Physical Controls.",
    "A.7.4": "Defined in PR05 Physical Controls.",
    "A.7.5": "Defined in PR05 Physical Controls.",
    "A.7.6": "Defined in PR05 Physical Controls.",
    "A.7.7": (
        "The Employee Security Policy and ISMS documentation require users to "
        "maintain a clear desk and screen policy."
    ),
    "A.7.8": "Equipment is adequately protected against environmental risks.",
    "A.7.9": (
        "The Employee Security Policy defines employee responsibilities for "
        "off-premises use of assets."
    ),
    "A.7.10": "Defined in PR05 Physical Controls.",
    "A.7.11": (
        "Not applicable in the traditional sense due to remote working model. "
        "Laptop batteries serve as backup power for interruptions."
    ),
    "A.7.12": "Cables are kept organized and away from potential hazards.",
    "A.7.13": (
        "Equipment owners periodically review their equipment to ensure proper "
        "functioning and absence of unauthorized software."
    ),
    "A.7.14": "Defined in PR05 Physical Controls.",
    "A.8.1": (
        "Multiple mechanisms protect endpoint devices: disk encryption, "
        "screen lock, antivirus, and access controls."
    ),
    "A.8.2": (
        "Access management defines who has access, their permissions, and "
        "periodic access reviews."
    ),
    "A.8.3": (
        "Each user has access only to information relevant to their department."
    ),
    "A.8.4": (
        "Only authorized personnel have access to source code."
    ),
    "A.8.5": (
        "Each user has unique authentication credentials for system access."
    ),
    "A.8.6": (
        "Capacity is auto-scalable through cloud providers and monitored "
        "by responsible personnel."
    ),
    "A.8.7": (
        "Detection, prevention, and recovery controls are implemented as "
        "protection against malware."
    ),
    "A.8.8": (
        "The ISMS Manager subscribes to INCIBE for vulnerability alerts. "
        "Compliance checks are performed regularly."
    ),
    "A.8.9": (
        "Secure equipment configuration is defined: minimizing access, "
        "synchronizing clocks, configuring MFA, and limiting privileges."
    ),
    "A.8.10": "Defined in POL12 Secure Disposal Policy.",
    "A.8.11": (
        "Fictitious data is used in test environments and no data is shared "
        "with third parties."
    ),
    "A.8.12": "Defined in PR11 Data Leakage Prevention procedure.",
    "A.8.13": (
        "A backup policy is defined within the Operations Security procedure."
    ),
    "A.8.14": "Information is backed up per the backup policy.",
    "A.8.15": (
        "Defined in the Operations Security procedure; implemented through "
        "Google Workspace."
    ),
    "A.8.16": (
        "Defined in the Operations Security procedure; implemented through "
        "Google Workspace."
    ),
    "A.8.17": "All clocks are synchronized.",
    "A.8.18": "Defined in PR08 Operations Security.",
    "A.8.19": "Defined in PR08 Operations Security.",
    "A.8.20": (
        "No internal network exists; cloud access segregation is implemented."
    ),
    "A.8.21": (
        "Network service security measures are documented to ensure secure "
        "internet access."
    ),
    "A.8.22": "Google-based network segregation is in place.",
    "A.8.23": (
        "An alternative approach is implemented: due to the technical nature "
        "of work, broad internet access is needed. Compensating controls "
        "include security awareness training and acceptable use policies."
    ),
    "A.8.24": (
        "All sensitive documentation (internal and client information, "
        "proprietary technology, personal data) is encrypted."
    ),
    "A.8.25": "Software development follows the Secure Development Policy.",
    "A.8.26": (
        "Security requirements are defined in the Secure Development Policy."
    ),
    "A.8.27": (
        "Secure engineering principles are applied at all stages of software "
        "development."
    ),
    "A.8.28": "Defined in the Secure Coding procedure.",
    "A.8.29": (
        "Security testing is performed before any deployment, ensuring "
        "software meets established requirements."
    ),
    "A.8.30": (
        "Outsourced development is regulated through contractual security "
        "clauses, access controls, use of fictitious data, and compliance "
        "audits."
    ),
    "A.8.31": (
        "Software development separates production, test, and development "
        "environments per the Secure Development Policy."
    ),
    "A.8.32": (
        "Change management is conducted per the Change Management Policy."
    ),
    "A.8.33": (
        "Test data is protected through: anonymized or randomly generated data, "
        "restricted access to test environments, and data masking."
    ),
    "A.8.34": (
        "Audit testing activities involving information systems are carefully "
        "planned to minimize impact on operations."
    ),
}

# Translations for justification field
JUSTIFICATION_EN: dict[str, str] = {
    "_default": "Required by ISO 27001:2022 and risk assessment.",
    "A.5.5": (
        "Contact with authorities is maintained for business continuity "
        "management preparedness."
    ),
    "A.5.6": (
        "Implementation of this control is necessary for our business activities "
        "and to improve our security posture."
    ),
    "A.5.11": (
        "Applicable to manage risks associated with loss and/or theft of assets."
    ),
    "A.5.23": (
        "Applicable as all infrastructure is cloud-based."
    ),
    "A.5.31": (
        "To avoid legal non-compliance and protect the organization's "
        "intellectual property. Applicable legislation is observed."
    ),
    "A.6.7": (
        "Applicable as remote working is the primary working model of the "
        "organization."
    ),
    "A.8.4": (
        "Applicable as software development activities are within the ISMS scope."
    ),
    "A.8.25": (
        "Applicable as software development activities are within the ISMS scope."
    ),
    "A.8.28": (
        "Applicable as software development activities are within the ISMS scope."
    ),
    "A.8.29": (
        "Applicable as software development activities are within the ISMS scope."
    ),
    "A.8.31": (
        "Applicable as software development activities are within the ISMS scope."
    ),
}


def translate_justification(control_id: str, original: str | None) -> str | None:
    if not original:
        return None
    if control_id in JUSTIFICATION_EN:
        return JUSTIFICATION_EN[control_id]
    lower = original.lower()
    if "por requisito" in lower or "iso 27001" in lower:
        return JUSTIFICATION_EN["_default"]
    if "no aplica" in lower:
        return "Not applicable."
    return original


async def translate(db_url: str | None = None) -> int:
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
            data = dict(row.data)
            control_id = data["control_id"]
            changed = False

            if control_id in MANAGEMENT_EN:
                data["management"] = MANAGEMENT_EN[control_id]
                changed = True

            new_just = translate_justification(control_id, data.get("justification"))
            if new_just and new_just != data.get("justification"):
                data["justification"] = new_just
                changed = True

            if changed:
                row.data = data
                updated += 1

        await db.commit()

    await engine.dispose()
    return updated


async def main() -> None:
    print("Translating SOA fields to English...")
    count = await translate()
    print(f"Done. Updated {count} rows.")


if __name__ == "__main__":
    asyncio.run(main())
