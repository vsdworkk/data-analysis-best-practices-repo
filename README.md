# ABS Labour Force pipeline

Each Databricks notebook downloads and cleans one ABS source, saves a CSV, then creates or overwrites its own Delta table directly from the cleaned data.

| Notebook | Delta table |
|---|---|
| [01 Prepare Table 010](notebooks/01%20Prepare%20Table%20010.ipynb) | `catalog.schema.table_010` |
| [02 Prepare Table 014](notebooks/02%20Prepare%20Table%20014.ipynb) | `catalog.schema.table_014` |
| [03 Prepare MLF1](notebooks/03%20Prepare%20MLF1.ipynb) | `catalog.schema.mlf1` |
| [04 Prepare Table 013](notebooks/04%20Prepare%20Table%20013.ipynb) | `catalog.schema.table_013` |

The four tables update independently. There is no separate publishing notebook, staging Delta table or multi-table transaction. If one source fails, the others can still publish, so their latest releases may differ.

Each notebook selects its next release automatically from its own reference workbook and completed runs, then records success in `sources.csv`. All four use the same seven sections: setup, next release, download, validation, reshaping/cleaning, CSV export and Delta publication.

## Set up Databricks

1. Import the four notebooks in `notebooks/`, or use them from a Databricks Git folder.
2. Create a destination Unity Catalog catalogue and schema for the Delta tables.
3. Keep `Table 010.xlsx`, `Interim Table 14.xlsx`, `MLF1.xlsx` and `Table 013.xlsx` in the workspace project's `referencedatasets/` folder, keeping their filenames. Set `workspace_path` to the absolute `/Workspace/...` path of that project folder.
4. Use compute with Spark, workspace file read/write support, `pandas`, `openpyxl`, `requests` and network access to `www.abs.gov.au`.
5. Give the run identity permission to read the workspace reference files, write to the project's `outputs/` folder, use the catalogue and schema, and create or modify the destination tables.
6. Fill in `catalog` and `schema` in **Section 7 of each notebook**. These are code settings, not job parameters.
7. Run the notebooks as four independent tasks in one job, or as separate jobs. They do not depend on each other. Limit each job to one concurrent run to avoid competing writes to the same source's files or table.

The [original notebook](ABS%20Labour%20Force.ipynb) remains a local CSV walkthrough. Use the four source notebooks for Databricks. No helper module is needed, and there is no multi-table transaction or catalogue-commits feature requirement.

## Values to fill out

Set these job parameters, or fill in the corresponding notebook widgets for an interactive run:

| Parameter | Example | Purpose |
|---|---|---|
| `run_date` | `{{job.start_time.iso_date}}` | Job start date in UTC (`YYYY-MM-DD`); for an interactive run, enter the date you run it. |
| `job_run_id` | `{{job.run_id}}` | Set this dynamic reference in job settings; for an interactive run, enter a folder label such as `manual-july-2026`. |
| `workspace_path` | `/Workspace/Users/<your-email>/abs-labour-force` | Workspace project folder containing `referencedatasets/`; generated Excel files and CSVs go into `outputs/`. |

In the final code cell of **each** notebook, replace:

```python
catalog = "YOUR_CATALOG"
schema = "YOUR_SCHEMA"
```

`dataset_key` is already set to `table_010`, `table_014`, `mlf1` or `table_013`. The write creates a missing Delta table or replaces all its rows, including historical observations, with the latest cleaned data. It does not append another copy of the history or automatically replace an existing schema.

Each notebook selects one month after the later of its reference workbook's latest month and its own latest completed release, following the original notebook's method. Tables 010, 014 and 013 read the reference month from `Data1`; MLF1 reads the latest month in the `Month` column of `Data 1`. No notebook uses a `release_month` job parameter.

Table 013 uses the [July 2026 reference workbook](https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/jul-2026/62020013.xlsx), so its first run selects August 2026. It covers national labour force status for ages 15–24 by sex, with Trend, Seasonally Adjusted and Original series.

