"""Export Capacity management.xlsx 'General view' tab to capacity_seed.json.

Run locally where the xlsx file exists:
    python scripts/export_capacity_xlsx_to_json.py temp/Capacity\ management.xlsx

Outputs: capacity_seed.json in the current directory.
"""

import json
import sys
from datetime import date, timedelta

import openpyxl

# Manual mapping: spreadsheet name → user email.
# Fill in before running. Names not in this dict are skipped with a warning.
NAME_TO_EMAIL: dict[str, str] = {
    "Adam Trincas": "adam.trincas@vizzuality.com",
    "Adélaïde Cadioux": "adelaide.cadioux@vizzuality.com",
    "Alex Larrañaga": "alex.larranaga@vizzuality.com",
    "Alicia Arenzana": "alicia.arenzana@vizzuality.com",
    "Andrea Rota": "andrea.rota@vizzuality.com",
    "Andreia Ribeiro": "andreia.ribeiro@vizzuality.com",
    "Andrés Gonzalez": "andres.gonzalez@vizzuality.com",
    "Angel Arcones": "angel.arcones@vizzuality.com",
    "Angela Minto": "angela.minto@vizzuality.com",
    "Ariadna Ariza": "ariadna.ariza@vizzuality.com",
    "Clara Linos": "clara.linos@vizzuality.com",
    "Clement Prodhomme": "clement.prodhomme@vizzuality.com",
    "Cristina Jaramago": "cristina.jaramago@vizzuality.com",
    "Daniel Caso": "daniel.caso@vizzuality.com",
    "Edgar Espinoza": "edgar.espinoza@vizzuality.com",
    "Elena Palao": "elena.palao@vizzuality.com",
    "Iker Sanchez": "iker.sanchez@vizzuality.com",
    "Irene Rodriguez": "irene.rodriguez@vizzuality.com",
    "Jacinta Hamley": "jacinta.hamley@vizzuality.com",
    "Javi Lois": "javier.lois@vizzuality.com",
    "Kevin Sánchez": "kevin.sanchez@vizzuality.com",
    "Laura Riera": "laura.riera@vizzuality.com",
    "Lyubov Pencheva": "lyubov.pencheva@vizzuality.com",
    "María Luena": "maria.luena@vizzuality.com",
    "María Relea": "maria.relea@vizzuality.com",
    "Miguel Barrenechea": "miguel.barrenechea@vizzuality.com",
    "Biel Stela": "biel.stela@vizzuality.com",
    "Cecilia Fili": "cecilia.fili@vizzuality.com",
    "Miguel Mendoza": "miguel.mendoza@vizzuality.com",
    "Mike Harfoot": "mike.harfoot@vizzuality.com",
    "Santiago Ferrer": "santiago.ferrer@vizzuality.com",
    "Sergio Estella": "sergio.estella@vizzuality.com",
    "Sofia Aldabet": "sofia.aldabet@vizzuality.com",
    "Susana Romao": "susana.romao@vizzuality.com",
}

# Spreadsheet project names → DB project names (where they differ)
PROJECT_NAME_MAPPING: dict[str, str] = {
    "Amazonia 360": "Amazonia360 - MVP",
    "CCSA": "Climate Smart Map",
    "Catalyse": "CATALYSE",
    "Climate Watch": "Climate Watch 2026 Maintenance Contract",
    "ECCC": "ECCC HJBL",
    "ESA-GDA": "ESA GDA Comms 2023 - 2027",
    "FHWPC": "FHWPC Implementation phase",
    "Global Rangelands": "Global Rangelands Data Platform (GRASS) - MVP",
    "ICIMOD": "ICIMOD web discovery",
    "IDB": "IDB ESGeoHub",
    "IIASA": "IIASA Scenario Compass Platform ",
    "Landscape Capital Explorer": "Landscape Capital Explorer - Implementation Phase",
    "MIRACA": "HE MIRACA",
    "Mars": "Mars MGIS Maintenance 2025",
    "Marxan": "Marxan maintenance 2025-2028",
    "Open Earth Monitor (OEM)": "Open Earth Monitor ",
    "South Sudán": "South Sudan Visualization Pilot",
    "Unesco": "UNESCO WHOMP",
    "WB Country Workspace": "World bank country workspace MVP design",
    "Wetlands - Gap Map": "Wetlands gap map",
}

