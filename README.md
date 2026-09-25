# Data Analysis Tool for Scientists

A Python desktop application for loading, exploring, plotting and exporting scientific CSV data, with dedicated support for conventional date/time values and Modified Julian Date (MJD).

## Current Features

### CSV and data handling

- Load CSV datasets through a desktop file picker.
- Automatically detect likely datetime and MJD columns.
- Keep all columns available for the X axis.
- Restrict the Y axis to numeric measurement columns while excluding detected time columns.
- Highlight detected time columns in blue and bold in the X-axis selector.
- Configure Matplotlib path chunking for large plotted datasets.

### Time and MJD support

- Work with CSV files containing standard date/time values.
- Work with CSV files containing native Modified Julian Date values.
- Convert between Date/Time and MJD using `astropy.time.Time`.
- Display either Date/Time or MJD regardless of the time format stored in the source CSV.
- Show live MJD equivalents beside the selected Start and End date/time controls.

### Time-range selection

The application provides Start and End controls for filtering time-series data, along with quick-range buttons for:

- Full dataset
- 1 hour
- 6 hours
- 24 hours
- 7 days
- 30 days

Statistics and plots are calculated from the currently selected range.

### Plotting

- Matplotlib plot embedded directly in the PySide6 interface.
- Selectable X and Y columns.
- Automatic date formatting for Date/Time axes.
- Plain full-value formatting for MJD axes.
- Axis labels, plot title and grid.

### Statistics

The statistics panel displays:

- Count
- Mean
- Median
- Standard deviation
- Minimum
- Maximum
- Range

Statistics update for the data included in the current plot.

### Plot export

Plots can be exported as:

- PNG
- JPEG
- PDF
- SVG

The exported report-style figure includes:

- The plotted data
- Statistics panel
- Selected Start and End date/times when a time axis is used
- Corresponding Start and End MJD values

## Technology

- Python
- PySide6
- pandas
- Matplotlib
- Astropy

## Project Structure

The current application uses:

- `main.py` for the PySide6 interface, time handling, plotting and export workflow.
- `analysis.py` for CSV loading and statistical calculations.

## Running the Application

Activate the project's Python environment, ensure the required packages are installed, then run:

```bash
python main.py
```

## Current Status

The project currently provides a working foundation for interactive scientific CSV analysis, including time-range filtering, Date/Time and MJD interoperability, descriptive statistics, plotting and report-style figure export.

Further functionality can be added incrementally while retaining the current working application as a baseline.
