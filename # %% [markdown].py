# %% [markdown]
# > **Local CSV walkthrough.** For scheduled Databricks runs, use the four notebooks in `notebooks/` and the setup in [README](README.md).
# 
# # ABS Labour Force Survey data
# 
# The notebook’s goal is to automate the monthly preparation of ABS Labour Force data for analysis and dashboards. It identifies the next release to process, downloads three workbooks covering national and state labour force figures, youth figures, and modelled regional estimates, then checks them against reference files for structural or definition changes. It reshapes the data into consistent, clearly labelled tables and saves three cleaned CSVs, while retaining the original downloads and a source manifest so each completed run is traceable.
# 
# - **Table 010:** Labour force status by Sex, State and Territory — Trend, Seasonally adjusted and Original
# - **Table 014:** Labour force status for 15–24 year olds by State and Territory
# - **MLF1:** Modelled estimates of Labour force status by SA4 (ASGS), Age and Sex

# %% [markdown]
# ## 1. Setup and reference workbooks
# 
# Paths assume the notebook is opened from the project folder.

# %%
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests
from IPython.display import display

# Separate incase the base-url for any dataset changes in the future.
base_urls = {
    "Table 010": "https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/",
    "Table 014": "https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/",
    "MLF1": "https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/",
}

root = Path.cwd()
baseline = root / "Reference Datasets"
now = datetime.now(timezone.utc)
retrieved_at = now.isoformat()
run = root / "outputs" / "abs_labour_force" / now.strftime("%Y%m%dT%H%M%S%fZ")

# %% [markdown]
# ## 2. Build the next release URLs and download all three files
# 
# The next release is one month after the later of the last month in the reference Table 010 workbook and the latest completed run. For the three workbooks, build the observed ABS URL pattern from that month and each fixed filename. The download fails if a file is unavailable. All three are held in memory and the run folder is created only after every download succeeds, so trying an unpublished release leaves nothing behind. MLF1 is scheduled to move to a separate ABS publication from October 2026, so its URL will need updating then.

# %%
# Create a table linking each dataset to its reference and download filenames.
sources = pd.DataFrame(
    [("Table 010", "Table 010.xlsx", "62020010.xlsx"), ("Table 014", "Interim Table 14.xlsx", "62020014.xlsx"), ("MLF1", "MLF1.xlsx", "MLF1.xlsx")],
    columns=["dataset", "baseline_file", "download_file"],
).set_index("dataset")

# Read the last month recorded in the Table 010 reference workbook.
baseline_file = baseline / sources.loc["Table 010", "baseline_file"]
baseline_latest_month = pd.to_datetime(pd.read_excel(baseline_file, sheet_name="Data1", header=None).iloc[-1, 0])
# Find the source records from completed runs and read their release months.
completed_sources = (root / "outputs" / "abs_labour_force").glob("*/sources.csv")
processed_months = [pd.to_datetime(pd.read_csv(source_file)["reference_period"]).max() for source_file in completed_sources]
# Choose the next month after the latest reference or previously processed month.
download_month = max([baseline_latest_month, *processed_months]) + pd.offsets.MonthBegin(1)

# Build each download URL from its base address, month and filename.
sources["source_url"] = sources.index.map(base_urls) + f"{download_month:%b-%Y}/".lower() + sources["download_file"]
# Record the release month and retrieval time for each dataset.
sources["reference_period"] = download_month
sources["retrieved_at_utc"] = retrieved_at

# Create an empty collection to hold the downloaded files in memory.
downloads = {}

# Download each file and stop if the server reports an unsuccessful response.
for row in sources.itertuples():
    response = requests.get(row.source_url, timeout=120, headers={"Cache-Control": "no-cache"})
    response.raise_for_status()
    # Check that the response starts with the ZIP file marker used by XLSX files.
    assert response.content.startswith(b"PK"), f"{row.Index}: download is not an XLSX file"
    downloads[row.download_file] = response.content

