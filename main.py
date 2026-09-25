import sys
from pathlib import Path
import pandas as pd
from astropy.time import Time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QComboBox, QDateTimeEdit, QCheckBox
)
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QColor, QFont
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from analysis import load_csv, calculate_statistics
import matplotlib as mpl
mpl.rcParams["agg.path.chunksize"] = 10000

class PlotCanvas(FigureCanvasQTAgg):
    """Matplotlib canvas embedded inside the GUI."""

    def __init__(self):
        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)
        super().__init__(self.figure)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Analysis Tool")
        self.resize(1200, 700)

        self.data = None
        self.time_column = None
        self.possible_time_columns = []
        self.current_statistics = None
        self.current_plot_data = None
        self.current_display_x = None
        self.current_x_label = None
        self.current_y_column = None
        self.current_using_mjd = False

        self.file_label = QLabel("No CSV loaded")
        self.load_button = QPushButton("Load CSV")

        self.x_label = QLabel("X Axis")
        self.x_selector = QComboBox()
        self.y_label = QLabel("Y Axis")
        self.y_selector = QComboBox()
        self.plot_button = QPushButton("Plot")
        self.save_plot_button = QPushButton("Save Plot")
        self.save_plot_button.setEnabled(False)
        self.export_dpi_selector = QComboBox()
        self.export_dpi_selector.addItems(["300 DPI", "600 DPI", "1200 DPI"])
        self.export_dpi_selector.setCurrentText("1200 DPI")
        self.export_dpi_selector.setToolTip("Resolution used for raster exports such as PNG and JPEG")

        self.time_detection_label = QLabel("Possible time columns detected: none")

        # Choose the displayed time representation independently of the source format.
        self.time_axis_label = QLabel("Time axis")
        self.time_axis_selector = QComboBox()
        self.time_axis_selector.addItems(["Date / Time", "MJD"])
        self.time_axis_selector.setEnabled(False)

        self.start_label = QLabel("Start")
        self.start_time = QDateTimeEdit()
        self.start_mjd_label = QLabel("MJD: --")
        self.start_time.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        self.start_time.setCalendarPopup(True)

        self.end_label = QLabel("End")
        self.end_time = QDateTimeEdit()
        self.end_mjd_label = QLabel("MJD: --")
        self.end_time.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        self.end_time.setCalendarPopup(True)

        self.full_range_button = QPushButton("Full")
        self.one_hour_button = QPushButton("1h")
        self.six_hour_button = QPushButton("6h")
        self.day_button = QPushButton("24h")
        self.week_button = QPushButton("7d")
        self.month_button = QPushButton("30d")
        self.set_time_controls_enabled(False)

        self.canvas = PlotCanvas()

        self.stats_title = QLabel("Statistics")
        stats_title_font = QFont()
        stats_title_font.setBold(True)
        self.stats_title.setFont(stats_title_font)
        self.stats_label = QLabel("Load data and create a plot\nto see statistics.")

        self.status_label = QLabel("Ready")

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.file_label)
        main_layout.addWidget(self.load_button)
        main_layout.addWidget(self.time_detection_label)
        time_axis_display_layout = QHBoxLayout()
        time_axis_display_layout.addWidget(self.time_axis_label)
        time_axis_display_layout.addWidget(self.time_axis_selector)
        time_axis_display_layout.addStretch()
        main_layout.addLayout(time_axis_display_layout)

        axis_layout = QHBoxLayout()
        axis_layout.addWidget(self.x_label)
        axis_layout.addWidget(self.x_selector)
        axis_layout.addWidget(self.y_label)
        axis_layout.addWidget(self.y_selector)
        axis_layout.addWidget(self.plot_button)
        axis_layout.addWidget(self.save_plot_button)
        axis_layout.addWidget(self.export_dpi_selector)
        main_layout.addLayout(axis_layout)

        time_layout = QHBoxLayout()
        time_layout.addWidget(self.start_label)
        time_layout.addWidget(self.start_time)
        time_layout.addWidget(self.start_mjd_label)
        time_layout.addWidget(self.end_label)
        time_layout.addWidget(self.end_time)
        time_layout.addWidget(self.end_mjd_label)
        main_layout.addLayout(time_layout)

        quick_range_layout = QHBoxLayout()
        quick_range_layout.addWidget(QLabel("Quick range:"))
        quick_range_layout.addWidget(self.full_range_button)
        quick_range_layout.addWidget(self.one_hour_button)
        quick_range_layout.addWidget(self.six_hour_button)
        quick_range_layout.addWidget(self.day_button)
        quick_range_layout.addWidget(self.week_button)
        quick_range_layout.addWidget(self.month_button)
        quick_range_layout.addStretch()
        main_layout.addLayout(quick_range_layout)

        stats_layout = QVBoxLayout()
        stats_layout.addWidget(self.stats_title)
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        stats_widget = QWidget()
        stats_widget.setLayout(stats_layout)

        results_layout = QHBoxLayout()
        results_layout.addWidget(self.canvas, 4)
        results_layout.addWidget(stats_widget, 1)
        main_layout.addLayout(results_layout)
        main_layout.addWidget(self.status_label)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.load_button.clicked.connect(self.load_csv_file)
        self.plot_button.clicked.connect(self.create_plot)
        self.save_plot_button.clicked.connect(self.save_plot)
        self.x_selector.currentTextChanged.connect(self.x_axis_changed)
        self.full_range_button.clicked.connect(self.reset_time_range)
        self.one_hour_button.clicked.connect(lambda: self.set_quick_range(hours=1))
        self.six_hour_button.clicked.connect(lambda: self.set_quick_range(hours=6))
        self.day_button.clicked.connect(lambda: self.set_quick_range(hours=24))
        self.week_button.clicked.connect(lambda: self.set_quick_range(days=7))
        self.month_button.clicked.connect(lambda: self.set_quick_range(days=30))
        self.time_axis_selector.currentTextChanged.connect(self.time_axis_display_changed)
        self.start_time.dateTimeChanged.connect(self.update_mjd_reference_labels)
        self.end_time.dateTimeChanged.connect(self.update_mjd_reference_labels)

    def set_time_controls_enabled(self, enabled):
        controls = [
            self.start_time, self.end_time, self.full_range_button,
            self.one_hour_button, self.six_hour_button, self.day_button,
            self.week_button, self.month_button
        ]
        for control in controls:
            control.setEnabled(enabled)

    def detect_time_columns(self):
        """Find likely datetime and MJD columns without removing X-axis choices."""
        candidates = []
        if self.data is None:
            return candidates

        for column in self.data.columns:
            if self.is_mjd_column(column):
                numeric = pd.to_numeric(self.data[column], errors="coerce")
                if numeric.notna().any():
                    candidates.append(column)
                continue

            name_hint = "time" in str(column).lower() or "date" in str(column).lower()
            if pd.api.types.is_datetime64_any_dtype(self.data[column]):
                candidates.append(column)
                continue
            if name_hint:
                converted = pd.to_datetime(self.data[column], errors="coerce")
                if converted.notna().any():
                    candidates.append(column)
        return candidates

    def is_mjd_column(self, column):
        """Return True when a column name identifies Modified Julian Date."""
        normalised = str(column).strip().lower().replace("_", " ").replace("-", " ")
        return normalised == "mjd" or "modified julian date" in normalised

    def is_time_column(self, column):
        return column in self.possible_time_columns

    def pandas_to_qdatetime(self, timestamp):
        return QDateTime(
            timestamp.year, timestamp.month, timestamp.day,
            timestamp.hour, timestamp.minute, timestamp.second
        )

    @staticmethod
    def datetime_to_mjd(values):
        """Convert pandas/Python datetime values to MJD using Astropy UTC."""
        converted = pd.to_datetime(values, errors="coerce")
        scalar = isinstance(converted, pd.Timestamp)
        if scalar:
            if pd.isna(converted):
                return float("nan")
            return float(Time(converted.to_pydatetime(), scale="utc").mjd)

        valid_mask = ~pd.isna(converted)
        result = pd.Series(float("nan"), index=converted.index, dtype="float64")
        if valid_mask.any():
            datetimes = [value.to_pydatetime() for value in converted[valid_mask]]
            result.loc[valid_mask] = Time(datetimes, scale="utc").mjd
        return result

    @staticmethod
    def mjd_to_datetime(values):
        """Convert MJD values to pandas datetimes using Astropy UTC."""
        numeric = pd.to_numeric(values, errors="coerce")
        scalar = not hasattr(numeric, "index")
        if scalar:
            if pd.isna(numeric):
                return pd.NaT
            return pd.Timestamp(Time(float(numeric), format="mjd", scale="utc").to_datetime())

        result = pd.Series(pd.NaT, index=numeric.index, dtype="datetime64[ns]")
        valid_mask = numeric.notna()
        if valid_mask.any():
            converted = Time(
                numeric.loc[valid_mask].to_numpy(dtype=float),
                format="mjd",
                scale="utc"
            ).to_datetime()
            result.loc[valid_mask] = pd.to_datetime(converted)
        return result

    def update_mjd_reference_labels(self):
        """Show MJD equivalents beside the Start and End calendar controls."""
        try:
            start_dt = self.start_time.dateTime().toPython()
            end_dt = self.end_time.dateTime().toPython()
            self.start_mjd_label.setText(f"MJD: {Time(start_dt, scale='utc').mjd:.6f}")
            self.end_mjd_label.setText(f"MJD: {Time(end_dt, scale='utc').mjd:.6f}")
        except Exception:
            self.start_mjd_label.setText("MJD: --")
            self.end_mjd_label.setText("MJD: --")

    def set_time_range(self, column):
        if self.is_mjd_column(column):
            converted = self.mjd_to_datetime(self.data[column])
        else:
            converted = pd.to_datetime(self.data[column], errors="coerce")

        if converted.notna().sum() == 0:
            raise ValueError(f"'{column}' could not be interpreted as a time column.")

        # Keep native MJD numeric. Calendar controls use a converted datetime view only.
        if not self.is_mjd_column(column):
            self.data[column] = converted

        valid = converted.dropna()
        minimum = valid.min()
        maximum = valid.max()
        minimum_qt = self.pandas_to_qdatetime(minimum)
        maximum_qt = self.pandas_to_qdatetime(maximum)

        self.start_time.setDateTimeRange(minimum_qt, maximum_qt)
        self.end_time.setDateTimeRange(minimum_qt, maximum_qt)
        self.start_time.setDateTime(minimum_qt)
        self.end_time.setDateTime(maximum_qt)
        self.time_column = column
        self.set_time_controls_enabled(True)
        self.update_mjd_reference_labels()

    def reset_time_range(self):
        if self.data is not None and self.time_column is not None:
            self.set_time_range(self.time_column)
            self.status_label.setText("Time range reset to full dataset.")

    def set_quick_range(self, hours=None, days=None):
        if self.data is None or self.time_column is None:
            return

        column = self.time_column
        if self.is_mjd_column(column):
            valid = self.mjd_to_datetime(self.data[column]).dropna()
        else:
            valid = pd.to_datetime(self.data[column], errors="coerce").dropna()
        if valid.empty:
            return
        minimum = valid.min()
        maximum = valid.max()

        if hours is not None:
            start = maximum - pd.Timedelta(hours=hours)
        elif days is not None:
            start = maximum - pd.Timedelta(days=days)
        else:
            start = minimum

        start = max(start, minimum)
        self.start_time.setDateTime(self.pandas_to_qdatetime(start))
        self.end_time.setDateTime(self.pandas_to_qdatetime(maximum))

    def x_axis_changed(self, column):
        if self.data is None or not column:
            return
        if self.is_time_column(column):
            self.time_axis_selector.setEnabled(True)
            self.time_axis_selector.blockSignals(True)
            self.time_axis_selector.setCurrentText(
                "MJD" if self.is_mjd_column(column) else "Date / Time"
            )
            self.time_axis_selector.blockSignals(False)
            try:
                self.set_time_range(column)
            except Exception as error:
                self.status_label.setText(f"Error reading time column: {error}")
        else:
            self.time_column = None
            self.time_axis_selector.setEnabled(False)
            self.set_time_controls_enabled(False)

    def time_axis_display_changed(self):
        """Redraw when the selected time-axis representation changes."""
        if self.data is not None and self.is_time_column(self.x_selector.currentText()):
            self.create_plot()

    def highlight_time_columns(self):
        for index in range(self.x_selector.count()):
            column = self.x_selector.itemText(index)
            if self.is_time_column(column):
                self.x_selector.setItemData(index, QColor("#1976D2"), Qt.ForegroundRole)
                font = QFont(self.x_selector.font())
                font.setBold(True)
                self.x_selector.setItemData(index, font, Qt.FontRole)

    def load_csv_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open CSV File", "", "CSV Files (*.csv)"
        )
        if not filepath:
            return

        try:
            self.data = load_csv(filepath)
            self.current_statistics = None
            self.current_plot_data = None
            self.current_display_x = None
            self.save_plot_button.setEnabled(False)
            self.file_label.setText(filepath)
            self.x_selector.clear()
            self.y_selector.clear()

            # X axis deliberately contains every column, including timestamps.
            all_columns = list(self.data.columns)
            self.x_selector.addItems(all_columns)

            self.possible_time_columns = self.detect_time_columns()
            if self.possible_time_columns:
                self.time_detection_label.setText(
                    "Possible time columns detected: " + ", ".join(self.possible_time_columns)
                )
            else:
                self.time_detection_label.setText("Possible time columns detected: none")
            self.highlight_time_columns()

            # Y axis contains numeric measurement columns only.
            # Detected datetime/MJD time columns remain available on X, but are
            # deliberately excluded from Y even when their source data is numeric.
            numeric_columns = self.data.select_dtypes(include="number").columns.tolist()
            y_columns = [
                column for column in numeric_columns
                if column not in self.possible_time_columns
            ]
            self.y_selector.addItems(y_columns)

            if self.possible_time_columns:
                first_time = self.possible_time_columns[0]
                self.x_selector.setCurrentText(first_time)
                self.set_time_range(first_time)
                self.time_axis_selector.blockSignals(True)
                self.time_axis_selector.setCurrentText(
                    "MJD" if self.is_mjd_column(first_time) else "Date / Time"
                )
                self.time_axis_selector.setEnabled(True)
                self.time_axis_selector.blockSignals(False)
            else:
                self.time_column = None
                self.time_axis_selector.setEnabled(False)
                self.set_time_controls_enabled(False)

            self.stats_label.setText("Select axes and press Plot.")
            self.status_label.setText(f"Loaded {len(self.data)} rows")
        except Exception as error:
            self.status_label.setText(f"Error: {error}")

    def save_plot(self):
        """Save a report-style figure containing the plot and statistics panel."""
        filepath, selected_filter = QFileDialog.getSaveFileName(
            self, "Save Plot", "plot.png",
            "PNG Image (*.png);;SVG Vector Image (*.svg);;PDF Document (*.pdf);;JPEG Image (*.jpg *.jpeg)"
        )
        if not filepath:
            return

        if self.current_statistics is None or self.current_plot_data is None:
            self.status_label.setText("Create a plot before saving.")
            return

        try:
            path = Path(filepath)
            if not path.suffix:
                if "SVG" in selected_filter:
                    filepath += ".svg"
                elif "PDF" in selected_filter:
                    filepath += ".pdf"
                elif "JPEG" in selected_filter:
                    filepath += ".jpg"
                else:
                    filepath += ".png"

            export_figure = Figure(figsize=(12, 7))
            grid = export_figure.add_gridspec(1, 2, width_ratios=[4, 1], wspace=0.22)
            plot_axes = export_figure.add_subplot(grid[0, 0])
            stats_axes = export_figure.add_subplot(grid[0, 1])

            plot_axes.plot(self.current_display_x, self.current_plot_data[self.current_y_column])
            if self.current_using_mjd:
                plot_axes.ticklabel_format(axis="x", style="plain", useOffset=False)
            plot_axes.set_xlabel(self.current_x_label)
            plot_axes.set_ylabel(self.current_y_column)
            plot_axes.set_title(f"{self.current_y_column} vs {self.current_x_label}")
            plot_axes.grid(True)
            if self.is_time_column(self.x_selector.currentText()) and not self.current_using_mjd:
                export_figure.autofmt_xdate()

            statistics = self.current_statistics
            stats_lines = [
                "Statistics",
                "",
                f"Count   {statistics['count']}",
                f"Mean    {statistics['mean']:.6g}",
                f"Median  {statistics['median']:.6g}",
                f"Std dev {statistics['std_dev']:.6g}",
                f"Minimum {statistics['min']:.6g}",
                f"Maximum {statistics['max']:.6g}",
                f"Range   {statistics['range']:.6g}",
            ]

            if self.is_time_column(self.x_selector.currentText()):
                start_dt = self.start_time.dateTime().toPython()
                end_dt = self.end_time.dateTime().toPython()
                stats_lines.extend([
                    "",
                    "Selected time range",
                    start_dt.strftime("Start  %d/%m/%Y %H:%M:%S"),
                    end_dt.strftime("End    %d/%m/%Y %H:%M:%S"),
                    "",
                    f"Start MJD {Time(start_dt, scale='utc').mjd:.6f}",
                    f"End MJD   {Time(end_dt, scale='utc').mjd:.6f}",
                ])

            stats_axes.axis("off")
            stats_axes.text(
                0.02, 0.98, "\n".join(stats_lines),
                transform=stats_axes.transAxes,
                va="top", ha="left",
                fontsize=10, linespacing=1.45
            )

            export_dpi = int(self.export_dpi_selector.currentText().split()[0])
            export_figure.savefig(filepath, dpi=export_dpi, bbox_inches="tight")
            export_figure.clear()
            self.status_label.setText(f"Plot saved with statistics: {filepath}")
        except Exception as error:
            self.status_label.setText(f"Error saving plot: {error}")

    def create_plot(self):
        """Filter by the GUI time range, calculate stats, and redraw embedded canvas."""
        if self.data is None:
            self.status_label.setText("Please load a CSV first.")
            return

        x_column = self.x_selector.currentText()
        y_column = self.y_selector.currentText()
        if not x_column or not y_column:
            self.status_label.setText("Please select both X and Y axes.")
            return

        try:
            plot_data = self.data

            if self.is_time_column(x_column):
                if self.is_mjd_column(x_column):
                    series = self.mjd_to_datetime(self.data[x_column])
                else:
                    series = pd.to_datetime(self.data[x_column], errors="coerce")
                start = pd.Timestamp(self.start_time.dateTime().toPython())
                end = pd.Timestamp(self.end_time.dateTime().toPython())
                if start > end:
                    raise ValueError("Start time must be before end time.")

                mask = series.notna() & (series >= start) & (series <= end)
                plot_data = self.data.loc[mask].copy()
                if not self.is_mjd_column(x_column):
                    plot_data[x_column] = series.loc[mask]
                if plot_data.empty:
                    raise ValueError("No data exists in the selected time range.")

            statistics = calculate_statistics(plot_data, y_column)

            self.canvas.axes.clear()

            display_x = plot_data[x_column]
            x_label = x_column
            native_mjd = self.is_mjd_column(x_column)
            using_mjd = (
                self.is_time_column(x_column)
                and self.time_axis_selector.currentText() == "MJD"
            )

            if self.is_time_column(x_column):
                if using_mjd:
                    if native_mjd:
                        display_x = pd.to_numeric(plot_data[x_column], errors="coerce")
                    else:
                        display_x = self.datetime_to_mjd(plot_data[x_column])
                    x_label = "MJD"
                else:
                    if native_mjd:
                        display_x = self.mjd_to_datetime(plot_data[x_column])
                    else:
                        display_x = pd.to_datetime(plot_data[x_column], errors="coerce")
                    x_label = "Date / Time"

            self.current_statistics = statistics
            self.current_plot_data = plot_data.copy()
            self.current_display_x = display_x.copy() if hasattr(display_x, "copy") else display_x
            self.current_x_label = x_label
            self.current_y_column = y_column
            self.current_using_mjd = using_mjd

            self.canvas.axes.plot(display_x, plot_data[y_column])
            if using_mjd:
                self.canvas.axes.ticklabel_format(axis="x", style="plain", useOffset=False)
            self.canvas.axes.set_xlabel(x_label)
            self.canvas.axes.set_ylabel(y_column)
            self.canvas.axes.set_title(f"{y_column} vs {x_label}")
            self.canvas.axes.grid(True)

            if self.is_time_column(x_column) and not using_mjd:
                self.canvas.figure.autofmt_xdate()
            self.canvas.figure.tight_layout()

            # Embedded Qt canvas: redraw only. Do not call plt.show(), which
            # would try to start a second GUI event loop.
            self.canvas.draw_idle()
            self.save_plot_button.setEnabled(True)

            stats_text = (
                f"Count\n{statistics['count']}\n\n"
                f"Mean\n{statistics['mean']:.6g}\n\n"
                f"Median\n{statistics['median']:.6g}\n\n"
                f"Standard deviation\n{statistics['std_dev']:.6g}\n\n"
                f"Minimum\n{statistics['min']:.6g}\n\n"
                f"Maximum\n{statistics['max']:.6g}\n\n"
                f"Range\n{statistics['range']:.6g}"
            )
            self.stats_label.setText(stats_text)
            self.status_label.setText(
                f"Plotted {len(plot_data)} points: {y_column} vs {x_column}"
            )
        except Exception as error:
            self.status_label.setText(f"Error: {error}")


def main():
    app = QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    if owns_app:
        sys.exit(app.exec())
    return window


if __name__ == "__main__":
    main()
