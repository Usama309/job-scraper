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
    # Should update Source Platforms column (N = col 14)
    mock_ws.update_cell.assert_any_call(2, 14, "LinkedIn, Indeed")


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

    # Verify no update_cell call touched columns 22-26 (V-Z)
    for call in mock_ws.update_cell.call_args_list:
        _, col, _ = call.args
        assert col < 22 or col > 26, f"Operator column {col} was overwritten"
