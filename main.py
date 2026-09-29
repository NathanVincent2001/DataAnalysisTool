import sys
from pathlib import Path
import pandas as pd
from astropy.time import Time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QComboBox, QDateTimeEdit, QGroupBox, QGridLayout, QCheckBox, QScrollArea, QDoubleSpinBox
)
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtGui import QColor, QFont, QPalette
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.widgets import SpanSelector
import matplotlib.dates as mdates
from analysis import load_csv, calculate_statistics, detect_anomalies
import matplotlib as mpl
mpl.rcParams["agg.path.chunksize"] = 10000

class PlotCanvas(FigureCanvasQTAgg):
    """Matplotlib canvas embedded inside the GUI."""

    def __init__(self):
        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)
        super().__init__(self.figure)



class PlotInspector(QMainWindow):
    """Interactive inspector for a single series or an overlaid set of series."""
    def __init__(self, parent, plot_data, x_column, y_columns, colours,
                 using_mjd, sigma_threshold, is_time_axis, native_mjd=False):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.y_columns = list(y_columns)
        self.colours = colours
        self.plot_data = plot_data.copy()
        self.x_column = x_column
        self.is_time_axis = is_time_axis
        self.native_mjd = native_mjd
        self.using_mjd = using_mjd
        self.sigma_threshold = sigma_threshold
        self.view_data = self.plot_data
        title_text = self.y_columns[0] if len(self.y_columns) == 1 else "Overlay"
        self.setWindowTitle(f"Plot Inspector - {title_text}")
        self.resize(1100, 720)

        central = QWidget(); root = QVBoxLayout(central)
        tools = QHBoxLayout()
        self.range_label = QLabel("Full plotted range")
        self.axis_label = QLabel("Time axis")
        self.axis_selector = QComboBox()
        self.axis_selector.setObjectName("timeAxisSelector")
        self.axis_selector.setFixedHeight(36)
        self.axis_selector.setMinimumWidth(130)
        self.axis_selector.addItems(["Date / Time", "MJD"])
        self.axis_selector.setCurrentText("MJD" if using_mjd else "Date / Time")
        self.axis_selector.setEnabled(is_time_axis)
        self.reset_button = QPushButton("Reset Range"); self.reset_button.setObjectName("inspectorResetButton"); self.reset_button.setMinimumSize(140, 38)
        self.save_button = QPushButton("Save Plot"); self.save_button.setObjectName("inspectorSaveButton"); self.save_button.setMinimumSize(140, 38)
        self.anomaly_toggle = QCheckBox("Show anomaly markers"); self.anomaly_toggle.setObjectName("anomalyToggle"); self.anomaly_toggle.setChecked(True)
        tools.addWidget(self.range_label, 1)
        tools.addWidget(self.axis_label); tools.addWidget(self.axis_selector)
        tools.addWidget(self.anomaly_toggle); tools.addWidget(self.reset_button); tools.addWidget(self.save_button)
        root.addLayout(tools)

        body = QHBoxLayout(); plot_box = QVBoxLayout()
        self.figure = Figure(); self.canvas = FigureCanvasQTAgg(self.figure); self.toolbar = NavigationToolbar2QT(self.canvas, self)
        plot_box.addWidget(self.toolbar); plot_box.addWidget(self.canvas, 1); body.addLayout(plot_box, 4)
        stats_box = QVBoxLayout(); stats_title = QLabel("Statistics"); f=QFont(); f.setBold(True); f.setPointSize(14); stats_title.setFont(f)
        self.stats_label=QLabel(); self.stats_label.setTextFormat(Qt.RichText); self.stats_label.setAlignment(Qt.AlignTop)
        stats_box.addWidget(stats_title); stats_box.addWidget(self.stats_label); stats_box.addStretch()
        sw=QWidget(); sw.setLayout(stats_box); body.addWidget(sw, 1); root.addLayout(body, 1)
        self.setCentralWidget(central)
        self.setStyleSheet("""
            QPushButton#inspectorResetButton { background: #1976d2; color: white; border: none; border-radius: 7px; padding: 7px 16px; font-size: 14px; font-weight: 800; }
            QPushButton#inspectorSaveButton { background: #008b95; color: white; border: none; border-radius: 7px; padding: 7px 16px; font-size: 14px; font-weight: 800; }
            QCheckBox#anomalyToggle { color: #9b1c1c; background: #fff5f5; border: 2px solid #ef9a9a; border-radius: 7px; padding: 7px 12px; font-weight: 800; }
            QComboBox#timeAxisSelector { min-height: 30px; padding: 1px 7px; border: 2px solid #80aee0; border-radius: 6px; background: #f4f9ff; color: #1f2937; font-weight: 600; }
            QComboBox#timeAxisSelector:hover { border-color: #5b96d6; background: #eaf4ff; }
        """)
        self.reset_button.clicked.connect(self.reset_range); self.save_button.clicked.connect(self.save_plot)
        self.anomaly_toggle.toggled.connect(self.draw); self.axis_selector.currentTextChanged.connect(self.change_time_axis)
        self.draw()

    def _display_x(self, data):
        source = data[self.x_column]
        if not self.is_time_axis:
            return source, self.x_column
        if self.using_mjd:
            if self.native_mjd:
                return pd.to_numeric(source, errors="coerce"), "MJD"
            converted = pd.to_datetime(source, errors="coerce")
            result = pd.Series(float("nan"), index=source.index, dtype="float64")
            valid = converted.notna()
            if valid.any():
                result.loc[valid] = Time([v.to_pydatetime() for v in converted.loc[valid]], scale="utc").mjd
            return result, "MJD"
        if self.native_mjd:
            numeric = pd.to_numeric(source, errors="coerce")
            result = pd.Series(pd.NaT, index=source.index, dtype="datetime64[ns]")
            valid = numeric.notna()
            if valid.any():
                result.loc[valid] = pd.to_datetime(Time(numeric.loc[valid].to_numpy(dtype=float), format="mjd", scale="utc").to_datetime())
            return result, "Date / Time"
        return pd.to_datetime(source, errors="coerce"), "Date / Time"

    def _stats_html(self):
        blocks=[]
        for column in self.y_columns:
            st=calculate_statistics(self.view_data, column); an=detect_anomalies(self.plot_data, column, self.sigma_threshold)
            colour=self.colours[column]
            blocks.append(f'<b style="color:{colour};font-size:12pt">{column}</b><br>'
                          f'Count: {st["count"]}<br>Mean: {st["mean"]:.6g}<br>Median: {st["median"]:.6g}<br>'
                          f'Std dev: {st["std_dev"]:.6g}<br>Min: {st["min"]:.6g}<br>Max: {st["max"]:.6g}<br>'
                          f'Range: {st["range"]:.6g}<br><b>Potential anomalies: {an["count"]}</b>')
        return '<br><br>'.join(blocks)

    def draw(self):
        self.figure.clear(); ax=self.figure.add_subplot(111); display_x, x_label=self._display_x(self.view_data)
        for column in self.y_columns:
            ax.plot(display_x, self.view_data[column], color=self.colours[column], label=column)
            # Anomaly classification is anchored to the inspector's full plotted X range.
            # Zooming/selecting only changes which already-classified points are visible.
            full_an = detect_anomalies(self.plot_data, column, self.sigma_threshold)
            mask = full_an['mask'].reindex(self.view_data.index, fill_value=False)
            if self.anomaly_toggle.isChecked() and mask.any():
                ax.scatter(display_x.loc[mask], self.view_data.loc[mask,column], s=60, facecolors='none', edgecolors='#d32f2f', linewidths=1.8, zorder=5)
        ax.set_title(self.y_columns[0] if len(self.y_columns)==1 else 'Overlay: ' + ', '.join(self.y_columns), fontweight='bold')
        ax.set_ylabel(self.y_columns[0] if len(self.y_columns)==1 else 'Value'); ax.set_xlabel(x_label); ax.grid(True)
        if self.using_mjd and self.is_time_axis: ax.ticklabel_format(axis='x', style='plain', useOffset=False)
        if self.is_time_axis and not self.using_mjd: self.figure.autofmt_xdate()
        self.figure.tight_layout(); self.stats_label.setText(self._stats_html()); self.canvas.draw_idle()
        self.span=SpanSelector(ax, self.select_range, 'horizontal', useblit=True, props=dict(alpha=.18, facecolor='#1976d2'), interactive=True, drag_from_anywhere=True)

    def change_time_axis(self, text):
        if not self.is_time_axis: return
        self.using_mjd = text == "MJD"; self.reset_range()

    def select_range(self, xmin, xmax):
        display_x, _=self._display_x(self.plot_data)
        if self.is_time_axis and not self.using_mjd:
            vals=mdates.date2num(pd.to_datetime(display_x).dt.to_pydatetime())
        else: vals=pd.to_numeric(display_x, errors='coerce').to_numpy()
        mask=pd.Series((vals >= min(xmin,xmax)) & (vals <= max(xmin,xmax)), index=self.plot_data.index)
        if not mask.any(): return
        self.view_data=self.plot_data.loc[mask].copy(); self.range_label.setText(f"Selected range: {len(self.view_data)} points"); self.draw()

    def reset_range(self):
        self.view_data=self.plot_data; self.range_label.setText("Full plotted range"); self.draw()

    def save_plot(self):
        default = self.y_columns[0] if len(self.y_columns)==1 else "overlay"
        path,_=QFileDialog.getSaveFileName(self,"Save Inspector Plot",f"{default}.png","PNG Image (*.png);;SVG Vector Image (*.svg);;PDF Document (*.pdf);;JPEG Image (*.jpg *.jpeg)")
        if path: self.figure.savefig(path, dpi=300, bbox_inches='tight')

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
        self.current_anomalies = {}
        self.plot_inspectors = []
        self.popout_buttons = []
        self.popout_button_layout = None
        self.current_sigma_threshold = 5.0

        self.file_label = QLabel("No CSV loaded")
        self.load_button = QPushButton("Load CSV")
        self.load_button.setObjectName("loadButton")
        self.load_button.setMinimumSize(125, 32)

        self.x_label = QLabel("X-axis")
        self.x_label.setObjectName("axisHeading")
        self.x_selector = QComboBox()
        self.x_selector.setObjectName("xAxisSelector")
        self.x_selector.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.x_selector.setMinimumContentsLength(10)
        self.y_label = QLabel("Choose Y-axis")
        self.y_label.setObjectName("axisHeading")
        self.y_selector = QGroupBox()
        self.y_selector.setObjectName("yAxisSelectorBox")
        self.y_grid = QGridLayout(self.y_selector)
        self.y_grid.setContentsMargins(6, 5, 6, 5)
        self.y_grid.setHorizontalSpacing(6)
        self.y_grid.setVerticalSpacing(4)
        self.y_grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.y_checkboxes = []
        self.plot_mode_label = QLabel("Layout")
        self.plot_mode_label.setObjectName("optionLabel")
        self.plot_mode_selector = QComboBox()
        self.plot_mode_selector.addItems(["Overlay", "Separate plots"])
        self.plot_mode_selector.setCurrentText("Separate plots")
        self.plot_mode_selector.setObjectName("layoutSelector")
        self.plot_mode_selector.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.sigma_label = QLabel("Anomaly sensitivity")
        self.sigma_label.setObjectName("optionLabel")
        self.sigma_selector = QDoubleSpinBox()
        self.sigma_selector.setRange(0.1, 100.0)
        self.sigma_selector.setDecimals(1)
        self.sigma_selector.setSingleStep(0.5)
        self.sigma_selector.setValue(5.0)
        self.sigma_selector.setSuffix(" sigma")
        self.sigma_selector.setObjectName("sigmaSelector")
        self.sigma_selector.setFixedWidth(112)
        self.sigma_selector.setToolTip(
            "Flag points whose absolute deviation from the mean is at least this many standard deviations."
        )
        self.main_anomaly_toggle = QCheckBox("Anomaly markers")
        self.main_anomaly_toggle.setObjectName("anomalyPill")
        self.main_anomaly_toggle.setChecked(True)
        self.main_anomaly_toggle.setToolTip("Show or hide potential-anomaly markers on the main plots")
        self.plot_button = QPushButton("Plot")
        self.plot_button.setObjectName("plotButton")
        self.plot_button.setMinimumSize(140, 34)
        self.save_plot_button = QPushButton("Save Plot")
        self.save_plot_button.setObjectName("saveButton")
        self.save_plot_button.setMinimumSize(110, 34)
        self.save_plot_button.setEnabled(False)
        self.export_dpi_selector = QComboBox()
        self.export_dpi_selector.setObjectName("dpiSelector")
        self.export_dpi_selector.addItems(["300 DPI", "600 DPI", "1200 DPI"])
        self.export_dpi_selector.setCurrentText("300 DPI")
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
            button.setFixedSize(52, 26)
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
            QLabel#axisHeading {
                color: #172033; font-size: 16px; font-weight: 800; padding-bottom: 1px;
            }
            QLabel#statsTitle {
                color: #172033; font-size: 18px; font-weight: 800;
                padding: 4px 0 6px 0;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d8e0ea;
                border-radius: 9px;
                margin-top: 16px;
                padding-top: 14px;
                font-weight: 600;
                color: #243447;
            }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; top: 1px; padding: 2px 6px; background: #ffffff; }
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
            QLabel#optionLabel { color: #536273; font-weight: 700; }
            QDoubleSpinBox#sigmaSelector { min-height: 30px; padding: 1px 10px; border: 2px solid #c6a7e8; border-radius: 9px; background: #faf6ff; color: #593a78; font-weight: 700; }
            QDoubleSpinBox#sigmaSelector:focus { border-color: #9b72cf; background: #f5edff; }
            QCheckBox#anomalyPill { spacing: 7px; color: #65411e; background: #fff8e8; border: 2px solid #efc676; border-radius: 10px; padding: 5px 10px; font-weight: 700; }
            QCheckBox#anomalyPill:hover { background: #fff1ce; border-color: #dfa94b; }
            QCheckBox#anomalyPill::indicator { width: 17px; height: 17px; }
            QComboBox#dpiSelector { min-height: 30px; padding: 1px 9px; border: 2px solid #8fc5bf; border-radius: 9px; background: #f0faf8; color: #24625c; font-weight: 700; }
            QComboBox#dpiSelector:hover { background: #e4f5f2; border-color: #62aaa2; }
            QLabel#xAxisWarning {
                color: #9a6700; font-size: 11px; font-style: italic;
                padding-left: 2px;
            }
            QPushButton[popoutButton="true"] {
                background: #e8f0f7; color: #345166; border: 1px solid #a9bdcc;
                border-radius: 7px; padding: 6px 10px; font-size: 12px; font-weight: 700;
            }
            QPushButton[popoutButton="true"]:hover { background: #dbe8f2; border-color: #829fb4; }
            QWidget[statsCard="true"] {
                background: #ffffff; border: 1px solid #d8e0ea; border-radius: 9px;
            }
            QLabel[statsData="true"] { color: #243447; font-size: 13px; }
            QCheckBox { color: #334155; }
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(4)

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
        plot_setup_layout.setContentsMargins(8, 8, 8, 5)
        plot_setup_layout.setSpacing(2)

        axis_row = QHBoxLayout()
        axis_row.setSpacing(14)

        x_axis_panel = QVBoxLayout()
        x_axis_panel.setSpacing(5)
        x_axis_panel.addWidget(self.x_label)
        x_axis_controls = QHBoxLayout()
        x_axis_controls.addWidget(self.x_selector)
        x_axis_controls.addWidget(self.x_axis_warning)
        x_axis_controls.addStretch(1)
        x_axis_panel.addLayout(x_axis_controls)
        x_axis_panel.addStretch(1)
        axis_row.addLayout(x_axis_panel, 0)

        y_axis_panel = QVBoxLayout()
        y_axis_panel.setSpacing(5)
        y_axis_panel.addWidget(self.y_label)
        y_axis_panel.addWidget(self.y_selector)
        axis_row.addLayout(y_axis_panel, 0)

        plot_options = QVBoxLayout()
        plot_options.setSpacing(5)
        option_row = QHBoxLayout()
        option_row.setSpacing(8)
        option_row.setAlignment(Qt.AlignVCenter)
        option_row.addWidget(self.plot_mode_label)
        self.plot_mode_selector.setFixedHeight(36)
        self.plot_mode_selector.setMinimumWidth(145)
        option_row.addWidget(self.plot_mode_selector)
        self.time_axis_label.setObjectName("optionLabel")
        option_row.addSpacing(8)
        option_row.addWidget(self.time_axis_label)
        self.time_axis_selector.setFixedHeight(36)
        self.time_axis_selector.setMinimumWidth(130)
        option_row.addWidget(self.time_axis_selector)
        plot_options.addLayout(option_row)
        plot_options.addStretch(1)
        axis_row.addStretch(1)
        axis_row.addLayout(plot_options, 0)

        plot_setup_layout.addLayout(axis_row)
        action_row = QHBoxLayout()
        action_row.addStretch()
        action_row.addWidget(self.sigma_label)
        action_row.addWidget(self.sigma_selector)
        action_row.addWidget(self.main_anomaly_toggle)
        action_row.addSpacing(10)
        export_label = QLabel("Export")
        export_label.setObjectName("optionLabel")
        action_row.addWidget(export_label)
        action_row.addWidget(self.export_dpi_selector)
        action_row.addWidget(self.save_plot_button)
        action_row.addWidget(self.plot_button)
        plot_setup_layout.addLayout(action_row)
        main_layout.addWidget(plot_setup, 0)

        # Compact single-line time range controls.
        time_range_group = QGroupBox("Time Range")
        time_range_group_layout = QHBoxLayout(time_range_group)
        # Give the single-line controls enough vertical breathing room so the
        # group title and taller date widgets never overlap the results area.
        time_range_group_layout.setContentsMargins(8, 18, 8, 8)
        time_range_group_layout.setSpacing(5)
        time_range_group_layout.setAlignment(Qt.AlignVCenter)
        time_range_group_layout.addWidget(self.start_label)
        self.start_time.setFixedWidth(220)
        time_range_group_layout.addWidget(self.start_time)
        time_range_group_layout.addWidget(self.start_mjd_label)
        time_range_group_layout.addSpacing(8)
        time_range_group_layout.addWidget(self.end_label)
        self.end_time.setFixedWidth(220)
        time_range_group_layout.addWidget(self.end_time)
        time_range_group_layout.addWidget(self.end_mjd_label)
        time_range_group_layout.addSpacing(12)
        time_range_group_layout.addWidget(QLabel("Quick range:"))
        for button in self.quick_range_buttons:
            time_range_group_layout.addWidget(button)
        time_range_group_layout.addStretch(1)
        time_range_group.setMinimumHeight(76)
        time_range_group.setMaximumHeight(82)
        main_layout.addWidget(time_range_group, 0)
        # Scrollable result area. Separate mode is built as one row per series so
        # graph, pop-out control and statistics always remain aligned.
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setFrameShape(QScrollArea.NoFrame)
        self.results_content = QWidget()
        self.results_rows = QVBoxLayout(self.results_content)
        self.results_rows.setContentsMargins(2, 2, 2, 2)
        self.results_rows.setSpacing(10)
        self.results_scroll.setWidget(self.results_content)
        main_layout.addWidget(self.results_scroll, 4)
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
        self.main_anomaly_toggle.toggled.connect(self.create_plot)

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

    @staticmethod
    def _datetime_parse_candidate(series, sample_size=200, minimum_success=0.90):
        """Return True when a non-numeric column strongly resembles datetime data."""
        if pd.api.types.is_datetime64_any_dtype(series):
            return True
        if pd.api.types.is_numeric_dtype(series):
            return False
        sample = series.dropna().astype(str).str.strip()
        sample = sample[sample.ne("")].head(sample_size)
        if sample.empty:
            return False
        try:
            parsed = pd.to_datetime(sample, errors="coerce", utc=True)
        except Exception:
            return False
        return float(parsed.notna().mean()) >= minimum_success

    def normalise_datetime_columns(self):
        """Convert name-hinted or content-inferred datetime columns to datetime64[ns]."""
        if self.data is None:
            return
        for column in self.data.columns:
            if self.is_mjd_column(column):
                continue
            series = self.data[column]
            column_name = str(column).lower()
            name_hint = "time" in column_name or "date" in column_name
            already_datetime = pd.api.types.is_datetime64_any_dtype(series)
            content_hint = self._datetime_parse_candidate(series)
            if not (name_hint or already_datetime or content_hint):
                continue
            try:
                converted = pd.to_datetime(series, errors="coerce", utc=True)
                # Require strong content evidence when there was no explicit name/type hint.
                nonempty = series.notna().sum()
                success = converted.notna().sum() / nonempty if nonempty else 0.0
                if converted.notna().any() and (name_hint or already_datetime or success >= 0.90):
                    self.data[column] = converted.dt.tz_localize(None)
            except Exception:
                pass

    def detect_time_columns(self):
        """Find native MJD, parsed datetime, and strongly datetime-like text columns."""
        candidates = []
        if self.data is None:
            return candidates
        for column in self.data.columns:
            series = self.data[column]
            if self.is_mjd_column(column):
                numeric = pd.to_numeric(series, errors="coerce")
                if numeric.notna().any():
                    candidates.append(column)
                continue
            if pd.api.types.is_datetime64_any_dtype(series):
                candidates.append(column)
                continue
            if self._datetime_parse_candidate(series):
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
                checkbox.setFixedHeight(28)
                checkbox.setFixedWidth(150)
                checkbox.stateChanged.connect(
                    lambda _state: self.update_y_selector_colours(self.current_series_colours)
                )
                self.y_checkboxes.append(checkbox)
                # Keep the selector compact: fill exactly two rows, expanding
                # horizontally to suit however many Y series the dataset contains.
                columns_per_row = max(1, (len(y_columns) + 1) // 2)
                row = index // columns_per_row
                grid_column = index % columns_per_row
                self.y_grid.addWidget(
                    checkbox, row, grid_column,
                    alignment=Qt.AlignLeft | Qt.AlignVCenter
                )
            for grid_column in range(columns_per_row):
                self.y_grid.setColumnStretch(grid_column, 0)
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

    def statistics_html(self, statistics_by_column, colours, anomalies_by_column):
        blocks = []
        for column, statistics in statistics_by_column.items():
            colour = self.qt_colour_string(colours.get(column, "#222222"))
            blocks.append(
                f'<span style="color: {colour}; font-weight: 700; font-size: 14pt;">{column}</span><br>'
                f"Count: {statistics['count']}<br>"
                f"Mean: {statistics['mean']:.6g}<br>"
                f"Median: {statistics['median']:.6g}<br>"
                f"Std dev: {statistics['std_dev']:.6g}<br>"
                f"Min: {statistics['min']:.6g}<br>"
                f"Max: {statistics['max']:.6g}<br>"
                f"Range: {statistics['range']:.6g}<br>"
                f'<span style="font-weight: 700;">Potential anomalies: '
                f"{anomalies_by_column[column]['count']}</span><br>"
                f"Threshold: {anomalies_by_column[column]['threshold']:.1f} sigma<br>"
                f"Maximum deviation: {anomalies_by_column[column]['max_deviation_sigma']:.2f} sigma"
            )
        return "<br><br>".join(blocks)

    def draw_series(self, figure, display_x, plot_data, x_label, y_columns, mode, using_mjd, colours, anomalies_by_column, show_anomalies=True):
        figure.clear()
        if mode == "Overlay":
            axes = [figure.add_subplot(111)]
            ax = axes[0]
            for column in y_columns:
                ax.plot(display_x, plot_data[column], color=colours[column])
                anomaly_mask = anomalies_by_column[column]["mask"]
                if show_anomalies and anomaly_mask.any():
                    ax.scatter(
                        display_x.loc[anomaly_mask], plot_data.loc[anomaly_mask, column],
                        s=52, facecolors="none", edgecolors="#d32f2f", linewidths=1.8,
                        marker="o", zorder=5
                    )
            ax.set_ylabel("Value" if len(y_columns) > 1 else y_columns[0])
            ax.set_title(f"{', '.join(y_columns)} vs {x_label}")
        else:
            axes = figure.subplots(len(y_columns), 1, sharex=True, squeeze=False).ravel().tolist()
            for ax, column in zip(axes, y_columns):
                ax.plot(display_x, plot_data[column], label=column, color=colours[column])
                anomaly_mask = anomalies_by_column[column]["mask"]
                if show_anomalies and anomaly_mask.any():
                    ax.scatter(
                        display_x.loc[anomaly_mask], plot_data.loc[anomaly_mask, column],
                        s=52, facecolors="none", edgecolors="#d32f2f", linewidths=1.8,
                        marker="o", label="Potential anomaly", zorder=5
                    )
                ax.set_ylabel(column)
                ax.set_title(column, color=colours[column], fontweight="bold")
        for ax in axes:
            ax.grid(True)
            if using_mjd:
                ax.ticklabel_format(axis="x", style="plain", useOffset=False)
        axes[-1].set_xlabel(x_label)
        return axes

    def open_plot_inspector(self, column=None):
        if self.current_plot_data is None or not self.current_y_columns:
            return
        columns = self.current_y_columns if column is None else [column]
        if any(c not in self.current_y_columns for c in columns):
            return
        x_column = self.x_selector.currentText()
        inspector = PlotInspector(
            self, self.current_plot_data, x_column, columns, self.current_series_colours,
            self.current_using_mjd, self.current_sigma_threshold,
            self.is_time_column(x_column), self.is_mjd_column(x_column)
        )
        self.plot_inspectors.append(inspector)
        inspector.destroyed.connect(lambda *_: self.plot_inspectors.remove(inspector) if inspector in self.plot_inspectors else None)
        inspector.show()

    def update_popout_buttons(self):
        """Pop-out controls are now created beside each separate plot row."""
        return

    def clear_results_rows(self):
        while self.results_rows.count():
            item = self.results_rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def populate_results_area(self, display_x, plot_data, x_label, y_columns, mode,
                              using_mjd, colours, statistics, anomalies):
        self.clear_results_rows()
        if mode == "Overlay":
            row = QWidget(); layout = QHBoxLayout(row); layout.setContentsMargins(4, 4, 4, 8)
            canvas = PlotCanvas(); canvas.setMinimumHeight(510)
            self.draw_series(canvas.figure, display_x, plot_data, x_label, y_columns, mode,
                             using_mjd, colours, anomalies, self.main_anomaly_toggle.isChecked())
            canvas.figure.subplots_adjust(bottom=0.16)
            canvas.draw_idle(); layout.addWidget(canvas, 7)
            card = QWidget(); card.setProperty("statsCard", True); card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            stats = QLabel(self.statistics_html(statistics, colours, anomalies)); stats.setTextFormat(Qt.RichText); stats.setProperty("statsData", True); stats.setAlignment(Qt.AlignTop)
            card_layout.addWidget(stats, 1)
            overlay_button = QPushButton("Pop out overlay")
            overlay_button.setProperty("popoutButton", True)
            overlay_button.setToolTip("Open the overlaid graph in the interactive Plot Inspector")
            overlay_button.clicked.connect(lambda _=False: self.open_plot_inspector())
            card_layout.addWidget(overlay_button, 0, Qt.AlignVCenter)
            layout.addWidget(card, 1); row._canvas = canvas; self.results_rows.addWidget(row)
        else:
            for column in y_columns:
                row = QWidget(); row.setMinimumHeight(350)
                layout = QHBoxLayout(row); layout.setContentsMargins(4, 4, 4, 8); layout.setSpacing(10)
                canvas = PlotCanvas(); canvas.setMinimumHeight(334)
                self.draw_series(canvas.figure, display_x, plot_data, x_label, [column], "Separate plots",
                                 using_mjd, colours, {column: anomalies[column]}, self.main_anomaly_toggle.isChecked())
                # Reserve a larger lower margin so Date / Time stays inside the plot's white canvas.
                canvas.figure.subplots_adjust(left=0.09, right=0.98, top=0.88, bottom=0.20)
                canvas.draw_idle(); layout.addWidget(canvas, 7)

                card = QWidget(); card.setProperty("statsCard", True); card.setMinimumWidth(275); card.setMaximumWidth(330)
                card_layout = QHBoxLayout(card); card_layout.setContentsMargins(14, 12, 12, 12); card_layout.setSpacing(10)
                stats = QLabel(self.statistics_html({column: statistics[column]}, colours, {column: anomalies[column]}))
                stats.setTextFormat(Qt.RichText); stats.setProperty("statsData", True); stats.setAlignment(Qt.AlignTop); stats.setMinimumWidth(180)
                card_layout.addWidget(stats, 1, Qt.AlignVCenter)
                button = QPushButton("Pop out"); button.setProperty("popoutButton", True); button.setFixedWidth(82)
                button.clicked.connect(lambda _=False, c=column: self.open_plot_inspector(c))
                card_layout.addWidget(button, 0, Qt.AlignVCenter)
                layout.addWidget(card, 1)
                row._canvas = canvas; self.results_rows.addWidget(row)
        self.results_rows.addStretch()

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
                             self.current_using_mjd, self.current_series_colours, self.current_anomalies)
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
            sigma_threshold = self.sigma_selector.value()
            anomalies = {
                c: detect_anomalies(plot_data, c, sigma_threshold)
                for c in y_columns
            }
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
            self.current_anomalies = anomalies; self.current_sigma_threshold = sigma_threshold
            self.update_y_selector_colours(colours)
            self.populate_results_area(display_x, plot_data, x_label, y_columns, mode, using_mjd, colours, statistics, anomalies)
            self.save_plot_button.setEnabled(True)
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