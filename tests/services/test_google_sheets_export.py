from services.google_sheets_rows import build_sheet_rows, parse_spreadsheet_id


def test_parse_spreadsheet_id_from_url() -> None:
    url = "https://docs.google.com/spreadsheets/d/abc123XYZ/edit#gid=0"
    assert parse_spreadsheet_id(url) == "abc123XYZ"


def test_parse_spreadsheet_id_raw() -> None:
    assert parse_spreadsheet_id("abc123XYZ") == "abc123XYZ"


def test_build_sheet_rows_total_first_then_sources() -> None:
    sources = [
        {
            "source_name": "alpha",
            "total_users": 100,
            "trial_users": 50,
            "connected_users": 40,
            "paid_users": 10,
            "total_payments": 12,
            "total_revenue": 1200.0,
        },
        {
            "source_name": "beta",
            "total_users": 200,
            "trial_users": 100,
            "connected_users": 80,
            "paid_users": 20,
            "total_payments": 25,
            "total_revenue": 2500.0,
        },
    ]

    rows = build_sheet_rows(sources)

    assert rows[0][0] == "Источник"
    assert rows[1][0] == "Всего"
    assert rows[1][1] == 300
    assert rows[1][2] == 150
    assert rows[1][3] == "50.0%"
    assert rows[1][9] == 3700
    assert rows[2][0] == "alpha"
    assert rows[3][0] == "beta"