# Create the raw-data folder and save each downloaded file there.
(run / "raw").mkdir(parents=True)
for name, content in downloads.items():
    (run / "raw" / name).write_bytes(content)

# Display the chosen month, filenames and download URLs for review.
print("Download month:", f"{download_month:%B %Y}")
display(sources[["download_file", "reference_period", "source_url"]])

# %% [markdown]
# ## 3. Read and validate Table 010
# 
# This table has its own workbook reads, layout settings, validation and description parsing. Read every populated data column; expected sheets and header labels come from its reference workbook. The seven series-definition fields must match by ABS series ID.
# 
# Tables 010 and 014 reshape the monthly observations and convert values to numbers. Their metadata joins preserve the date/series keys and row counts, and `many_to_one` prevents duplicate metadata matches. These joins do not compare the reshaped observations with the original sheets. Neither table checks that its latest source month matches the requested download month.
# 

# %%

# Select the Table 010 filenames and read every sheet from both workbooks.
row = sources.loc["Table 010"]
table_010_base = pd.read_excel(baseline / row["baseline_file"], sheet_name=None, header=None)
table_010_book = pd.read_excel(run / "raw" / row["download_file"], sheet_name=None, header=None)

# Check that the downloaded workbook has the same sheet names as the reference.
dataset = "Table 010"
assert set(table_010_book) == set(table_010_base), f"{dataset}: workbook sheets changed"

# Name the ten rows that describe each series, in their workbook order.
metadata_fields = ["description", "unit", "series_type", "data_type", "frequency", "collection_month", "series_start", "series_end", "n_obs", "series_id"]

# Locate the first monthly data row and the row containing series IDs.
first_data_row = len(metadata_fields)
series_id_row = metadata_fields.index("series_id")
# Select the series details to compare, excluding end dates and observation counts.
definition_fields = ["description", "unit", "series_type", "data_type", "frequency", "collection_month", "series_start"]

# Create empty lists to collect series details, monthly values and sheet summaries.
metadata_frames, observation_frames, sheet_checks = [], [], []

# Read the three data sheets by name.
for sheet in ["Data1", "Data2", "Data3"]:
    raw_sheet = table_010_book[sheet]
    # Check that the first ten row labels match those in the reference sheet.
    baseline_sheet = table_010_base[sheet]
    pd.testing.assert_series_equal(raw_sheet.iloc[:first_data_row, 0], baseline_sheet.iloc[:first_data_row, 0], obj=f"{dataset}/{sheet}: header rows")
    # Read the series IDs and check that none are missing or repeated within this sheet.
    series_ids = raw_sheet.iloc[series_id_row, 1:]
    assert series_ids.notna().all() and series_ids.is_unique, f"{dataset}/{sheet}: missing or duplicate series IDs"

    # Turn the series details into one row per series, label the columns and sort by ID.
    sheet_metadata = raw_sheet.iloc[:first_data_row, 1:].T.set_axis(metadata_fields, axis=1).set_index("series_id").sort_index()
    baseline_metadata = baseline_sheet.iloc[:first_data_row, 1:].T.set_axis(metadata_fields, axis=1).set_index("series_id").sort_index()
    # Compare the selected series details with the reference and stop if they differ.
    pd.testing.assert_frame_equal(sheet_metadata[definition_fields], baseline_metadata[definition_fields], obj=f"{dataset}/{sheet}: series definitions")

    # Reshape the monthly values into date, series ID and value columns.
    sheet_observations = (
        raw_sheet.iloc[first_data_row:].set_axis(["date", *series_ids], axis=1).melt("date", var_name="series_id").astype({"date": "datetime64[ns]"})
    )
    # Convert the observation values to numbers.
    sheet_observations["value"] = pd.to_numeric(sheet_observations["value"])
    # Collect this sheet's values and series details, adding their source labels.
    observation_frames.append(sheet_observations.assign(dataset=dataset))
    metadata_frames.append(sheet_metadata.reset_index().assign(dataset=dataset, sheet=sheet))
    # Record the number of months, series and observations, plus the latest month.
    sheet_checks.append((dataset, sheet, sheet_observations["date"].nunique(), len(sheet_metadata), len(sheet_observations), sheet_observations["date"].max()))

