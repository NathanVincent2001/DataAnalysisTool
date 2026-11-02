# NorphStats

A PySide6 desktop application for loading scientific CSV data, exploring numeric series, analysing time and frequency stability, identifying potential anomalies, and exporting publication-style plots.

## Features

- Load and inspect CSV data with automatic detection for comma, semicolon, tab, pipe, caret, tilde, single-space and repeated-space separators.
- Read common UTF-8, UTF-8 BOM, UTF-16, Windows-1252 and Latin-1 encodings.
- Detect decimal-comma and European thousands formats, Excel `sep=` preambles, comment lines, quoted punctuation and mixed datetime formats.
- Select any column for the X axis and one or more numerical Y series. Blank headers receive usable names; timestamps are detected from names and values.
- Plot series separately or as an overlay, switch time axes between Date / Time and Modified Julian Date (MJD), and filter by manual or quick time ranges.
- View summary statistics and apply adjustable sigma-based anomaly detection.
- Open a per-series pop-out inspector to select a range, switch the time-axis display, hide series, remove detected anomaly rows, estimate best-fit curves, and export the current view. **Reset All** restores the original data and plot settings.
- Calculate classic Allan deviation (ADEV) and overlapping Allan deviation (OADEV) for each separately plotted time series. Choose phase/time-error input and its units, or fractional-frequency input; choose octave or decade averaging-time spacing.
- Export plot reports as PNG, SVG, PDF or JPEG, including the selected series, dataset and axis details, range, anomaly information and summary statistics.

## Curve fitting

Use **Best Fit** in the pop-out inspector to compare linear, quadratic, cubic, exponential, logarithmic and power-law models for each visible series. The selected equation, normalized X definition, R², RMSE and AICc appear beside the plot. The model is selected using AICc to balance fit quality and model complexity. Fits use the current selected range and anomaly-filtered data; changing the view clears the fit so it can be recalculated for the new data.

## ADEV / OADEV data requirements

ADEV/OADEV is available for plots with a datetime or MJD X axis. The application derives the sample interval from the time column and checks that samples are evenly spaced. It reports an error for irregular timing or gaps rather than calculating from unsuitable input.

In the ADEV/OADEV window, select **Phase / time error** and the matching unit (seconds, milliseconds, microseconds, nanoseconds or picoseconds), or select **Fractional frequency** for dimensionless fractional-frequency values. The input type and units matter to the result. The window displays both ADEV and OADEV and lets you save the result plot.

## Test data and CSV format checks

A synthetic two-hour, 1 Hz clock dataset is available at `Test files/synthetic_clock_adev_test.csv`. It contains phase-error columns in nanoseconds and fractional-frequency columns for simulated optical, rubidium and OCXO clocks. The values are illustrative synthetic data, not measurements from specific hardware.

The format fixtures and loader integration tests are in `Test files/csv_format_compatibility/`. They cover the supported separators, decimal conventions, encodings, preambles, quoted fields, blank headers, mixed datetime strings and malformed input. Run them from the application folder with:

```powershell
.venv\Scripts\python.exe -m unittest discover -s "Test files\csv_format_compatibility" -v
```

## Requirements and installation

Python, PySide6, pandas, Matplotlib, Astropy and AllanTools are required. The pinned dependencies are listed in `requirements.txt`.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Running

From the application folder:

```powershell
.venv\Scripts\python.exe main.py
```

Load a CSV, choose an X axis and one or more Y series, set any desired time range or anomaly sensitivity, then click **Plot**.

## Code layout

- `main.py` starts the desktop application.
- `main_window.py` contains the main application window and plot controls.
- `plot_inspector.py` contains the embedded plot canvas and interactive pop-out inspector.
- `exporting.py` builds consistent report figures for saved plots.
- `allan_analysis.py` validates clock samples and calculates and plots ADEV/OADEV.
- `curve_fitting.py` compares candidate models and selects best fits with AICc.
- `data_analysis.py` loads CSV files, detects datetimes and provides statistics and anomaly detection.
- `analysis_cli.py` contains the legacy command-line workflow.
- `analysis.py` re-exports the analysis and command-line functions for compatibility.




