# Data Analysis Tool for Scientists

A PySide6 desktop application for loading CSV data, selecting scientific data series, filtering by time, plotting data with Matplotlib, viewing summary statistics, and exporting plots.

## Recent interface and plotting updates

### Y-series selection
- Y-series controls use a compact horizontal, scrollable selector.
- Numeric measurement columns can be selected independently.
- Selected series are visually highlighted and use colours matching their plotted series.
- Detected time columns remain available for the X axis but are excluded from Y-series choices.

### X-axis controls
- The X-axis selector has stronger visual styling so it is easier to identify.
- Detected time columns are highlighted in the selector.
- Selecting a non-time X axis shows a small inline `* Non-time X axis` notice rather than an intrusive warning.
- Time-specific controls are disabled when the X axis is not a detected time column.

### Date/time and MJD support
- Time columns are detected from datetime-like columns and MJD data.
- The displayed time axis can be switched between **Date / Time** and **MJD**.
- Start and end date/time controls show their corresponding MJD values alongside them.
- The End MJD value is positioned directly beside the End date/time control for a cleaner layout.

### Quick time ranges
The Time Range panel provides these shortcuts:

`Full` · `1h` · `2h` · `6h` · `12h` · `1d` · `2d` · `3d` · `7d` · `14d` · `30d`

Quick ranges are calculated backwards from the latest timestamp in the dataset and are constrained by the available data range.

The active quick-range option is visually highlighted so the selected range is clear.

### Plot layout
- **Separate plots** is now the default layout.
- **Overlay** remains available from the Layout selector.
- The Layout selector has updated styling to make it easier to distinguish from other controls.

### Plot export
Plots can be saved as:
- PNG
- SVG
- PDF
- JPEG

Raster exports provide selectable DPI settings of **300**, **600**, and **1200 DPI**.

### Statistics
For each selected Y series, the Statistics panel displays:
- Count
- Mean
- Median
- Standard deviation
- Minimum
- Maximum
- Range

Statistics use the same series colours as the corresponding plots.

## Core dependencies

- Python
- PySide6
- pandas
- Matplotlib
- Astropy

## Typical workflow

1. Click **Load CSV** and select a dataset.
2. Choose the X axis.
3. Select one or more Y series.
4. If using a time X axis, select a quick range or set Start and End manually.
5. Choose **Separate plots** or **Overlay**.
6. Choose **Date / Time** or **MJD** when applicable.
7. Click **Plot**.
8. Review the statistics and optionally save the plot.

## Notes

The application keeps native MJD values numeric while providing converted calendar date/time controls for selecting ranges. Date/time data can also be displayed as MJD when plotting.
