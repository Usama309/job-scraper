from datetime import datetime
from unittest.mock import MagicMock, patch

from src.models import Job
from src.sheets import EXPECTED_TABS, MASTER_HEADERS, SheetsClient


def test_expected_tabs_constant():
    assert EXPECTED_TABS == [
        "All Jobs", "LinkedIn", "Indeed", "Glassdoor",
        "API Sources", "Run Log",
    ]


def test_master_headers_count():
    assert len(MASTER_HEADERS) == 26
    assert MASTER_HEADERS[0] == "Job ID"
    assert MASTER_HEADERS[25] == "Notes"


@patch("src.sheets.gspread.service_account_from_dict")
def test_ensure_tabs_creates_missing(mock_sa):
    mock_sheet = MagicMock()
    mock_sheet.worksheets.return_value = [
        MagicMock(title="All Jobs"), MagicMock(title="Run Log")
    ]
    mock_sa.return_value.open_by_key.return_value = mock_sheet

    client = SheetsClient(creds={}, sheet_id="x")
    client.ensure_tabs()

    # 4 missing tabs should be created
    assert mock_sheet.add_worksheet.call_count == 4
    created_titles = {c.kwargs["title"] for c in mock_sheet.add_worksheet.call_args_list}
    assert created_titles == {"LinkedIn", "Indeed", "Glassdoor", "API Sources"}


@patch("src.sheets.gspread.service_account_from_dict")
def test_append_to_tab_calls_append_rows(mock_sa):
    mock_ws = MagicMock()
    mock_sheet = MagicMock()
    mock_sheet.worksheet.return_value = mock_ws
    mock_sa.return_value.open_by_key.return_value = mock_sheet

    client = SheetsClient(creds={}, sheet_id="x")
    rows = [["a"] * 26, ["b"] * 26]
    client.append_to_tab("LinkedIn", rows)

    mock_sheet.worksheet.assert_called_with("LinkedIn")
    mock_ws.append_rows.assert_called_once_with(rows, value_input_option="USER_ENTERED")


def _make_job(jid, title, company, source="LinkedIn"):
    return Job(
        job_id=jid, scraped_at=datetime(2026, 5, 13, 14, 0),
        posted_date="2026-05-13", title=title, company=company,
        location="Remote", remote_type="Remote", employment_type="Full-time",
        salary_range=None, skills_tags=[], keyword_matched="kw",
        description_snippet="", source=source, url=f"https://x/{jid}",
    )


@patch("src.sheets.gspread.service_account_from_dict")
def test_upsert_appends_new_jobs(mock_sa):
    mock_ws = MagicMock()
    mock_ws.get_all_values.return_value = [["Job ID"] + [""] * 25]  # only header
    mock_sheet = MagicMock()
    mock_sheet.worksheet.return_value = mock_ws
    mock_sa.return_value.open_by_key.return_value = mock_sheet

    client = SheetsClient(creds={}, sheet_id="x")
    client.upsert_to_master([_make_job("aaa", "T", "C")])

    mock_ws.append_rows.assert_called_once()
    appended = mock_ws.append_rows.call_args.args[0]
    assert appended[0][0] == "aaa"


@patch("src.sheets.gspread.service_account_from_dict")
def test_upsert_merges_sources_for_existing_job(mock_sa):
    existing_row = ["aaa"] + [""] * 12 + ["LinkedIn", "LinkedIn"] + [""] * 11
    mock_ws = MagicMock()
    mock_ws.get_all_values.return_value = [
        ["Job ID"] + [""] * 25,
        existing_row,
    ]
    mock_sheet = MagicMock()
    mock_sheet.worksheet.return_value = mock_ws
    mock_sa.return_value.open_by_key.return_value = mock_sheet

    client = SheetsClient(creds={}, sheet_id="x")
    client.upsert_to_master([_make_job("aaa", "T", "C", source="Indeed")])

    # Should NOT append a new row
    mock_ws.append_rows.assert_not_called()
    # Should batch_update with Source Platforms (column N = col 14, A1: "N2")
    mock_ws.batch_update.assert_called_once()
    batch_arg = mock_ws.batch_update.call_args.args[0]
    assert any(u["range"] == "N2" and u["values"] == [["LinkedIn, Indeed"]] for u in batch_arg)


@patch("src.sheets.gspread.service_account_from_dict")
def test_upsert_never_overwrites_columns_v_to_z(mock_sa):
    existing_row = ["aaa"] + [""] * 12 + ["LinkedIn", "LinkedIn"] + [""] * 6 + \
                   ["Applied", "2026-05-12", "2026-05-20", "v2.pdf", "Hot lead"]
    mock_ws = MagicMock()
    mock_ws.get_all_values.return_value = [
        ["Job ID"] + [""] * 25,
        existing_row,
    ]
    mock_sheet = MagicMock()
    mock_sheet.worksheet.return_value = mock_ws
    mock_sa.return_value.open_by_key.return_value = mock_sheet

    client = SheetsClient(creds={}, sheet_id="x")
    client.upsert_to_master([_make_job("aaa", "T", "C", source="Indeed")])

    # Verify no batch_update range touched columns V-Z (V2..Z2 etc.)
    for call in mock_ws.batch_update.call_args_list:
        updates = call.args[0]
        for u in updates:
            a1 = u["range"]
            # Extract column letters from A1 (e.g. "N2" -> "N", "AA10" -> "AA")
            col_letters = "".join(c for c in a1 if c.isalpha())
            assert col_letters not in ("V", "W", "X", "Y", "Z"), (
                f"Operator column {col_letters} was overwritten via {a1}"
            )


@patch("src.sheets.gspread.service_account_from_dict")
def test_write_run_log_appends_19_columns(mock_sa):
    mock_ws = MagicMock()
    mock_sheet = MagicMock()
    mock_sheet.worksheet.return_value = mock_ws
    mock_sa.return_value.open_by_key.return_value = mock_sheet

    client = SheetsClient(creds={}, sheet_id="x")
    stats = {
        "started": "2026-05-13 14:00",
        "ended": "2026-05-13 14:01",
        "duration_sec": 60,
        "trigger": "manual",
        "time_window": "6h",
        "counts": {"LinkedIn": 10, "Indeed": 20, "Glassdoor": 0,
                   "Remotive": 5, "RemoteOK": 3, "WeWorkRemotely": 2,
                   "Adzuna": 0, "JSearch": 0},
        "after_dedup": 35,
        "new_jobs": 12,
        "errors": "",
        "adzuna_quota": "42/250",
        "jsearch_quota": "18/150",
        "status": "OK",
    }
    client.write_run_log(stats)

    mock_sheet.worksheet.assert_called_with("Run Log")
    row = mock_ws.append_row.call_args.args[0]
    assert len(row) == 19
    assert row[3] == "manual"  # Trigger column D
    assert row[18] == "OK"     # Status column S
