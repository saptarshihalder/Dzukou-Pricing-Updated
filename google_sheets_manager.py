"""Google Sheets database manager for Dzukou pricing system."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import gspread
from google.oauth2.service_account import Credentials


class GoogleSheetsManager:
    """Simplified database wrapper using Google Sheets."""

    def __init__(self, credentials_json: Dict[str, Any], spreadsheet_id: str):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(credentials_json, scopes=scopes)
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)

    def worksheet(self, name: str) -> gspread.Worksheet:
        try:
            return self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=name, rows=1000, cols=20)

    def upload_csv(self, csv_path: str, sheet_name: str) -> int:
        import pandas as pd

        df = pd.read_csv(csv_path, encoding="cp1252" if "Dzukou" in csv_path else "utf-8")
        ws = self.worksheet(sheet_name)
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        return len(df)

    def get_sheet_as_df(self, sheet_name: str):
        import pandas as pd

        ws = self.worksheet(sheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)

    def append_row(self, sheet_name: str, values: List[Any]):
        ws = self.worksheet(sheet_name)
        ws.append_row(values)


# Helper to load credentials from environment variable or file

def load_credentials() -> Dict[str, Any]:
    creds_env = os.getenv("GSHEETS_CREDENTIALS")
    if creds_env and creds_env.strip().startswith("{"):
        return json.loads(creds_env)
    creds_file = os.getenv("GSHEETS_CREDENTIALS_FILE", "gsheets_credentials.json")
    if os.path.exists(creds_file):
        with open(creds_file, "r", encoding="utf-8") as f:
            return json.load(f)
    raise RuntimeError("Google Sheets credentials not found")


def get_manager(spreadsheet_id: str) -> GoogleSheetsManager:
    creds = load_credentials()
    return GoogleSheetsManager(creds, spreadsheet_id)

