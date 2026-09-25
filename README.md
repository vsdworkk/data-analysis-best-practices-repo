# ABS Labour Force data pipeline

`ABS Labour Force.ipynb` downloads three ABS Labour Force workbooks, checks their structure against the reference workbooks in `Labour Force Datasets/`, and saves one cleaned CSV per source table. Each output filename includes the ABS reference month.

Run the notebook from this project folder using **Restart Kernel and Run All Cells**. The notebook installs its Python dependencies in its first cell. It chooses the next reference month after the latest completed run, builds the corresponding ABS download URLs, and writes files under `outputs/abs_labour_force/`. Generated outputs are excluded from Git.

The three reference workbooks are part of this repository because the structural checks depend on them. If ABS changes a workbook's layout or definitions, review the change before updating the relevant reference workbook and its saved SHA-256 fingerprint in the notebook.

The MLF1 workbook is expected to move to a separate ABS publication from October 2026. Its URL logic will need updating for that release.

The cleaned time-series CSVs retain unit, series type, data type and series ID alongside the clean dimensions and monthly values. Their exports omit frequency, collection month, series start/end, observation count and source table; source metadata is still read internally. MLF1 exports only its underlying SA4 regional records, with region code and name labelled `sa4_code` and `sa4_region`. Its output omits series ID, geography level/basis, data type, frequency, collection month and series start/end; source table, observation count and reference period are also omitted. Table 014 keeps only the region name for geography; its export omits region code, geography level, geography basis and reference period. The release month remains in output filenames and the source manifest. The original downloaded workbooks remain under each run’s `raw/` folder for workbook notes and presentation details.

Table 010’s export omits region code, geography level, geography basis and reference period, retaining the region name.