# Combine the results from all data sheets into two tables.
table_010_metadata = pd.concat(metadata_frames, ignore_index=True)
table_010 = pd.concat(observation_frames, ignore_index=True)
# Check that no series ID appears in more than one sheet.
assert not table_010_metadata.duplicated(["dataset", "series_id"]).any(), f"{dataset}: a series ID is repeated across sheets"
# Display a summary of the records read from each data sheet.
display(pd.DataFrame(sheet_checks, columns=["dataset", "sheet", "months", "series", "observations", "latest_month"]))

# %% [markdown]
# ### Tidy Table 010 dimensions

# %%
# Remove surrounding spaces and trailing semicolons, then split each description into columns.
description_parts = table_010_metadata["description"].str.strip().str.rstrip(";").str.split(";", expand=True)
# Remove spaces and leading > markers from each part of the description.
description_parts = description_parts.apply(lambda s: s.str.strip().str.lstrip(">").str.strip())
# Copy the first three description parts into the measure, sex and region columns.
table_010_metadata["measure"] = description_parts[0]
table_010_metadata["sex"] = description_parts[1]
table_010_metadata["region"] = description_parts[2]
# Label every series as covering people aged 15 years and over.
table_010_metadata["age"] = "15 years and over"
# Add an apostrophe to the thousands unit label; leave other unit labels unchanged.
table_010_metadata["unit"] = table_010_metadata["unit"].replace("000", "'000")
# Check that every series has a measure, sex, region and age label.
assert table_010_metadata[["measure", "sex", "region", "age"]].notna().all().all()

# Count the rows for each dataset, date and series ID combination before joining.
observation_keys = ["dataset", "date", "series_id"]
keys_before_join = table_010[observation_keys].value_counts(sort=False).sort_index()

# Check that each dataset and series ID has only one matching row of series details.
table_010 = table_010.merge(
    table_010_metadata[["dataset", "series_id", "measure", "sex", "age", "region", "series_type", "data_type", "unit"]],
    on=["dataset", "series_id"],
    validate="many_to_one",
)
# Check that every dataset, date and series ID combination still has the same row count.
pd.testing.assert_series_equal(
    keys_before_join, table_010[observation_keys].value_counts(sort=False).sort_index(), obj="Table 010 metadata join: observation keys and counts"
)
# Display the table size and the first five rows for review.
print(table_010.shape)
display(table_010[["date", "series_id", "measure", "region", "sex", "age", "series_type", "data_type", "unit", "value"]].head())

# %% [markdown]
# ## 4. Read and validate Table 014

# %%
# Select the Table 014 filenames and read every sheet from both workbooks.
# Keep all rows as data rather than treating the first row as column headings.
row = sources.loc["Table 014"]
table_014_base = pd.read_excel(baseline / row["baseline_file"], sheet_name=None, header=None)
table_014_book = pd.read_excel(run / "raw" / row["download_file"], sheet_name=None, header=None)
# Display the sheet names in the downloaded workbook.
print("Table 014 sheets:", list(table_014_book))

# Check that the downloaded workbook has the same sheet names as the reference.
dataset = "Table 014"
assert set(table_014_book) == set(table_014_base), f"{dataset}: workbook sheets changed"

# Name the ten rows that describe each series, in their workbook order.
metadata_fields = ["description", "unit", "series_type", "data_type", "frequency", "collection_month", "series_start", "series_end", "n_obs", "series_id"]

# Locate the first monthly data row and the row containing series IDs.
first_data_row = len(metadata_fields)
series_id_row = metadata_fields.index("series_id")
# Select the series details to compare, excluding end dates and observation counts.
definition_fields = ["description", "unit", "series_type", "data_type", "frequency", "collection_month", "series_start"]

