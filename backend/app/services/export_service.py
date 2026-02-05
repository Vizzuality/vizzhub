"""XLSX export service for project scorecard data."""

from io import BytesIO
from uuid import UUID

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig
from app.models.metrics import MetricsCreate, MetricsDB
from app.models.project import ProjectDB
from app.services.export_definitions import get_metric_rows
from app.services.export_helpers import (
    THIN_BORDER,
    apply_header_style,
    apply_row_style,
    apply_traffic_light,
    create_methodology_sheet,
    format_month_header,
    freeze_panes,
    set_column_widths,
)
from app.services.score_computation import ScoreComputationService


class ExportService:
    """Generates XLSX exports for scorecard data."""

    def __init__(self, config: ScoringConfig):
        self.config = config
        self.score_service = ScoreComputationService(config)

    async def export_project_detail(
        self,
        db: AsyncSession,
        project_id: str,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
        snapshot_type: str = "cumulative",
    ) -> BytesIO:
        """Generate project detail XLSX with Summary, Metrics, and Methodology sheets."""
        project = await self._get_project(db, project_id)
        periods = self._generate_periods(start_year, start_month, end_year, end_month)
        metrics_by_period = await self._get_metrics_by_period(
            db, project_id, periods, snapshot_type
        )
        scores_by_period = self._compute_scores(metrics_by_period)

        wb = Workbook()

        self._build_summary_sheet(wb, project, periods, scores_by_period, snapshot_type)
        self._build_metrics_sheet(wb, periods, metrics_by_period, scores_by_period)
        create_methodology_sheet(wb, self.config)

        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        return self._save_to_bytes(wb)

    async def export_global_dashboard(
        self,
        db: AsyncSession,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
        snapshot_type: str = "cumulative",
    ) -> BytesIO:
        """Generate global dashboard XLSX with Overview, Dimensions, and Methodology sheets."""
        projects = await self._get_all_projects(db)
        periods = self._generate_periods(start_year, start_month, end_year, end_month)

        project_data: list[dict] = []
        for project in projects:
            metrics_by_period = await self._get_metrics_by_period(
                db, str(project.id), periods, snapshot_type
            )
            scores_by_period = self._compute_scores(metrics_by_period)
            project_data.append({
                "project": project,
                "scores": scores_by_period,
            })

        wb = Workbook()

        self._build_overview_sheet(wb, project_data, periods)
        self._build_dimensions_sheet(wb, project_data, periods)
        create_methodology_sheet(wb, self.config)

        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        return self._save_to_bytes(wb)

    # --- Data fetching ---

    async def _get_project(self, db: AsyncSession, project_id: str) -> ProjectDB:
        """Fetch a single project by ID."""
        project_uuid = UUID(project_id) if isinstance(project_id, str) else project_id
        result = await db.execute(
            select(ProjectDB).where(ProjectDB.id == project_uuid)
        )
        return result.scalar_one()

    async def _get_all_projects(self, db: AsyncSession) -> list[ProjectDB]:
        """Fetch all projects ordered by name."""
        result = await db.execute(select(ProjectDB).order_by(ProjectDB.name))
        return list(result.scalars().all())

    async def _get_metrics_by_period(
        self,
        db: AsyncSession,
        project_id: str,
        periods: list[tuple[int, int]],
        snapshot_type: str,
    ) -> dict[tuple[int, int], MetricsDB | None]:
        """Fetch metrics for each period, returns dict of (year, month) -> MetricsDB."""
        project_uuid = UUID(project_id) if isinstance(project_id, str) else project_id
        result: dict[tuple[int, int], MetricsDB | None] = {p: None for p in periods}
        if not periods:
            return result

        query = (
            select(MetricsDB)
            .where(MetricsDB.project_id == project_uuid)
            .where(MetricsDB.snapshot_type == snapshot_type)
            .where(
                tuple_(MetricsDB.period_year, MetricsDB.period_month).in_(periods)
            )
            .order_by(MetricsDB.created_at.desc())
        )
        res = await db.execute(query)
        for row in res.scalars().all():
            key = (row.period_year, row.period_month)
            if result[key] is None:
                result[key] = row
        return result

    # --- Score computation ---

    def _compute_scores(
        self,
        metrics_by_period: dict[tuple[int, int], MetricsDB | None],
    ) -> dict[tuple[int, int], dict | None]:
        """Compute scores for each period that has metrics."""
        result: dict[tuple[int, int], dict | None] = {}
        for period, metrics_db in metrics_by_period.items():
            if metrics_db is None:
                result[period] = None
                continue
            metrics = MetricsCreate.from_db(metrics_db)
            indicators, scores = self.score_service.compute(
                metrics, sev1_incident=metrics_db.sev1_incident
            )
            result[period] = {
                "indicators": indicators,
                "scores": scores,
            }
        return result

    # --- Sheet builders ---

    def _build_summary_sheet(
        self,
        wb: Workbook,
        project: ProjectDB,
        periods: list[tuple[int, int]],
        scores_by_period: dict,
        snapshot_type: str,
    ) -> None:
        """Build the Summary sheet with project info and final scores per period."""
        ws = wb.active
        ws.title = "Summary"

        info = [
            ("Project", project.name),
            ("Jira Key", project.jira_project_key or "-"),
            ("GitHub Repo", project.github_repo or "-"),
            ("Status", project.status),
            ("Start Date", str(project.start_date) if project.start_date else "-"),
            ("End Date", str(project.end_date) if project.end_date else "-"),
            ("Snapshot Type", snapshot_type),
        ]
        for label, value in info:
            ws.append([label, value])

        ws.append([])

        header = ["Final Score"] + [format_month_header(y, m) for y, m in periods]
        ws.append(header)
        apply_header_style(ws, ws.max_row)

        values = ["Score"]
        for period in periods:
            data = scores_by_period.get(period)
            values.append(data["scores"].score if data else None)
        ws.append(values)

        set_column_widths(ws, {"A": 20, "B": 30})

    def _build_metrics_sheet(
        self,
        wb: Workbook,
        periods: list[tuple[int, int]],
        metrics_by_period: dict,
        scores_by_period: dict,
    ) -> None:
        """Build the Metrics sheet with hierarchical rows and traffic-light coloring."""
        ws = wb.create_sheet("Metrics")
        metric_rows = get_metric_rows()

        header = ["Name", "Description", "Formula", "Target"]
        for year, month in periods:
            header.append(format_month_header(year, month))
        ws.append(header)
        apply_header_style(ws, 1)

        for metric_row in metric_rows:
            level = metric_row["level"]
            indent = "  " * level
            target = self._get_target_for_metric(metric_row["key"], level)

            row_data = [
                f"{indent}{metric_row['name']}",
                metric_row["description"],
                metric_row["formula"],
                target if target else "-",
            ]

            for period in periods:
                value = self._extract_value(
                    metric_row["key"], level, scores_by_period.get(period)
                )
                row_data.append(value)

            ws.append(row_data)
            current_row = ws.max_row
            apply_row_style(ws, current_row, level)

            target_num = self._parse_target(target)
            for col_idx, _period in enumerate(periods, start=5):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.border = THIN_BORDER
                if level <= 1 and target_num is not None:
                    apply_traffic_light(cell, cell.value, target_num)

        widths = {"A": 35, "B": 50, "C": 45, "D": 12}
        for i, _ in enumerate(periods):
            widths[get_column_letter(5 + i)] = 12
        set_column_widths(ws, widths)
        freeze_panes(ws, 2, 5)

    def _build_overview_sheet(
        self,
        wb: Workbook,
        project_data: list[dict],
        periods: list[tuple[int, int]],
    ) -> None:
        """Build the Overview sheet with one row per project and final scores."""
        ws = wb.active
        ws.title = "Overview"

        header = ["Project"] + [format_month_header(y, m) for y, m in periods]
        ws.append(header)
        apply_header_style(ws, 1)

        for item in project_data:
            project = item["project"]
            scores = item["scores"]
            row = [project.name]
            for period in periods:
                data = scores.get(period)
                score = data["scores"].score if data else None
                row.append(score)
            ws.append(row)

            current_row = ws.max_row
            for col_idx in range(2, 2 + len(periods)):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.border = THIN_BORDER
                apply_traffic_light(cell, cell.value, 80)

        widths = {"A": 30}
        for i in range(len(periods)):
            widths[get_column_letter(2 + i)] = 12
        set_column_widths(ws, widths)
        freeze_panes(ws, 2, 2)

    def _build_dimensions_sheet(
        self,
        wb: Workbook,
        project_data: list[dict],
        periods: list[tuple[int, int]],
    ) -> None:
        """Build the Dimensions sheet with per-dimension tables for all projects."""
        ws = wb.create_sheet("Dimensions")

        dim_keys = [
            ("p_time", "P_time \u2014 Schedule"),
            ("p_cost", "P_cost \u2014 Budget"),
            ("p_quality", "P_quality \u2014 Quality"),
            ("p_value", "P_value \u2014 Strategic Value"),
            ("p_satisfaction", "P_satisfaction \u2014 Satisfaction"),
            ("p_flow", "P_flow \u2014 Flow"),
            ("p_engineering", "P_engineering \u2014 Engineering"),
            ("p_risk", "P_risk \u2014 Risk"),
        ]

        for dim_key, dim_name in dim_keys:
            ws.append([dim_name])
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)

            header = ["Project"] + [format_month_header(y, m) for y, m in periods]
            ws.append(header)
            apply_header_style(ws, ws.max_row)

            for item in project_data:
                project = item["project"]
                scores = item["scores"]
                row = [project.name]
                for period in periods:
                    data = scores.get(period)
                    value = None
                    if data:
                        value = getattr(data["scores"].dimensions, dim_key, None)
                    row.append(value)
                ws.append(row)

                current_row = ws.max_row
                for col_idx in range(2, 2 + len(periods)):
                    cell = ws.cell(row=current_row, column=col_idx)
                    cell.border = THIN_BORDER
                    apply_traffic_light(cell, cell.value, 80)

            ws.append([])

        widths = {"A": 30}
        for i in range(len(periods)):
            widths[get_column_letter(2 + i)] = 12
        set_column_widths(ws, widths)

    # --- Helpers ---

    @staticmethod
    def _generate_periods(
        start_year: int, start_month: int, end_year: int, end_month: int
    ) -> list[tuple[int, int]]:
        """Generate a list of (year, month) tuples for the given range."""
        periods: list[tuple[int, int]] = []
        year, month = start_year, start_month
        while (year, month) <= (end_year, end_month):
            periods.append((year, month))
            month += 1
            if month > 12:
                month = 1
                year += 1
        return periods

    def _get_target_for_metric(self, key: str, level: int) -> str | None:
        """Get a display-friendly target string for a metric row."""
        if level == 0:
            return None
        if level == 1:
            return "80"
        try:
            return str(self.config.get_target(key))
        except (KeyError, ValueError):
            return None

    @staticmethod
    def _extract_value(
        key: str, level: int, score_data: dict | None
    ) -> int | float | None:
        """Extract the appropriate value from computed score data."""
        if score_data is None:
            return None
        if level == 0:
            return score_data["scores"].score
        if level == 1:
            return getattr(score_data["scores"].dimensions, key, None)
        return getattr(score_data["indicators"], key, None)

    @staticmethod
    def _parse_target(target: str | None) -> float | None:
        """Parse a target string to a float for traffic-light comparison."""
        if not target or target == "-":
            return None
        try:
            return float(target)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _save_to_bytes(wb: Workbook) -> BytesIO:
        """Save workbook to an in-memory BytesIO buffer."""
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output
