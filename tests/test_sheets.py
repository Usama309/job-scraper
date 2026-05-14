from unittest.mock import MagicMock, patch

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
