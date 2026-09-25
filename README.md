# ABS Labour Force data pipeline

`ABS Labour Force.ipynb` downloads four ABS Labour Force workbooks, checks their structure against the reference workbooks in `Labour Force Datasets/`, and saves one cleaned CSV per source table. Each output filename includes the ABS reference month.

Run the notebook from this project folder using **Restart Kernel and Run All Cells**. The notebook installs its Python dependencies in its first cell. It chooses the next reference month after the latest completed run, builds the corresponding ABS download URLs, and writes files under `outputs/abs_labour_force/`. Generated outputs are excluded from Git.

The four reference workbooks are part of this repository because the structural checks depend on them. If ABS changes a workbook's layout or definitions, review the change before updating the relevant reference workbook and its saved SHA-256 fingerprint in the notebook.

The MLF1 workbook is expected to move to a separate ABS publication from October 2026. Its URL logic will need updating for that release.
