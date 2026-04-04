"""Seed the 17 predefined ISO registry types.

Run: python -m scripts.seed_registry_types
Idempotent: skips existing types by slug.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import Base  # noqa: F401 — ensures all models are registered
from app.core.models.user import UserDB  # noqa: F401
from app.modules.iso_docs.models.registry_type import RegistryTypeDB

UNDER_REVIEW = "Under Review"
VERY_HIGH = "Very High"
VERY_LOW = "Very Low"

ORIGIN_OPTIONS = ["SWOT Analysis", "Stakeholder Expectations", "SWOT & Stakeholder Expectations", "Other"]
PROCESS_OPTIONS = [
    "Risk & Opportunity Analysis and Organization Context (4)",
    "Leadership (5)", "Quality Planning (6)", "Human Resources (7)",
    "Document Information Control (7)", "Procurement and Outsourcing (7)",
    "Equipment Maintenance (7)", "Order and Offer Management (8)",
    "Personnel Selection (8)", "Service Delivery (8)",
    "Performance Evaluation (9)", "Improvement (10)",
]
ACTION_TYPE_OPTIONS = ["Objective", "Improvement Action", "Training", "None", "Maintain Current Management"]
CLOSURE_OPTIONS = ["Satisfactory", "Improvable", "Unsatisfactory"]

REGISTRY_TYPES = [
    {
        "name": "Asset Inventory",
        "slug": "asset-inventory",
        "description": "Information assets: hardware, software, data, people, facilities",
        "is_yearly": False,
        "schema": [
            {"key": "asset_id", "label": "Asset ID", "type": "string", "required": True, "width": 100},
            {"key": "name", "label": "Asset Name", "type": "string", "required": True, "width": 200},
            {"key": "category", "label": "Category", "type": "select", "required": True, "options": ["Hardware", "Software", "Data", "People", "Facilities", "Network", "Cloud Service"], "width": 130},
            {"key": "description", "label": "Description", "type": "string", "required": False, "width": 250},
            {"key": "owner", "label": "Owner", "type": "string", "required": True, "width": 150},
            {"key": "custodian", "label": "Custodian", "type": "string", "required": False, "width": 150},
            {"key": "location", "label": "Location", "type": "string", "required": False, "width": 150},
            {"key": "classification", "label": "Classification", "type": "select", "required": True, "options": ["Public", "Internal", "Confidential", "Restricted"], "width": 120},
            {"key": "criticality", "label": "Criticality", "type": "select", "required": True, "options": ["Low", "Medium", "High", "Critical"], "width": 100},
            {"key": "acquisition_date", "label": "Acquisition Date", "type": "date", "required": False, "width": 130},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Active", "Decommissioned", UNDER_REVIEW], "width": 120},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Risk Register",
        "slug": "risk-register",
        "description": "Risk assessment and treatment: identified risks from SWOT analysis and stakeholder expectations, rated by probability (1-3) and impact (1-3) with auto-calculated evaluation (P×I), action plans, and closure tracking. Yearly registry aligned to audit cycles. ISO 27001 clause 6.1, ISO 9001 clause 6.1.",
        "is_yearly": True,
        "schema": [
            {"key": "risk_id", "label": "Risk ID", "type": "string", "required": True, "width": 80},
            {"key": "analysis_date", "label": "Analysis Date", "type": "date", "required": False, "width": 120},
            {"key": "origin", "label": "Origin", "type": "select", "required": True, "options": ORIGIN_OPTIONS, "width": 180},
            {"key": "related_process", "label": "Related Process", "type": "select", "required": False, "options": PROCESS_OPTIONS, "width": 250},
            {"key": "description", "label": "Description", "type": "string", "required": True, "width": 350},
            {"key": "probability", "label": "Probability", "type": "number", "required": True, "width": 90},
            {"key": "impact", "label": "Impact", "type": "number", "required": True, "width": 80},
            {"key": "evaluation", "label": "Evaluation (P×I)", "type": "computed", "width": 140, "formula": {"operation": "multiply", "fields": ["probability", "impact"]}, "conditional_format": [{"min": 1, "max": 1, "color": "#86efac", "label": "Trivial"}, {"min": 2, "max": 2, "color": "#22c55e", "label": "Tolerable"}, {"min": 3, "max": 4, "color": "#eab308", "label": "Moderate"}, {"min": 6, "max": 6, "color": "#f97316", "label": "Important"}, {"min": 9, "max": 9, "color": "#ef4444", "label": "Critical"}]},
            {"key": "action_type", "label": "Action Type", "type": "select", "required": False, "options": ACTION_TYPE_OPTIONS, "width": 180},
            {"key": "action_description", "label": "Action Description", "type": "string", "required": False, "width": 350},
            {"key": "system_reference", "label": "System Reference", "type": "string", "required": False, "width": 150},
            {"key": "closure", "label": "Closure", "type": "select", "required": False, "options": CLOSURE_OPTIONS, "width": 120},
        ],
    },
    {
        "name": "Opportunity Register",
        "slug": "opportunity-register",
        "description": "Opportunity assessment and prioritization: identified opportunities from SWOT analysis and stakeholder expectations, rated by benefit (1-10) and effort (1-10, where 10=low effort) with auto-calculated evaluation (B×E), action plans, and closure tracking. Yearly registry aligned to audit cycles. ISO 27001 clause 6.1, ISO 9001 clause 6.1.",
        "is_yearly": True,
        "schema": [
            {"key": "opp_id", "label": "Opportunity ID", "type": "string", "required": True, "width": 80},
            {"key": "analysis_date", "label": "Analysis Date", "type": "date", "required": False, "width": 120},
            {"key": "origin", "label": "Origin", "type": "select", "required": True, "options": ORIGIN_OPTIONS, "width": 180},
            {"key": "related_process", "label": "Related Process", "type": "select", "required": False, "options": PROCESS_OPTIONS, "width": 250},
            {"key": "description", "label": "Description", "type": "string", "required": True, "width": 350},
            {"key": "benefit", "label": "Benefit", "type": "number", "required": True, "width": 80},
            {"key": "effort", "label": "Effort", "type": "number", "required": True, "width": 80},
            {"key": "evaluation", "label": "Evaluation (B×E)", "type": "computed", "width": 140, "formula": {"operation": "multiply", "fields": ["benefit", "effort"]}, "conditional_format": [{"min": 1, "max": 49, "color": "#22c55e", "label": "Low"}, {"min": 50, "max": 74, "color": "#f97316", "label": "High"}, {"min": 75, "max": 100, "color": "#ef4444", "label": "Critical"}]},
            {"key": "action_type", "label": "Action Type", "type": "select", "required": False, "options": ACTION_TYPE_OPTIONS, "width": 180},
            {"key": "action_description", "label": "Action Description", "type": "string", "required": False, "width": 350},
            {"key": "system_reference", "label": "System Reference", "type": "string", "required": False, "width": 150},
            {"key": "closure", "label": "Closure", "type": "select", "required": False, "options": CLOSURE_OPTIONS, "width": 120},
        ],
    },
    {
        "name": "Statement of Applicability",
        "slug": "statement-of-applicability",
        "description": "Annex A controls applicability and implementation status",
        "is_yearly": False,
        "schema": [
            {"key": "control_id", "label": "Control ID", "type": "string", "required": True, "width": 100},
            {"key": "control_name", "label": "Control Name", "type": "string", "required": True, "width": 200},
            {"key": "applicable", "label": "Applicable", "type": "boolean", "required": True, "width": 90},
            {"key": "justification", "label": "Justification", "type": "string", "required": False, "width": 250},
            {"key": "implementation_status", "label": "Implementation Status", "type": "select", "required": True, "options": ["Implemented", "Partially Implemented", "Planned", "Not Implemented", "N/A"], "width": 160},
            {"key": "responsible", "label": "Responsible", "type": "string", "required": False, "width": 150},
            {"key": "evidence", "label": "Evidence/Reference", "type": "string", "required": False, "width": 200},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Incident Register",
        "slug": "incident-register",
        "description": "Security incidents, data breaches, and near-misses",
        "is_yearly": True,
        "schema": [
            {"key": "incident_id", "label": "Incident ID", "type": "string", "required": True, "width": 100},
            {"key": "title", "label": "Title", "type": "string", "required": True, "width": 200},
            {"key": "date_reported", "label": "Date Reported", "type": "date", "required": True, "width": 130},
            {"key": "date_occurred", "label": "Date Occurred", "type": "date", "required": False, "width": 130},
            {"key": "reporter", "label": "Reporter", "type": "string", "required": True, "width": 150},
            {"key": "severity", "label": "Severity", "type": "select", "required": True, "options": ["Low", "Medium", "High", "Critical"], "width": 100},
            {"key": "category", "label": "Category", "type": "select", "required": True, "options": ["Data Breach", "Malware", "Phishing", "Unauthorized Access", "System Failure", "Physical", "Human Error", "Other"], "width": 140},
            {"key": "description", "label": "Description", "type": "string", "required": True, "width": 300},
            {"key": "affected_systems", "label": "Affected Systems", "type": "string", "required": False, "width": 200},
            {"key": "root_cause", "label": "Root Cause", "type": "string", "required": False, "width": 200},
            {"key": "corrective_action", "label": "Corrective Action", "type": "string", "required": False, "width": 250},
            {"key": "date_resolved", "label": "Date Resolved", "type": "date", "required": False, "width": 130},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Open", "Investigating", "Resolved", "Closed"], "width": 120},
            {"key": "lessons_learned", "label": "Lessons Learned", "type": "string", "required": False, "width": 250},
        ],
    },
    {
        "name": "Corrective Action Register",
        "slug": "corrective-action-register",
        "description": "Non-conformities, corrective actions, and effectiveness reviews",
        "is_yearly": True,
        "schema": [
            {"key": "car_id", "label": "CAR ID", "type": "string", "required": True, "width": 100},
            {"key": "source", "label": "Source", "type": "select", "required": True, "options": ["Audit", "Incident", "Management Review", "Risk Assessment", "Customer Complaint", "Other"], "width": 130},
            {"key": "date_raised", "label": "Date Raised", "type": "date", "required": True, "width": 130},
            {"key": "non_conformity", "label": "Non-Conformity", "type": "string", "required": True, "width": 300},
            {"key": "root_cause", "label": "Root Cause", "type": "string", "required": False, "width": 250},
            {"key": "corrective_action", "label": "Corrective Action", "type": "string", "required": True, "width": 250},
            {"key": "responsible", "label": "Responsible", "type": "string", "required": True, "width": 150},
            {"key": "target_date", "label": "Target Date", "type": "date", "required": True, "width": 130},
            {"key": "completion_date", "label": "Completion Date", "type": "date", "required": False, "width": 130},
            {"key": "effectiveness_review", "label": "Effectiveness Review", "type": "string", "required": False, "width": 250},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Open", "In Progress", "Completed", "Verified", "Closed"], "width": 120},
        ],
    },
    {
        "name": "Audit Plan & Results",
        "slug": "audit-plan-results",
        "description": "Internal audit schedule, findings, and follow-up",
        "is_yearly": True,
        "schema": [
            {"key": "audit_id", "label": "Audit ID", "type": "string", "required": True, "width": 100},
            {"key": "audit_type", "label": "Audit Type", "type": "select", "required": True, "options": ["Internal", "External", "Surveillance", "Certification"], "width": 120},
            {"key": "scope", "label": "Scope / Area", "type": "string", "required": True, "width": 200},
            {"key": "clauses", "label": "Clauses / Controls", "type": "string", "required": False, "width": 200},
            {"key": "planned_date", "label": "Planned Date", "type": "date", "required": True, "width": 130},
            {"key": "actual_date", "label": "Actual Date", "type": "date", "required": False, "width": 130},
            {"key": "auditor", "label": "Auditor", "type": "string", "required": True, "width": 150},
            {"key": "findings_count", "label": "Findings", "type": "number", "required": False, "width": 80},
            {"key": "nc_major", "label": "Major NCs", "type": "number", "required": False, "width": 80},
            {"key": "nc_minor", "label": "Minor NCs", "type": "number", "required": False, "width": 80},
            {"key": "observations", "label": "Observations", "type": "number", "required": False, "width": 80},
            {"key": "summary", "label": "Summary", "type": "string", "required": False, "width": 300},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Planned", "In Progress", "Completed", "Follow-up"], "width": 120},
        ],
    },
    {
        "name": "Supplier Register",
        "slug": "supplier-register",
        "description": "Third-party suppliers and service providers with security assessments",
        "is_yearly": False,
        "schema": [
            {"key": "supplier_name", "label": "Supplier Name", "type": "string", "required": True, "width": 200},
            {"key": "service_type", "label": "Service Type", "type": "string", "required": True, "width": 200},
            {"key": "contact", "label": "Contact", "type": "string", "required": False, "width": 150},
            {"key": "data_access", "label": "Data Access", "type": "select", "required": True, "options": ["None", "Limited", "Full"], "width": 100},
            {"key": "criticality", "label": "Criticality", "type": "select", "required": True, "options": ["Low", "Medium", "High", "Critical"], "width": 100},
            {"key": "contract_start", "label": "Contract Start", "type": "date", "required": False, "width": 130},
            {"key": "contract_end", "label": "Contract End", "type": "date", "required": False, "width": 130},
            {"key": "last_assessment", "label": "Last Assessment", "type": "date", "required": False, "width": 130},
            {"key": "assessment_result", "label": "Assessment Result", "type": "select", "required": False, "options": ["Pass", "Conditional", "Fail", "Pending"], "width": 130},
            {"key": "certifications", "label": "Certifications", "type": "string", "required": False, "width": 200},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Active", UNDER_REVIEW, "Suspended", "Terminated"], "width": 120},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Training Register",
        "slug": "training-register",
        "description": "Security awareness training records",
        "is_yearly": True,
        "schema": [
            {"key": "employee_name", "label": "Employee Name", "type": "string", "required": True, "width": 180},
            {"key": "department", "label": "Department", "type": "string", "required": False, "width": 150},
            {"key": "training_type", "label": "Training Type", "type": "select", "required": True, "options": ["Security Awareness", "ISMS Procedures", "Incident Response", "Data Protection", "Phishing Simulation", "Technical", "Other"], "width": 150},
            {"key": "training_name", "label": "Training Name", "type": "string", "required": True, "width": 200},
            {"key": "date_completed", "label": "Date Completed", "type": "date", "required": True, "width": 130},
            {"key": "provider", "label": "Provider", "type": "string", "required": False, "width": 150},
            {"key": "result", "label": "Result", "type": "select", "required": True, "options": ["Pass", "Fail", "Attended", "N/A"], "width": 100},
            {"key": "next_due", "label": "Next Due", "type": "date", "required": False, "width": 130},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Change Management Register",
        "slug": "change-management-register",
        "description": "Changes to the ISMS, infrastructure, and processes",
        "is_yearly": True,
        "schema": [
            {"key": "change_id", "label": "Change ID", "type": "string", "required": True, "width": 100},
            {"key": "title", "label": "Title", "type": "string", "required": True, "width": 200},
            {"key": "description", "label": "Description", "type": "string", "required": True, "width": 300},
            {"key": "type", "label": "Type", "type": "select", "required": True, "options": ["ISMS", "Infrastructure", "Application", "Process", "Policy", "Other"], "width": 120},
            {"key": "requester", "label": "Requester", "type": "string", "required": True, "width": 150},
            {"key": "date_requested", "label": "Date Requested", "type": "date", "required": True, "width": 130},
            {"key": "risk_assessment", "label": "Risk Assessment", "type": "select", "required": True, "options": ["Low", "Medium", "High"], "width": 120},
            {"key": "approver", "label": "Approver", "type": "string", "required": False, "width": 150},
            {"key": "date_approved", "label": "Date Approved", "type": "date", "required": False, "width": 130},
            {"key": "date_implemented", "label": "Date Implemented", "type": "date", "required": False, "width": 140},
            {"key": "rollback_plan", "label": "Rollback Plan", "type": "boolean", "required": True, "width": 100},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Requested", "Approved", "Implementing", "Completed", "Rejected", "Rolled Back"], "width": 130},
        ],
    },
    {
        "name": "Business Continuity Plan",
        "slug": "business-continuity-plan",
        "description": "BCP scenarios, recovery procedures, and test results",
        "is_yearly": False,
        "schema": [
            {"key": "scenario", "label": "Scenario", "type": "string", "required": True, "width": 200},
            {"key": "description", "label": "Description", "type": "string", "required": True, "width": 300},
            {"key": "impact_level", "label": "Impact Level", "type": "select", "required": True, "options": ["Low", "Medium", "High", "Critical"], "width": 100},
            {"key": "rto", "label": "RTO", "type": "string", "required": True, "width": 100},
            {"key": "rpo", "label": "RPO", "type": "string", "required": True, "width": 100},
            {"key": "recovery_procedure", "label": "Recovery Procedure", "type": "string", "required": True, "width": 250},
            {"key": "responsible_team", "label": "Responsible Team", "type": "string", "required": True, "width": 150},
            {"key": "last_tested", "label": "Last Tested", "type": "date", "required": False, "width": 130},
            {"key": "test_result", "label": "Test Result", "type": "select", "required": False, "options": ["Pass", "Partial", "Fail", "Not Tested"], "width": 100},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Access Control Register",
        "slug": "access-control-register",
        "description": "System access rights, privileges, and review status",
        "is_yearly": False,
        "schema": [
            {"key": "system", "label": "System / Application", "type": "string", "required": True, "width": 200},
            {"key": "user_name", "label": "User", "type": "string", "required": True, "width": 150},
            {"key": "role", "label": "Role", "type": "string", "required": True, "width": 150},
            {"key": "access_level", "label": "Access Level", "type": "select", "required": True, "options": ["Read Only", "Standard", "Privileged", "Admin"], "width": 120},
            {"key": "granted_date", "label": "Granted Date", "type": "date", "required": True, "width": 130},
            {"key": "granted_by", "label": "Granted By", "type": "string", "required": False, "width": 150},
            {"key": "last_review", "label": "Last Review", "type": "date", "required": False, "width": 130},
            {"key": "next_review", "label": "Next Review", "type": "date", "required": False, "width": 130},
            {"key": "mfa_enabled", "label": "MFA Enabled", "type": "boolean", "required": True, "width": 90},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Active", "Suspended", "Revoked"], "width": 100},
        ],
    },
    {
        "name": "Legal & Regulatory Register",
        "slug": "legal-regulatory-register",
        "description": "Applicable laws, regulations, and contractual obligations",
        "is_yearly": False,
        "schema": [
            {"key": "requirement", "label": "Requirement", "type": "string", "required": True, "width": 200},
            {"key": "type", "label": "Type", "type": "select", "required": True, "options": ["Law", "Regulation", "Standard", "Contract", "Policy"], "width": 100},
            {"key": "jurisdiction", "label": "Jurisdiction", "type": "string", "required": False, "width": 150},
            {"key": "description", "label": "Description", "type": "string", "required": True, "width": 300},
            {"key": "applicable_to", "label": "Applicable To", "type": "string", "required": False, "width": 200},
            {"key": "compliance_status", "label": "Compliance Status", "type": "select", "required": True, "options": ["Compliant", "Partially Compliant", "Non-Compliant", UNDER_REVIEW], "width": 140},
            {"key": "responsible", "label": "Responsible", "type": "string", "required": True, "width": 150},
            {"key": "last_reviewed", "label": "Last Reviewed", "type": "date", "required": False, "width": 130},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Communication Register",
        "slug": "communication-register",
        "description": "Internal and external ISMS communications",
        "is_yearly": True,
        "schema": [
            {"key": "subject", "label": "Subject", "type": "string", "required": True, "width": 200},
            {"key": "type", "label": "Type", "type": "select", "required": True, "options": ["Internal", "External"], "width": 100},
            {"key": "audience", "label": "Audience", "type": "string", "required": True, "width": 200},
            {"key": "responsible", "label": "Responsible", "type": "string", "required": True, "width": 150},
            {"key": "frequency", "label": "Frequency", "type": "select", "required": True, "options": ["One-time", "Monthly", "Quarterly", "Annual", "As Needed"], "width": 110},
            {"key": "method", "label": "Method", "type": "string", "required": False, "width": 150},
            {"key": "last_communicated", "label": "Last Communicated", "type": "date", "required": False, "width": 140},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Management Review Register",
        "slug": "management-review-register",
        "description": "Management review meetings, inputs, decisions, and actions",
        "is_yearly": True,
        "schema": [
            {"key": "review_date", "label": "Review Date", "type": "date", "required": True, "width": 130},
            {"key": "attendees", "label": "Attendees", "type": "string", "required": True, "width": 250},
            {"key": "topics", "label": "Topics Covered", "type": "string", "required": True, "width": 300},
            {"key": "decisions", "label": "Decisions", "type": "string", "required": True, "width": 300},
            {"key": "actions", "label": "Action Items", "type": "string", "required": False, "width": 300},
            {"key": "responsible", "label": "Responsible", "type": "string", "required": False, "width": 150},
            {"key": "due_date", "label": "Due Date", "type": "date", "required": False, "width": 130},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Completed", "Actions Pending", "Overdue"], "width": 120},
        ],
    },
    {
        "name": "Document Control Register",
        "slug": "document-control-register",
        "description": "Controlled documents, versions, and approval status",
        "is_yearly": False,
        "schema": [
            {"key": "doc_id", "label": "Document ID", "type": "string", "required": True, "width": 100},
            {"key": "title", "label": "Title", "type": "string", "required": True, "width": 200},
            {"key": "category", "label": "Category", "type": "select", "required": True, "options": ["Policy", "Procedure", "Work Instruction", "Form", "Record", "Plan", "Report"], "width": 130},
            {"key": "version", "label": "Version", "type": "string", "required": True, "width": 80},
            {"key": "author", "label": "Author", "type": "string", "required": True, "width": 150},
            {"key": "reviewer", "label": "Reviewer", "type": "string", "required": False, "width": 150},
            {"key": "approver", "label": "Approver", "type": "string", "required": False, "width": 150},
            {"key": "effective_date", "label": "Effective Date", "type": "date", "required": True, "width": 130},
            {"key": "next_review", "label": "Next Review", "type": "date", "required": False, "width": 130},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Draft", UNDER_REVIEW, "Approved", "Obsolete"], "width": 120},
            {"key": "distribution", "label": "Distribution", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Interested Parties Register",
        "slug": "interested-parties-register",
        "description": "Stakeholders, their requirements, and expectations",
        "is_yearly": False,
        "schema": [
            {"key": "party_name", "label": "Interested Party", "type": "string", "required": True, "width": 200},
            {"key": "type", "label": "Type", "type": "select", "required": True, "options": ["Customer", "Employee", "Regulator", "Partner", "Supplier", "Shareholder", "Community"], "width": 120},
            {"key": "requirements", "label": "Requirements & Expectations", "type": "string", "required": True, "width": 300},
            {"key": "relevance", "label": "Relevance to ISMS", "type": "string", "required": False, "width": 250},
            {"key": "influence", "label": "Influence Level", "type": "select", "required": True, "options": ["Low", "Medium", "High"], "width": 100},
            {"key": "contact", "label": "Contact", "type": "string", "required": False, "width": 150},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Purchases Register",
        "slug": "purchases-register",
        "description": "Security-relevant purchases, subscriptions, and licenses",
        "is_yearly": True,
        "schema": [
            {"key": "purchase_id", "label": "Purchase ID", "type": "string", "required": True, "width": 100},
            {"key": "description", "label": "Description", "type": "string", "required": True, "width": 250},
            {"key": "category", "label": "Category", "type": "select", "required": True, "options": ["Hardware", "Software License", "SaaS Subscription", "Service", "Training", "Consulting", "Other"], "width": 140},
            {"key": "supplier", "label": "Supplier", "type": "string", "required": True, "width": 150},
            {"key": "amount", "label": "Amount (EUR)", "type": "number", "required": True, "width": 120},
            {"key": "date", "label": "Date", "type": "date", "required": True, "width": 130},
            {"key": "requester", "label": "Requester", "type": "string", "required": True, "width": 150},
            {"key": "approver", "label": "Approver", "type": "string", "required": False, "width": 150},
            {"key": "recurring", "label": "Recurring", "type": "boolean", "required": False, "width": 80},
            {"key": "renewal_date", "label": "Renewal Date", "type": "date", "required": False, "width": 130},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Pending", "Approved", "Delivered", "Cancelled"], "width": 110},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
]


async def seed(db_url: str | None = None) -> int:
    url = db_url or get_settings().database_url
    engine = create_async_engine(url)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    created = 0
    async with session_maker() as db:
        for rt_data in REGISTRY_TYPES:
            existing = await db.execute(
                select(RegistryTypeDB).where(RegistryTypeDB.slug == rt_data["slug"])
            )
            if existing.scalar_one_or_none():
                print(f"  skip: {rt_data['name']} (exists)")
                continue

            rt = RegistryTypeDB(
                name=rt_data["name"],
                slug=rt_data["slug"],
                description=rt_data["description"],
                is_yearly=rt_data["is_yearly"],
                schema=rt_data["schema"],
            )
            db.add(rt)
            created += 1
            print(f"  create: {rt_data['name']}")

        await db.commit()

    await engine.dispose()
    return created


async def main() -> None:
    print("Seeding registry types...")
    created = await seed()
    print(f"Done. Created {created} registry types.")


if __name__ == "__main__":
    asyncio.run(main())
