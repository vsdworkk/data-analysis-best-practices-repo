# ABS Labour Force data pipeline

`ABS Labour Force.ipynb` downloads three ABS Labour Force workbooks, checks their structure against the reference workbooks in `Labour Force Datasets/`, and saves one cleaned CSV per source table. Each output filename includes the ABS reference month.

Run the notebook from this project folder using **Restart Kernel and Run All Cells**. In a new environment, install `pandas`, `openpyxl` and `requests` once first. The notebook chooses the next reference month after the latest completed run, builds the corresponding ABS download URLs, and writes files under `outputs/abs_labour_force/`. Generated outputs are excluded from Git.

The three reference workbooks are part of this repository because the structural checks depend on them. If ABS changes a workbook's layout or definitions, review the change before updating the relevant reference workbook.

The MLF1 workbook is expected to move to a separate ABS publication from October 2026. Its URL logic will need updating for that release.

| File | Columns |
|---|---|
| `table_010_*.csv`, `table_014_*.csv` | `date`, `series_id`, `measure`, `sex`, `age`, `region`, `series_type`, `data_type`, `unit`, `value` |
| `mlf1_*.csv` | `date`, `measure`, `sex`, `age`, `sa4_code`, `sa4_region`, `series_type`, `unit`, `value` |

The release month is recorded in output filenames and in each run's `sources.csv`, not as a column. The original downloaded workbooks remain under each run's `raw/` folder for workbook notes and presentation details.
