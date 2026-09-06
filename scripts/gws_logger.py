import os
import json
import logging
import subprocess

from scripts.insight_formatter import build_trade_insight, format_trade_for_journal


logger = logging.getLogger(__name__)


class GWSLogger:
    def __init__(self, config):
        self.config = config.get('gws', {})
        self.enabled = self.config.get('enabled', True)
        self.spreadsheet_id = self.config.get('spreadsheet_id')
        self.doc_id = self.config.get('doc_id')
        self.gws_path = self.config.get('cli_path', "/Users/nopparuj/.gemini/extensions/google-workspace-cli/npm/run.js")
        if not self.enabled:
            logger.info("Google Workspace logger disabled")
        elif not os.path.exists(self.gws_path):
            logger.warning("Google Workspace CLI path not found: %s", self.gws_path)
            self.enabled = False

    def _run_gws(self, cmd_args):
        """Runs a GWS CLI command."""
        if not self.enabled:
            logger.info("GWS disabled; skipped command")
            return None

        full_cmd = ["node", self.gws_path] + cmd_args
        try:
            result = subprocess.run(full_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error("GWS error: %s", result.stderr)
            return result.stdout
        except Exception as e:
            logger.error("Exception running GWS: %s", e)
            return None

    def log_trade_to_sheets(self, trade_data):
        """Appends trade data to Google Sheets."""
        if not self.enabled or not self.spreadsheet_id:
            logger.info("GWS Sheets logging skipped")
            return
            
        insight = build_trade_insight(trade_data)

        # [Time, Symbol, Type, Entry, TP, SL, RR, Action, Status]
        values = [[
            str(trade_data.get('time')),
            trade_data.get('symbol', 'XAUUSD'),
            trade_data.get('type'),
            trade_data.get('entry'),
            trade_data.get('tp'),
            trade_data.get('sl'),
            insight["risk"]["rr"],
            insight["action"],
            trade_data.get('status', 'OPEN')
        ]]
        
        json_body = json.dumps({"values": values})
        self._run_gws([
            "sheets", "spreadsheets", "values", "append",
            "--params", json.dumps({"spreadsheetId": self.spreadsheet_id, "range": "Sheet1!A1", "valueInputOption": "USER_ENTERED"}),
            "--json", json_body
        ])

    def log_journal_to_docs(self, journal_entry):
        """Appends a detailed journal entry to Google Docs."""
        if not self.enabled or not self.doc_id:
            logger.info("GWS Docs logging skipped")
            return
            
        content = (
            format_trade_for_journal(journal_entry)
        )
        
        # Using gws-docs-write skill pattern
        self._run_gws([
            "docs", "documents", "batchUpdate",
            "--params", json.dumps({"documentId": self.doc_id}),
            "--json", json_encode_request(content)
        ])

def json_encode_request(text):
    """Helper to format docs batchUpdate request."""
    return json.dumps({
        "requests": [{
            "insertText": {
                "location": {"index": 1}, # Insert at start
                "text": text
            }
        }]
    })