Completed releases come from `outputs/<dataset>/*/sources.csv`. Each notebook writes that file only after its CSV and Delta table have both been written. Incomplete runs and other datasets do not advance its release. Existing runs in the previous folder layout are not scanned automatically.

## Files and table columns

Each source saves:

```text
<workspace_path>/outputs/<dataset>/<run_date>_<job_run_id>/
    raw/<downloaded_workbook>.xlsx
    <dataset>_<release_month>.csv
    sources.csv
```

`<dataset>` is `table_010`, `table_014`, `mlf1` or `table_013`. Each `sources.csv` records the dataset, reference and download filenames, source URL, release month, retrieval time and output filename.

Section 4 reads and validates the source workbook. Section 5 reshapes and cleans the observations, with checks on the resulting labels and joins. Separate date checks immediately before CSV export have been removed. Tables 010, 014 and 013 retain their sheet-level series-ID and metadata checks without the redundant combined duplicate-ID check. MLF1 retains its layout, category, numeric-value and monthly-coverage checks.

For example, a job started on 27 September 2026 (UTC) with run ID `12345` saves Table 010 under `outputs/table_010/2026-09-27_12345/` in the workspace project folder. The date comes from the [job start time](https://docs.databricks.com/aws/en/jobs/dynamic-value-references), independently of the ABS release month.

Reference workbooks, downloaded workbooks and cleaned CSVs are workspace files. The Delta tables are managed in Unity Catalog through `saveAsTable`; no volume is required. The project's `outputs/` folder is Git-ignored.

Use a persistent, writable workspace folder for `workspace_path`. For jobs sourced directly from remote Git, use that explicit workspace path rather than the temporary checkout. [Databricks workspace files](https://docs.databricks.com/aws/en/files/workspace) support Python file operations and have a 500 MB limit per file.

Retrying an incomplete run with the same date and job run ID replaces its files in that folder. A full rerun after completion selects the next release; use a new job run ID to keep each completed release in its own folder. The CSV is saved before the Delta write, so it is still available if publishing fails.

The Delta tables contain the same columns as the CSVs; observation dates are stored as calendar dates:

| Dataset | Columns |
|---|---|
| Table 010, Table 014 and Table 013 | `date`, `series_id`, `measure`, `sex`, `age`, `region`, `series_type`, `data_type`, `unit`, `value` |
| MLF1 | `date`, `measure`, `sex`, `age`, `sa4_code`, `sa4_region`, `series_type`, `unit`, `value` |

There are no extra publication-ID or release-period columns. The release month is recorded in each CSV filename and its source completion record.

Table 013 sets `region` to `Australia` and `age` to `15-24 years`; `measure` and `sex` come from each series description. Counts use `'000` and rates retain the source's `Percent` unit and values.

## Reruns and ABS changes

Repair or rerun only the source that failed. Each notebook selects its next release automatically from its reference workbook and completed runs. If the cleaned `df` is still available in the same notebook session, the publishing cell can be rerun on its own. A fresh session needs the earlier cells to rebuild `df`.

Each notebook keeps its URL, filenames, exact sheet names and layout settings near the top. If ABS changes a workbook, inspect the raw download, adjust that source's parsing and deliberately update its reference workbook. MLF1's download location may change independently of the other sources.

Workbook structure checks, metadata checks, numeric conversion and release-month checks remain in the source notebooks. The removed observation-validation helper has not been restored.

## Local verification

From the project folder, run:

```bash
.venv/bin/python tests/check_databricks_notebooks.py
```

The checks use the reference workbooks in place of live downloads, compare the existing cleaned data with the original notebook, reconcile every Table 013 observation and series label against its ABS workbook, read back the CSVs and check the direct Delta-write calls using a Spark mock. They also check independent release selection and confirm that a failed publication creates no completion record. They require `pandas`, `openpyxl`, `requests`, `IPython` and `nbformat`.

Actual Delta writes must be checked in Databricks. Run each notebook against a test destination, confirm the columns and row count, then rerun the publishing cell and confirm the row count stays the same.
