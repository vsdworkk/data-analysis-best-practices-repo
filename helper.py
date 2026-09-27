import pandas as pd
from IPython.display import display


def validate_observations(raw_sheet, sheet_observations, first_data_row, dataset, sheet, download_month):
    """Return numeric observations after checking preservation from the raw sheet.

    Assert the requested month, unchanged key multiplicities and populated keys.
    Allow source blanks; reject invalid numeric content. No numeric equality check.
    """
    label = f"{dataset}/{sheet}"
    source_dates = pd.to_datetime(raw_sheet.iloc[first_data_row:, 0])
    assert source_dates.notna().all(), f"{label}: missing dates"
    assert source_dates.max() == download_month, f"{label}: latest month is not {download_month:%B %Y}"

    # Each raw row contributes one observation for every series, including blanks.
    # The series IDs occupy the metadata row immediately above the observations.
    source_keys = pd.MultiIndex.from_product([source_dates, raw_sheet.iloc[first_data_row - 1, 1:]], names=["date", "series_id"])
    reshaped_keys = pd.MultiIndex.from_frame(sheet_observations[["date", "series_id"]])
    assert source_keys.sort_values().equals(reshaped_keys.sort_values()), f"{label}: reshaping changed observation keys or their counts"

    numeric_values = pd.to_numeric(sheet_observations["value"], errors="coerce")
    invalid_values = sheet_observations["value"].notna() & (numeric_values.isna() | numeric_values.isin([float("inf"), -float("inf")]))
    if invalid_values.any():
        display(sheet_observations.loc[invalid_values, ["date", "series_id", "value"]])
    assert not invalid_values.any(), f"{label}: nonnumeric or infinite values; see rows above"

    # Flatten row by row to match the raw date × series keys; compare presence, not values.
    source_populated = raw_sheet.iloc[first_data_row:, 1:].notna().to_numpy().ravel()
    source_populated_keys = source_keys[source_populated].sort_values()
    reshaped_populated_keys = reshaped_keys[numeric_values.notna()].sort_values()
    assert source_populated_keys.equals(reshaped_populated_keys), f"{label}: reshaping changed which observation keys have populated values"
    return sheet_observations.assign(value=numeric_values)
