# Data Analysis Tool for Scientists

A PySide6 desktop application for loading CSV datasets, exploring numerical series, handling time-based data, identifying potential anomalies and exporting plots.

## Features

- Load and inspect CSV datasets.
- Select any column for the X axis and one or more numerical Y series.
- Plot series separately or as an overlay.
- Automatic datetime detection using column names, data types and datetime-like column contents, including columns with missing or misleading headers.
- Native Modified Julian Date (MJD) support with Date / Time and MJD display switching.
- Manual start/end time filtering plus quick ranges from 1 hour to 30 days.
- Summary statistics for each plotted series.
- Adjustable sigma-based anomaly detection with optional plot markers.
- Interactive pop-out plot inspector with range selection and axis switching.
- Export plots as PNG, SVG, PDF or JPEG, with selectable raster DPI.

## Requirements

- Python
- PySide6
- pandas
- Matplotlib
- Astropy

Install dependencies with:

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

Load a CSV, choose the X and Y axes, adjust the time range or anomaly sensitivity if required, then click **Plot**.

## Notes

Datetime-like text columns are inferred from their contents when a useful header is unavailable. Numeric columns are not automatically treated as datetimes, helping avoid false detection of ordinary measurement or index data.