# Create empty lists to collect series details, monthly values and sheet summaries.
metadata_frames, observation_frames, sheet_checks = [], [], []
# Read the Data1 sheet by name.
for sheet in ["Data1"]:
    raw_sheet = table_014_book[sheet]
    # Check that the first ten row labels match those in the reference sheet.
    baseline_sheet = table_014_base[sheet]
    pd.testing.assert_series_equal(raw_sheet.iloc[:first_data_row, 0], baseline_sheet.iloc[:first_data_row, 0], obj=f"{dataset}/{sheet}: header rows")
    # Read the series IDs and check that none are missing or repeated within this sheet.
    series_ids = raw_sheet.iloc[series_id_row, 1:]
    assert series_ids.notna().all() and series_ids.is_unique, f"{dataset}/{sheet}: missing or duplicate series IDs"
    # Turn the series details into one row per series, label the columns and sort by ID.
    sheet_metadata = raw_sheet.iloc[:first_data_row, 1:].T.set_axis(metadata_fields, axis=1).set_index("series_id").sort_index()
    baseline_metadata = baseline_sheet.iloc[:first_data_row, 1:].T.set_axis(metadata_fields, axis=1).set_index("series_id").sort_index()
    # Compare the selected series details with the reference and stop if they differ.
    pd.testing.assert_frame_equal(sheet_metadata[definition_fields], baseline_metadata[definition_fields], obj=f"{dataset}/{sheet}: series definitions")
    # Reshape the monthly values into date, series ID and value columns.
    sheet_observations = (
        raw_sheet.iloc[first_data_row:].set_axis(["date", *series_ids], axis=1).melt("date", var_name="series_id").astype({"date": "datetime64[ns]"})
    )
    # Convert the observation values to numbers.
    sheet_observations["value"] = pd.to_numeric(sheet_observations["value"])
    # Collect this sheet's values and series details, adding their source labels.
    observation_frames.append(sheet_observations.assign(dataset=dataset))
    metadata_frames.append(sheet_metadata.reset_index().assign(dataset=dataset, sheet=sheet))
    # Record the number of months, series and observations, plus the latest month.
    sheet_checks.append((dataset, sheet, sheet_observations["date"].nunique(), len(sheet_metadata), len(sheet_observations), sheet_observations["date"].max()))

# Combine the collected series details and monthly values into two tables.
table_014_metadata = pd.concat(metadata_frames, ignore_index=True)
table_014 = pd.concat(observation_frames, ignore_index=True)
# Check that each dataset and series ID combination appears only once in the series details.
assert not table_014_metadata.duplicated(["dataset", "series_id"]).any(), f"{dataset}: a series ID is repeated across sheets"
# Display a summary of the records read from each data sheet.
display(pd.DataFrame(sheet_checks, columns=["dataset", "sheet", "months", "series", "observations", "latest_month"]))

# %% [markdown]
# ### Tidy Table 014 dimensions
# 

# %%
# Remove surrounding spaces and trailing semicolons, then split each description into columns.
description_parts = table_014_metadata["description"].str.strip().str.rstrip(";").str.split(";", expand=True)
# Remove spaces and leading > markers from each part of the description.
description_parts = description_parts.apply(lambda s: s.str.strip().str.lstrip(">").str.strip())
# Copy the first two description parts into the region and measure columns.
table_014_metadata["region"] = description_parts[0]
table_014_metadata["measure"] = description_parts[1]
# Label every series as covering persons aged 15–24.
table_014_metadata["sex"] = "Persons"
table_014_metadata["age"] = "15-24 years"
# Add an apostrophe to the thousands unit label; leave other unit labels unchanged.
table_014_metadata["unit"] = table_014_metadata["unit"].replace("000", "'000")
# Check that every series has a measure, sex, region and age label.
assert table_014_metadata[["measure", "sex", "region", "age"]].notna().all().all()

