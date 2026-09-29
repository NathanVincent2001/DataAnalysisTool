import sys
from pathlib import Path
import pandas as pd
from astropy.time import Time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QComboBox, QDateTimeEdit, QGroupBox, QGridLayout, QCheckBox, QScrollArea
)
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtGui import QColor, QFont, QPalette
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
        self.current_y_columns = []
        self.current_plot_mode = "Separate plots"
        self.current_series_colours = {}
        self.current_using_mjd = False

        self.file_label = QLabel("No CSV loaded")
        self.load_button = QPushButton("Load CSV")
        self.load_button.setObjectName("loadButton")
        self.load_button.setMinimumSize(140, 36)

        self.x_label = QLabel("X Axis")
        self.x_selector = QComboBox()
        self.x_selector.setObjectName("xAxisSelector")
        self.x_selector.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.x_selector.setMinimumContentsLength(10)
        self.y_label = QLabel("Y Axes")
        self.y_selector = QGroupBox("Choose Y series")
        y_selector_layout = QVBoxLayout(self.y_selector)
        y_selector_layout.setContentsMargins(6, 8, 6, 6)
        self.y_scroll = QScrollArea()
        self.y_scroll.setWidgetResizable(True)
        self.y_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.y_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.y_scroll.setFrameShape(QScrollArea.NoFrame)
        self.y_scroll.setFixedHeight(48)
        self.y_scroll_content = QWidget()
        self.y_grid = QGridLayout(self.y_scroll_content)
        self.y_grid.setContentsMargins(2, 2, 2, 2)
        self.y_grid.setHorizontalSpacing(10)
        self.y_grid.setVerticalSpacing(0)
        self.y_grid.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.y_scroll.setWidget(self.y_scroll_content)
        y_selector_layout.addWidget(self.y_scroll)
        self.y_selector.setFixedHeight(78)
        self.y_checkboxes = []
        self.plot_mode_label = QLabel("Layout")
        self.plot_mode_selector = QComboBox()
        self.plot_mode_selector.addItems(["Overlay", "Separate plots"])
        self.plot_mode_selector.setCurrentText("Separate plots")
        self.plot_mode_selector.setObjectName("layoutSelector")
        self.plot_mode_selector.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.plot_button = QPushButton("Plot")
        self.plot_button.setObjectName("plotButton")
        self.plot_button.setMinimumSize(155, 38)
        self.save_plot_button = QPushButton("Save Plot")
        self.save_plot_button.setObjectName("saveButton")
        self.save_plot_button.setMinimumSize(120, 36)
        self.save_plot_button.setEnabled(False)
        self.export_dpi_selector = QComboBox()
        self.export_dpi_selector.addItems(["300 DPI", "600 DPI", "1200 DPI"])
        self.export_dpi_selector.setCurrentText("1200 DPI")
        self.export_dpi_selector.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.export_dpi_selector.setToolTip("Resolution used for raster exports such as PNG and JPEG")

        self.time_detection_label = QLabel("Possible time columns detected: none")
        self.x_axis_warning = QLabel("")
        self.x_axis_warning.setObjectName("xAxisWarning")
        self.x_axis_warning.setVisible(False)

        # Choose the displayed time representation independently of the source format.
        self.time_axis_label = QLabel("Time axis")
        self.time_axis_selector = QComboBox()
        self.time_axis_selector.addItems(["Date / Time", "MJD"])
        self.time_axis_selector.setObjectName("timeAxisSelector")
        self.time_axis_selector.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.time_axis_selector.setMinimumWidth(120)
        self.time_axis_selector.setMinimumHeight(34)
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
        self.two_hour_button = QPushButton("2h")
        self.six_hour_button = QPushButton("6h")
        self.twelve_hour_button = QPushButton("12h")
        self.day_button = QPushButton("1d")
        self.two_day_button = QPushButton("2d")
        self.three_day_button = QPushButton("3d")
        self.week_button = QPushButton("7d")
        self.fortnight_button = QPushButton("14d")
        self.month_button = QPushButton("30d")
        self.full_range_button.setObjectName("fullRangeButton")
        self.quick_range_buttons = [
            self.full_range_button, self.one_hour_button, self.two_hour_button,
            self.six_hour_button, self.twelve_hour_button, self.day_button,
            self.two_day_button, self.three_day_button, self.week_button,
            self.fortnight_button, self.month_button
        ]
        for button in (
            self.full_range_button, self.one_hour_button, self.two_hour_button,
            self.six_hour_button, self.twelve_hour_button, self.day_button,
            self.two_day_button, self.three_day_button, self.week_button,
            self.fortnight_button, self.month_button
        ):
            button.setProperty("quickRange", True)
            button.setMinimumSize(58, 27)
        self.set_time_controls_enabled(False)

        self.canvas = PlotCanvas()

        self.stats_title = QLabel("Statistics")
        stats_title_font = QFont()
        stats_title_font.setPointSize(15)
        stats_title_font.setBold(True)
        self.stats_title.setFont(stats_title_font)
        self.stats_title.setObjectName("statsTitle")
        self.stats_title.setMinimumHeight(28)
        self.stats_label = QLabel("Load data and create a plot\nto see statistics.")

        self.status_label = QLabel("Ready")

        # Visual hierarchy and layout
        self.full_range_button.setProperty("selected", True)
        self.setStyleSheet("""
            QMainWindow { background: #f4f7fb; }
            QLabel { color: #243447; }
            QLabel#statsTitle {
                color: #172033; font-size: 18px; font-weight: 800;
                padding: 4px 0 6px 0;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d8e0ea;
                border-radius: 9px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: 600;
                color: #243447;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
            QComboBox, QDateTimeEdit {
                min-height: 26px; padding: 1px 7px; border: 1px solid #bcc8d6;
                border-radius: 6px; background: white; color: #1f2937;
            }
            QPushButton { border-radius: 7px; padding: 5px 12px; font-weight: 600; }
            QPushButton#loadButton { background: #1976d2; color: white; border: none; font-size: 14px; }
            QPushButton#loadButton:hover { background: #1565c0; }
            QPushButton#plotButton { background: #2e9d57; color: white; border: none; font-size: 15px; font-weight: 700; }
            QPushButton#plotButton:hover { background: #258348; }
            QPushButton#saveButton { background: #008b95; color: white; border: none; }
            QPushButton#saveButton:hover { background: #00747c; }
            QPushButton#saveButton:disabled { background: #b9c5cc; color: #eef2f4; }
            QPushButton[quickRange="true"] {
                background: #edf2f7; color: #334155; border: 1px solid #cbd5e1;
                border-radius: 5px; padding: 5px 10px;
            }
            QPushButton[quickRange="true"]:hover { background: #dbeafe; border-color: #93c5fd; }
            QPushButton[selected="true"] {
                background: #dbeafe; color: #1558a6; border: 1px solid #93c5fd; font-weight: 700;
            }
            QComboBox#timeAxisSelector { border: 2px solid #80aee0; background: #f4f9ff; font-weight: 600; }
            QComboBox#xAxisSelector {
                border: 2px solid #6aa7df; background: #f4f9ff; color: #173f68;
                font-weight: 700; min-height: 30px;
            }
            QComboBox#xAxisSelector:hover { border-color: #347fc4; background: #eaf4ff; }
            QComboBox#layoutSelector {
                border: 2px solid #72a98a; background: #f3faf6; color: #285b3d;
                font-weight: 700; min-height: 30px;
            }
            QComboBox#layoutSelector:hover { border-color: #3f8d63; background: #e8f6ee; }
            QLabel#xAxisWarning {
                color: #9a6700; font-size: 11px; font-style: italic;
                padding-left: 2px;
            }
            QCheckBox { color: #334155; }
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(6)

        # Top-left primary data action.
        file_bar = QHBoxLayout()
        file_bar.setSpacing(12)
        file_bar.addWidget(self.load_button)
        file_bar.addWidget(self.file_label, 1)
        main_layout.addLayout(file_bar)
        main_layout.addWidget(self.time_detection_label)

        # Plot setup keeps all plotting choices together.
        plot_setup = QGroupBox("Plot Setup")
        plot_setup_layout = QVBoxLayout(plot_setup)
        plot_setup_layout.setContentsMargins(10, 12, 10, 8)
        plot_setup_layout.setSpacing(5)

        setup_top = QHBoxLayout()
        setup_top.setSpacing(10)
        setup_top.addWidget(self.x_label)
        setup_top.addWidget(self.x_selector)
        setup_top.addWidget(self.x_axis_warning)
        setup_top.addStretch(1)
        setup_top.addWidget(self.plot_mode_label)
        setup_top.addWidget(self.plot_mode_selector)

        time_axis_group = QGroupBox("Time axis")
        time_axis_group_layout = QHBoxLayout(time_axis_group)
        time_axis_group_layout.setContentsMargins(8, 10, 8, 5)
        time_axis_group_layout.addWidget(self.time_axis_selector)
        setup_top.addWidget(time_axis_group)
        plot_setup_layout.addLayout(setup_top)

        # Retain the successful checkbox grid for selecting Y series.
        plot_setup_layout.addWidget(self.y_selector)

        action_row = QHBoxLayout()
        action_row.addStretch()
        action_row.addWidget(self.export_dpi_selector)
        action_row.addWidget(self.save_plot_button)
        action_row.addWidget(self.plot_button)
        plot_setup_layout.addLayout(action_row)
        main_layout.addWidget(plot_setup, 0)

        # Time range controls are visually separated from plot configuration.
        time_range_group = QGroupBox("Time Range")
        time_range_group_layout = QVBoxLayout(time_range_group)
        time_range_group_layout.setContentsMargins(10, 12, 10, 7)
        time_range_group_layout.setSpacing(4)
        time_layout = QHBoxLayout()
        time_layout.addWidget(self.start_label)
        self.start_time.setFixedWidth(220)
        time_layout.addWidget(self.start_time)
        time_layout.addWidget(self.start_mjd_label)
        time_layout.addSpacing(16)
        time_layout.addWidget(self.end_label)
        self.end_time.setFixedWidth(220)
        time_layout.addWidget(self.end_time)
        time_layout.addWidget(self.end_mjd_label)
        time_layout.addStretch(1)
        time_range_group_layout.addLayout(time_layout)

        quick_range_layout = QHBoxLayout()
        quick_range_layout.setSpacing(4)
        quick_range_layout.addWidget(QLabel("Quick range:"))
        quick_range_layout.addWidget(self.full_range_button)
        quick_range_layout.addWidget(self.one_hour_button)
        quick_range_layout.addWidget(self.two_hour_button)
        quick_range_layout.addWidget(self.six_hour_button)
        quick_range_layout.addWidget(self.twelve_hour_button)
        quick_range_layout.addWidget(self.day_button)
        quick_range_layout.addWidget(self.two_day_button)
        quick_range_layout.addWidget(self.three_day_button)
        quick_range_layout.addWidget(self.week_button)
        quick_range_layout.addWidget(self.fortnight_button)
        quick_range_layout.addWidget(self.month_button)
        quick_range_layout.addStretch()
        time_range_group_layout.addLayout(quick_range_layout)
        time_range_group.setMaximumHeight(120)
        main_layout.addWidget(time_range_group, 0)

        stats_layout = QVBoxLayout()
        stats_layout.setContentsMargins(10, 8, 10, 8)
        stats_layout.addWidget(self.stats_title)
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        stats_widget = QWidget()
        stats_widget.setLayout(stats_layout)
        results_layout = QHBoxLayout()
        results_layout.setSpacing(14)
        results_layout.addWidget(self.canvas, 4)
        results_layout.addWidget(stats_widget, 1)
        main_layout.addLayout(results_layout, 4)
        main_layout.addWidget(self.status_label)
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)
        self.load_button.clicked.connect(self.load_csv_file)
        self.plot_button.clicked.connect(self.create_plot)
        self.save_plot_button.clicked.connect(self.save_plot)
        self.x_selector.currentTextChanged.connect(self.x_axis_changed)
        self.full_range_button.clicked.connect(lambda: self.reset_time_range(self.full_range_button))
        self.one_hour_button.clicked.connect(lambda: self.set_quick_range(hours=1, button=self.one_hour_button))
        self.two_hour_button.clicked.connect(lambda: self.set_quick_range(hours=2, button=self.two_hour_button))
        self.six_hour_button.clicked.connect(lambda: self.set_quick_range(hours=6, button=self.six_hour_button))
        self.twelve_hour_button.clicked.connect(lambda: self.set_quick_range(hours=12, button=self.twelve_hour_button))
        self.day_button.clicked.connect(lambda: self.set_quick_range(days=1, button=self.day_button))
        self.two_day_button.clicked.connect(lambda: self.set_quick_range(days=2, button=self.two_day_button))
        self.three_day_button.clicked.connect(lambda: self.set_quick_range(days=3, button=self.three_day_button))
        self.week_button.clicked.connect(lambda: self.set_quick_range(days=7, button=self.week_button))
        self.fortnight_button.clicked.connect(lambda: self.set_quick_range(days=14, button=self.fortnight_button))
        self.month_button.clicked.connect(lambda: self.set_quick_range(days=30, button=self.month_button))
        self.time_axis_selector.currentTextChanged.connect(self.time_axis_display_changed)
        self.start_time.dateTimeChanged.connect(self.update_mjd_reference_labels)
        self.end_time.dateTimeChanged.connect(self.update_mjd_reference_labels)

    def set_time_controls_enabled(self, enabled):
        controls = [
            self.start_time, self.end_time, self.full_range_button,
            self.one_hour_button, self.two_hour_button, self.six_hour_button,
            self.twelve_hour_button, self.day_button, self.two_day_button,
            self.three_day_button, self.week_button, self.fortnight_button,
            self.month_button
        ]
        for control in controls:
            control.setEnabled(enabled)

    def normalise_datetime_columns(self):
        """
        Convert all detected datetime columns to timezone-naive
        datetime64[ns] values.

        Handles:
            2026-08-25 13:09:41
            2026-08-25T13:09:41+01:00
            2026-08-25T12:09:41Z

        by converting through UTC then removing timezone information.
        """

        if self.data is None:
            return

        for column in self.data.columns:

            if self.is_mjd_column(column):
                continue

            column_name = str(column).lower()

            looks_like_time = (
                "time" in column_name
                or "date" in column_name
            )

            already_datetime = pd.api.types.is_datetime64_any_dtype(
                self.data[column]
            )

            if not looks_like_time and not already_datetime:
                continue

            try:
                converted = pd.to_datetime(
                    self.data[column],
                    errors="coerce",
                    utc=True
                )

                if converted.notna().any():

                    converted = converted.dt.tz_localize(None)

                    self.data[column] = converted

            except Exception:
                pass


    def detect_time_columns(self):
        """Find likely datetime and MJD columns."""
        candidates = []
        if self.data is None:
            return candidates
        for column in self.data.columns:
            if self.is_mjd_column(column):
                numeric = pd.to_numeric(
                    self.data[column],
                    errors="coerce"
                )
                if numeric.notna().any():
                    candidates.append(column)
                continue
            if pd.api.types.is_datetime64_any_dtype(
                self.data[column]
            ):
                candidates.append(column)
                continue
            name_hint = (
                "time" in str(column).lower()
                or "date" in str(column).lower()
            )
            if name_hint:
                converted = pd.to_datetime(
                    self.data[column],
                    errors="coerce"
                )
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
            converted = self.data[column]

        if converted.notna().sum() == 0:
            raise ValueError(f"'{column}' could not be interpreted as a time column.")

        # Keep native MJD numeric. Calendar controls use a converted datetime view only.

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

    def set_quick_range_highlight(self, selected_button):
        """Highlight only the active quick-range button."""
        for quick_button in self.quick_range_buttons:
            quick_button.setProperty("selected", quick_button is selected_button)
            quick_button.style().unpolish(quick_button)
            quick_button.style().polish(quick_button)
            quick_button.update()

    def reset_time_range(self, button=None):
        if self.data is not None and self.time_column is not None:
            self.set_time_range(self.time_column)
            self.set_quick_range_highlight(button or self.full_range_button)
            self.status_label.setText("Time range reset to full dataset.")

    def set_quick_range(self, hours=None, days=None, button=None):
        if self.data is None or self.time_column is None:
            return
        column = self.time_column
        if self.is_mjd_column(column):
            valid = self.mjd_to_datetime(self.data[column]).dropna()
        else:
            valid = self.data[column].dropna()
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
        if button is not None:
            self.set_quick_range_highlight(button)

    def x_axis_changed(self, column):
        if self.data is None or not column:
            self.x_axis_warning.setVisible(False)
            return
        is_time = self.is_time_column(column)
        self.x_axis_warning.setText("* Non-time X axis")
        self.x_axis_warning.setVisible(not is_time)
        if is_time:
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
            # Normalise all timestamp columns immediately.
            self.normalise_datetime_columns()

            self.current_statistics = None
            self.current_plot_data = None
            self.current_display_x = None
            self.save_plot_button.setEnabled(False)
            self.file_label.setText(filepath)
            self.x_selector.clear()
            while self.y_grid.count():
                child = self.y_grid.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            self.y_checkboxes.clear()

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
            for index, column in enumerate(y_columns):
                checkbox = QCheckBox(column)
                checkbox.setChecked(index == 0)
                checkbox.setToolTip(f"Include {column} in the plot")
                checkbox.setFixedHeight(30)
                checkbox.setMinimumWidth(150)
                checkbox.setMaximumWidth(210)
                checkbox.stateChanged.connect(
                    lambda _state: self.update_y_selector_colours(self.current_series_colours)
                )
                self.y_checkboxes.append(checkbox)
                self.y_grid.addWidget(
                    checkbox, 0, index,
                    alignment=Qt.AlignLeft | Qt.AlignVCenter
                )
            self.y_grid.setColumnStretch(len(y_columns), 1)
            self.update_y_selector_colours()

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

    def selected_y_columns(self):
        return [checkbox.text() for checkbox in self.y_checkboxes if checkbox.isChecked()]

    @staticmethod
    def qt_colour_string(colour):
        """Convert any Matplotlib colour representation to Qt/HTML-safe hex."""
        try:
            return mpl.colors.to_hex(colour, keep_alpha=False)
        except (ValueError, TypeError):
            return "#1976D2"

    def series_colours(self, y_columns):
        colour_cycle = mpl.rcParams["axes.prop_cycle"].by_key().get("color", ["#1f77b4"])
        return {
            column: self.qt_colour_string(colour_cycle[i % len(colour_cycle)])
            for i, column in enumerate(y_columns)
        }

    def update_y_selector_colours(self, colours=None):
        colours = colours or {}
        for checkbox in self.y_checkboxes:
            selected = checkbox.isChecked()
            colour = self.qt_colour_string(colours.get(checkbox.text(), "#1976D2"))
            if selected:
                checkbox.setStyleSheet(
                    f"QCheckBox {{ color: {colour}; font-weight: bold; "
                    "background-color: #eaf3ff; border: 1px solid #8fbbe8; "
                    "border-radius: 6px; padding: 5px 8px; }}"
                    "QCheckBox:hover { background-color: #dcecff; border-color: #5f9ed6; }"
                    "QCheckBox::indicator { width: 16px; height: 16px; }"
                )
            else:
                checkbox.setStyleSheet(
                    "QCheckBox { color: #334155; font-weight: normal; "
                    "background-color: #f8fafc; border: 1px solid #cbd5e1; "
                    "border-radius: 6px; padding: 5px 8px; }"
                    "QCheckBox:hover { background-color: #eef6ff; border-color: #93b9df; }"
                    "QCheckBox::indicator { width: 16px; height: 16px; }"
                )

    def statistics_html(self, statistics_by_column, colours):
        blocks = []
        for column, statistics in statistics_by_column.items():
            colour = self.qt_colour_string(colours.get(column, "#222222"))
            blocks.append(
                f'<span style="color: {colour}; font-weight: 700; font-size: 12pt;">{column}</span><br>'
                f"Count: {statistics['count']}<br>"
                f"Mean: {statistics['mean']:.6g}<br>"
                f"Median: {statistics['median']:.6g}<br>"
                f"Std dev: {statistics['std_dev']:.6g}<br>"
                f"Min: {statistics['min']:.6g}<br>"
                f"Max: {statistics['max']:.6g}<br>"
                f"Range: {statistics['range']:.6g}"
            )
        return "<br><br>".join(blocks)

    def draw_series(self, figure, display_x, plot_data, x_label, y_columns, mode, using_mjd, colours):
        figure.clear()
        if mode == "Overlay":
            axes = [figure.add_subplot(111)]
            ax = axes[0]
            for column in y_columns:
                ax.plot(display_x, plot_data[column], label=column, color=colours[column])
            ax.set_ylabel("Value" if len(y_columns) > 1 else y_columns[0])
            ax.set_title(f"{', '.join(y_columns)} vs {x_label}")
            if len(y_columns) > 1:
                ax.legend()
        else:
            axes = figure.subplots(len(y_columns), 1, sharex=True, squeeze=False).ravel().tolist()
            for ax, column in zip(axes, y_columns):
                ax.plot(display_x, plot_data[column], label=column, color=colours[column])
                ax.set_ylabel(column)
                ax.set_title(column, color=colours[column], fontweight="bold")
        for ax in axes:
            ax.grid(True)
            if using_mjd:
                ax.ticklabel_format(axis="x", style="plain", useOffset=False)
        axes[-1].set_xlabel(x_label)
        return axes

    def save_plot(self):
        filepath, selected_filter = QFileDialog.getSaveFileName(
            self, "Save Plot", "plot.png",
            "PNG Image (*.png);;SVG Vector Image (*.svg);;PDF Document (*.pdf);;JPEG Image (*.jpg *.jpeg)"
        )
        if not filepath: return
        if self.current_statistics is None or self.current_plot_data is None:
            self.status_label.setText("Create a plot before saving."); return
        try:
            if not Path(filepath).suffix:
                filepath += {"SVG": ".svg", "PDF": ".pdf", "JPEG": ".jpg"}.get(next((k for k in ("SVG","PDF","JPEG") if k in selected_filter), ""), ".png")
            export_figure = Figure(figsize=(12, max(7, 3 * len(self.current_y_columns))))
            self.draw_series(export_figure, self.current_display_x, self.current_plot_data,
                             self.current_x_label, self.current_y_columns, self.current_plot_mode,
                             self.current_using_mjd, self.current_series_colours)
            if self.is_time_column(self.x_selector.currentText()) and not self.current_using_mjd:
                export_figure.autofmt_xdate()
            export_figure.tight_layout()
            dpi = int(self.export_dpi_selector.currentText().split()[0])
            export_figure.savefig(filepath, dpi=dpi, bbox_inches="tight")
            export_figure.clear()
            self.status_label.setText(f"Plot saved: {filepath}")
        except Exception as error:
            self.status_label.setText(f"Error saving plot: {error}")

    def create_plot(self):
        if self.data is None:
            self.status_label.setText("Please load a CSV first."); return
        x_column = self.x_selector.currentText(); y_columns = self.selected_y_columns()
        if not x_column or not y_columns:
            self.status_label.setText("Please select an X axis and check at least one Y axis."); return
        try:
            plot_data = self.data
            if self.is_time_column(x_column):
                series = (self.mjd_to_datetime(self.data[x_column]) if self.is_mjd_column(x_column) else self.data[x_column])
                start = pd.Timestamp(self.start_time.dateTime().toPython()); end = pd.Timestamp(self.end_time.dateTime().toPython())
                if start > end: raise ValueError("Start time must be before end time.")
                mask = series.notna() & (series >= start) & (series <= end)
                plot_data = self.data.loc[mask].copy()
                if not self.is_mjd_column(x_column): plot_data[x_column] = series.loc[mask]
                if plot_data.empty: raise ValueError("No data exists in the selected time range.")
            statistics = {c: calculate_statistics(plot_data, c) for c in y_columns}
            display_x = plot_data[x_column]; x_label = x_column
            native_mjd = self.is_mjd_column(x_column)
            using_mjd = self.is_time_column(x_column) and self.time_axis_selector.currentText() == "MJD"
            if self.is_time_column(x_column):
                if using_mjd:
                    display_x = pd.to_numeric(plot_data[x_column], errors="coerce") if native_mjd else self.datetime_to_mjd(plot_data[x_column]); x_label = "MJD"
                else:
                    display_x = (self.mjd_to_datetime(plot_data[x_column]) if native_mjd else plot_data[x_column]); x_label = "Date / Time"
            mode = self.plot_mode_selector.currentText(); colours = self.series_colours(y_columns)
            self.current_statistics = statistics; self.current_plot_data = plot_data.copy()
            self.current_display_x = display_x.copy() if hasattr(display_x, "copy") else display_x
            self.current_x_label = x_label; self.current_y_columns = y_columns
            self.current_plot_mode = mode; self.current_using_mjd = using_mjd; self.current_series_colours = colours
            self.update_y_selector_colours(colours)
            self.draw_series(self.canvas.figure, display_x, plot_data, x_label, y_columns, mode, using_mjd, colours)
            if self.is_time_column(x_column) and not using_mjd: self.canvas.figure.autofmt_xdate()
            self.canvas.figure.tight_layout(); self.canvas.draw_idle(); self.save_plot_button.setEnabled(True)
            self.stats_label.setTextFormat(Qt.RichText)
            self.stats_label.setText(self.statistics_html(statistics, colours))
            self.status_label.setText(f"Plotted {len(plot_data)} points for {len(y_columns)} series vs {x_column} ({mode}).")
        except Exception as error:
            self.status_label.setText(f"Error: {error}")

def main():
    app = QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QApplication(sys.argv)

    QGuiApplication.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()

    if owns_app:
        sys.exit(app.exec())
    return window


if __name__ == "__main__":
    main()