DATA_START_ROW = 16
PROJECT_COL = 1
ROLE_COL = 2
NAME_COL = 3
WEEK_START_COL = 4

# Columns 4-11 use "days" format (1-5), columns 12+ use percentage (0-100+)
DAYS_FORMAT_END_COL = 11


def iso_week_to_monday(year: int, week_num: int) -> date:
    """Convert ISO year + week number to the Monday of that week."""
    jan1 = date(year, 1, 1)
    # Find the Monday of ISO week 1
    day_of_week = jan1.isoweekday()
    if day_of_week <= 4:
        iso_week1_monday = jan1 - timedelta(days=day_of_week - 1)
    else:
        iso_week1_monday = jan1 + timedelta(days=8 - day_of_week)
    return iso_week1_monday + timedelta(weeks=week_num - 1)


def main(xlsx_path: str) -> None:
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb["General view"]

    # Read week numbers from row 12 and month names from row 14
    week_info: dict[int, dict] = {}
    current_year = None
    month_to_year: dict[str, int] = {}

    # Read month headers (row 14) to determine year boundaries
    for col in range(WEEK_START_COL, ws.max_column + 1):
        month_name = ws.cell(row=14, column=col).value
        if month_name:
            # Months Nov, Dec → 2025; Jan onwards → 2026 (adjust as needed)
            if month_name in ("November", "December"):
                month_to_year[month_name] = 2025
                current_year = 2025
            else:
                month_to_year[month_name] = 2026
                current_year = 2026

    # Build week_num → Monday mapping
    current_year = 2025  # Start year for first columns
    for col in range(WEEK_START_COL, ws.max_column + 1):
        week_num_val = ws.cell(row=12, column=col).value
        month_val = ws.cell(row=14, column=col).value
        if month_val and month_val in month_to_year:
            current_year = month_to_year[month_val]
        if week_num_val is not None:
            week_num = int(week_num_val)
            # Week 1-2 after week 52 means year rollover
            if week_num < 10 and current_year == 2025:
                current_year = 2026
            monday = iso_week_to_monday(current_year, week_num)
            week_info[col] = {
                "week_num": week_num,
                "monday": monday,
                "is_days_format": col <= DAYS_FORMAT_END_COL,
            }

    # Read data rows
    records: list[dict] = []
    skipped_names: set[str] = set()

    for row in range(DATA_START_ROW, ws.max_row + 1):
        project_name = ws.cell(row=row, column=PROJECT_COL).value
        person_name = ws.cell(row=row, column=NAME_COL).value

        if not person_name:
            continue

        person_name = str(person_name).strip()
        email = NAME_TO_EMAIL.get(person_name)
        if not email:
            skipped_names.add(person_name)
            continue

        project_name = str(project_name).strip() if project_name else None
        if not project_name:
            continue
        project_name = PROJECT_NAME_MAPPING.get(project_name, project_name)

        for col, info in week_info.items():
            val = ws.cell(row=row, column=col).value
            if val is None or val == "" or str(val).lower() == "x":
                continue

            try:
                num = float(val)
            except (ValueError, TypeError):
                continue

            if num <= 0:
                continue

            # Convert days to percentage if old format
            if info["is_days_format"]:
                percentage = int(num * 20)
            else:
                percentage = int(num)

            if percentage < 1:
                continue

            records.append({
                "project_name": project_name,
                "user_email": email,
                "week_start": info["monday"].isoformat(),
                "percentage": min(percentage, 200),
            })

    # Write output
    output_path = "capacity_seed.json"
    with open(output_path, "w") as f:
        json.dump(records, f, indent=2)

    print(f"Exported {len(records)} records to {output_path}")
    if skipped_names:
        print(f"Skipped names (no email mapping): {sorted(skipped_names)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <path-to-xlsx>")
        sys.exit(1)
    main(sys.argv[1])