# Count the rows for each dataset, date and series ID combination before joining.
observation_keys = ["dataset", "date", "series_id"]
keys_before_join = table_014[observation_keys].value_counts(sort=False).sort_index()
# Attach the series labels and units to each matching observation.
# Check that each dataset and series ID has only one matching row of series details.
table_014 = table_014.merge(
    table_014_metadata[["dataset", "series_id", "measure", "sex", "age", "region", "series_type", "data_type", "unit"]],
    on=["dataset", "series_id"],
    validate="many_to_one",
)
# Check that every dataset, date and series ID combination still has the same row count.
pd.testing.assert_series_equal(
    keys_before_join, table_014[observation_keys].value_counts(sort=False).sort_index(), obj="Table 014 metadata join: observation keys and counts"
)
# Display the table size and the first five rows for review.
print(table_014.shape)
display(table_014[["date", "series_id", "measure", "region", "sex", "age", "series_type", "data_type", "unit", "value"]].head())

# %% [markdown]
# ## 5. Read and validate MLF1
# 
# Use the underlying **Data 1** sheet, which contains all sex × age × region combinations. The presentation pivot sheet is not another dataset and is not appended. Ignore only completely empty columns below the workbook preamble; any populated new header or data column is compared with the baseline. Every month must have the same number of rows, and the latest month must be the release being processed.

# %%

# Select the MLF1 filenames and open the reference and downloaded workbooks.
row = sources.loc["MLF1"]
baseline_workbook = pd.ExcelFile(baseline / row["baseline_file"])
downloaded_workbook = pd.ExcelFile(run / "raw" / row["download_file"])

# Read the Data 1 sheet from each workbook, keeping the first row as data.
mlf_base = pd.read_excel(baseline_workbook, sheet_name="Data 1", header=None)
mlf_raw = pd.read_excel(downloaded_workbook, sheet_name="Data 1", header=None)
# Display the sheet names in the downloaded workbook.
print("MLF1 sheets:", downloaded_workbook.sheet_names)
# Check that both workbooks contain the same sheet names.
assert set(downloaded_workbook.sheet_names) == set(baseline_workbook.sheet_names), "MLF1: workbook sheets changed"
# Check that the table title in Excel cell A2 matches the reference.
assert mlf_raw.iloc[1, 0] == mlf_base.iloc[1, 0], "MLF1: table identity changed"
# Start at the headings in Excel row 4 and remove columns that are entirely empty from there down.
mlf_header_row = 3
mlf_base = mlf_base.iloc[mlf_header_row:].dropna(axis=1, how="all")
mlf_raw = mlf_raw.iloc[mlf_header_row:].dropna(axis=1, how="all")
# Check that the column headings and their order match the reference.
assert mlf_raw.iloc[0].tolist() == mlf_base.iloc[0].tolist(), "MLF1: column names, units, order or geography vintage changed"
# Reset the row numbers and let pandas recognise numeric and date values.
mlf_base = mlf_base.iloc[1:].set_axis(mlf_base.iloc[0].tolist(), axis=1).reset_index(drop=True).infer_objects()
mlf_raw = mlf_raw.iloc[1:].set_axis(mlf_raw.iloc[0].tolist(), axis=1).reset_index(drop=True).infer_objects()

# Select the sex, age and region columns, then the remaining measure columns.
# Store the region column name for the checks and reshaping that follow.
dimension_columns = mlf_raw.columns[1:4].tolist()
measure_columns = mlf_raw.columns[4:].tolist()
region_column = dimension_columns[2]
# Check that no cells are missing and that all measure columns contain numeric data.
assert mlf_raw.notna().all().all(), "MLF1: missing dimension or estimate"
assert mlf_raw[measure_columns].dtypes.map(pd.api.types.is_numeric_dtype).all(), "MLF1: non-numeric observations"
# Check that the sex, age and region categories match those in the reference.
for column in dimension_columns:
    assert set(mlf_raw[column]) == set(mlf_base[column]), f"MLF1: categories changed in {column}"
# Convert Month to dates and count the rows in each month.
mlf_raw["Month"] = pd.to_datetime(mlf_raw["Month"])
rows_per_month = mlf_raw.groupby("Month").size()
# Check that every month has the same number of rows.
assert rows_per_month.nunique() == 1, "MLF1: months have different numbers of sex × age × region rows"
# Find the latest month and check that it is the release being processed.
latest_month = mlf_raw["Month"].max()
assert latest_month == download_month, f"MLF1: latest month is not {download_month:%B %Y}"

# Display the table size and first five rows for review.
print(mlf_raw.shape)
display(mlf_raw.head())

# %% [markdown]
# ### Tidy MLF1 measures

# %%
# Rename the date, sex, age and region columns, then turn the measure columns into rows.
# Each row holds one measure and value for a date, sex, age and region combination.
mlf = mlf_raw.rename(columns={"Month": "date", "Sex": "sex", "Age": "age", region_column: "region"}).melt(
    id_vars=["date", "sex", "age", "region"], value_vars=measure_columns, var_name="measure"
)
# Split each region label into its three-digit code and the name after the space.
mlf[["region_code", "region"]] = mlf["region"].str.extract(r"^(\d{3}) (.+)$")
# Check that a region code was extracted from every row.
assert mlf["region_code"].notna().all(), "MLF1: region-code format changed"
# Remove the thousands unit from the measure names and record it in a separate column.
mlf["measure"] = mlf["measure"].str.replace(" ('000)", "", regex=False)
mlf["unit"] = "'000"
# Label all rows as modelled estimates.
mlf["series_type"] = "Modelled"
# Display the table size and the first five rows for review.
print(mlf.shape)
display(mlf[["date", "region_code", "region", "sex", "age", "measure", "value"]].head())

# %% [markdown]
# ## 6. Save three cleaned source tables
# 
# Each source workbook gets its own cleaned CSV named for the ABS table and download month, for example `table_010_2026-08.csv`. The release month is recorded in the filename and in `sources.csv`, not as a column.
# 
# | File | Columns |
# |---|---|
# | `table_010_*.csv`, `table_014_*.csv` | `date`, `series_id`, `measure`, `sex`, `age`, `region`, `series_type`, `data_type`, `unit`, `value` |
# | `mlf1_*.csv` | `date`, `measure`, `sex`, `age`, `sa4_code`, `sa4_region`, `series_type`, `unit`, `value` |
# 
# `region` in Tables 010 and 014 is Australia or a state/territory. `sources.csv` records each ABS download and its output file; it is written last, so it only exists for completed runs.

# %%
# Choose the columns and their order for the Table 010 and Table 014 CSV files.
export_columns = ["date", "series_id", "measure", "sex", "age", "region", "series_type", "data_type", "unit", "value"]
# Collect the two tables with only the selected columns.
exports = {"Table 010": table_010[export_columns], "Table 014": table_014[export_columns]}
# Add the regional table, selecting its columns and renaming the region fields to SA4 labels.
exports["MLF1"] = mlf[["date", "measure", "sex", "age", "region_code", "region", "series_type", "unit", "value"]].rename(
    columns={"region_code": "sa4_code", "region": "sa4_region"}
)

# Create a filename for each dataset using its name and the release month.
for dataset, dataset_rows in exports.items():
    sources.loc[dataset, "output_file"] = f"{dataset.lower().replace(' ', '_')}_{download_month:%Y-%m}.csv"
    # Save the table as a CSV without row numbers, formatting dates as YYYY-MM-DD.
    dataset_rows.to_csv(run / sources.loc[dataset, "output_file"], index=False, date_format="%Y-%m-%d")

# Save the download details and output filenames to sources.csv after writing all three tables.
sources.to_csv(run / "sources.csv")


# %% [markdown]
# ## 7. Databricks publishing
# 
# Use the three preparation notebooks and final publishing notebook in `notebooks/`, following [README](README.md). They share an explicit release month and replace all three Delta tables in one transaction. This local walkthrough saves CSVs only; its `sources.csv` does not mark a Databricks publication.
# 


