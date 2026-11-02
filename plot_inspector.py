import pandas as pd
from astropy.time import Time
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QCheckBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.widgets import SpanSelector
import matplotlib.dates as mdates
import matplotlib as mpl

from analysis import calculate_statistics, detect_anomalies
from exporting import build_plot_export, ensure_export_extension
from curve_fitting import fit_best_curve

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
        self.initial_using_mjd = using_mjd
        self.range_data = self.plot_data.copy()
        self.anomalies_removed = False
        self.fit_results = {}
        self.fit_errors = {}
        self.sigma_threshold = sigma_threshold
        self.view_data = self.plot_data
        self.series_visible = {column: True for column in self.y_columns}
        self.series_visibility_checkboxes = {}
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
        self.reset_button = QPushButton("Reset All"); self.reset_button.setObjectName("inspectorResetButton"); self.reset_button.setMinimumSize(120, 38)
        self.reset_button.setToolTip("Restore the full range, original axis, visible series and anomaly rows")
        self.remove_anomalies_button = QPushButton("Remove anomalies")
        self.remove_anomalies_button.setObjectName("removeAnomaliesButton")
        self.remove_anomalies_button.setCheckable(True)
        self.remove_anomalies_button.setToolTip("Filter detected outlier rows from the plotted data")
        self.save_button = QPushButton("Save Plot"); self.save_button.setObjectName("inspectorSaveButton"); self.save_button.setMinimumSize(140, 38)
        self.anomaly_toggle = QCheckBox("Show anomaly markers"); self.anomaly_toggle.setObjectName("anomalyToggle"); self.anomaly_toggle.setChecked(True)
        self.fit_button = QPushButton("Best Fit")
        self.fit_button.setObjectName("fitCurveButton")
        self.fit_button.setToolTip("Compare linear, polynomial, exponential, logarithmic and power-law fits")
        tools.addWidget(self.range_label, 1)
        tools.addWidget(self.axis_label); tools.addWidget(self.axis_selector)
        tools.addWidget(self.anomaly_toggle); tools.addWidget(self.fit_button)
        tools.addWidget(self.remove_anomalies_button)
        tools.addWidget(self.reset_button); tools.addWidget(self.save_button)
        root.addLayout(tools)

        body = QHBoxLayout(); plot_box = QVBoxLayout()
        self.figure = Figure(); self.canvas = FigureCanvasQTAgg(self.figure); self.toolbar = NavigationToolbar2QT(self.canvas, self)
        plot_box.addWidget(self.toolbar); plot_box.addWidget(self.canvas, 1); body.addLayout(plot_box, 4)
        stats_box = QVBoxLayout(); stats_title = QLabel("Statistics"); f=QFont(); f.setBold(True); f.setPointSize(14); stats_title.setFont(f)
        self.stats_label=QLabel(); self.stats_label.setTextFormat(Qt.RichText); self.stats_label.setAlignment(Qt.AlignTop)
        self.fit_label = QLabel("<i>Choose Best Fit to compare candidate models.</i>")
        self.fit_label.setTextFormat(Qt.RichText)
        self.fit_label.setWordWrap(True)
        self.fit_label.setAlignment(Qt.AlignTop)
        stats_box.addWidget(stats_title)
        for column in self.y_columns:
            visibility = QCheckBox(f"Show {column}")
            visibility.setObjectName("seriesVisibilityToggle")
            visibility.setChecked(True)
            visibility.setProperty("seriesColour", self.colours[column])
            visibility.toggled.connect(lambda checked, c=column: self.set_series_visibility(c, checked))
            self.series_visibility_checkboxes[column] = visibility
            stats_box.addWidget(visibility)
        stats_box.addWidget(self.stats_label)
        fit_title = QLabel("Best fit equations")
        fit_title.setStyleSheet("font-weight: 700; font-size: 12pt; color: #243447;")
        stats_box.addWidget(fit_title)
        stats_box.addWidget(self.fit_label)
        stats_box.addStretch()
        sw=QWidget(); sw.setLayout(stats_box); body.addWidget(sw, 1); root.addLayout(body, 1)
        self.setCentralWidget(central)
        self.setStyleSheet("""
            QPushButton#inspectorResetButton { background: #1976d2; color: white; border: none; border-radius: 7px; padding: 7px 16px; font-size: 14px; font-weight: 800; }
            QPushButton#fitCurveButton { background: #6d28d9; color: white; border: none; border-radius: 7px; padding: 7px 12px; font-size: 13px; font-weight: 800; }
            QPushButton#fitCurveButton:hover { background: #5b21b6; }
            QPushButton#removeAnomaliesButton { background: #fff7ed; color: #9a3412; border: 1px solid #fdba74; border-radius: 7px; padding: 7px 12px; font-weight: 700; }
            QPushButton#removeAnomaliesButton:checked { background: #9a3412; color: white; border-color: #9a3412; }
            QPushButton#inspectorSaveButton { background: #008b95; color: white; border: none; border-radius: 7px; padding: 7px 16px; font-size: 14px; font-weight: 800; }
            QCheckBox#anomalyToggle { color: #9b1c1c; background: #fff5f5; border: 2px solid #ef9a9a; border-radius: 7px; padding: 7px 12px; font-weight: 800; }
            QCheckBox#seriesVisibilityToggle { color: #334155; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 8px; font-weight: 800; }
            QCheckBox#seriesVisibilityToggle:hover { background: #eef6ff; border-color: #93b9df; }
            QComboBox#timeAxisSelector { min-height: 30px; padding: 1px 7px; border: 2px solid #80aee0; border-radius: 6px; background: #f4f9ff; color: #1f2937; font-weight: 600; }
            QComboBox#timeAxisSelector:hover { border-color: #5b96d6; background: #eaf4ff; }
        """)
        self.reset_button.clicked.connect(self.reset_all); self.save_button.clicked.connect(self.save_plot)
        self.remove_anomalies_button.toggled.connect(self.set_anomalies_removed)
        self.fit_button.clicked.connect(self.fit_visible_series)
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
            if not self.series_visible.get(column, True):
                continue
            st=calculate_statistics(self.view_data, column); an=detect_anomalies(self.plot_data, column, self.sigma_threshold)
            colour=self.colours[column]
            blocks.append(f'<b style="color:{colour};font-size:12pt">{column}</b><br>'
                          f'Count: {st["count"]}<br>Mean: {st["mean"]:.6g}<br>Median: {st["median"]:.6g}<br>'
                          f'Std dev: {st["std_dev"]:.6g}<br>Min: {st["min"]:.6g}<br>Max: {st["max"]:.6g}<br>'
                          f'Range: {st["range"]:.6g}<br><b>Potential anomalies: {an["count"]}</b>')
        return '<br><br>'.join(blocks) if blocks else '<i>No series visible</i>'

    def set_series_visibility(self, column, visible):
        self.series_visible[column] = visible
        self._clear_fit_results()
        self.draw()

    def _clear_fit_results(self):
        self.fit_results.clear()
        self.fit_errors.clear()
        self.fit_button.setText("Best Fit")
        self.fit_label.setText("<i>Choose Best Fit to compare candidate models.</i>")

    def _fit_summary_html(self, visible_columns):
        from html import escape

        blocks = []
        for column in visible_columns:
            result = self.fit_results.get(column)
            colour = self.colours.get(column, "#243447")
            if result:
                equation = escape(result["equation"])
                x_definition = escape(result["x_definition"])
                auxiliary = f"<br>{escape(result['auxiliary'])}" if result["auxiliary"] else ""
                blocks.append(
                    f'<b style="color:{colour};font-size:11pt">{escape(str(column))}</b><br>'
                    f'<b>{escape(result["model"])}</b><br>'
                    f'<span style="font-family:monospace">{equation}</span><br>'
                    f'<small>{x_definition}{auxiliary}<br>'
                    f'R²: {result["r_squared"]:.5f}<br>'
                    f'RMSE: {result["rmse"]:.5g}<br>AICc: {result["aicc"]:.5g}</small>'
                )
            elif column in self.fit_errors:
                blocks.append(
                    f'<b style="color:{colour}">{escape(str(column))}</b><br>'
                    f'<span style="color:#9b1c1c">{escape(self.fit_errors[column])}</span>'
                )
        if not blocks:
            return "<i>No visible series to fit.</i>"
        return "<br><br>".join(blocks) + "<br><br><small>Best model selected by AICc; lower scores balance fit quality and model complexity.</small>"

    def fit_visible_series(self):
        display_x, x_label = self._display_x(self.view_data)
        visible_columns = [
            column for column in self.y_columns
            if self.series_visible.get(column, True)
        ]
        self.fit_results.clear()
        self.fit_errors.clear()
        for column in visible_columns:
            try:
                self.fit_results[column] = fit_best_curve(
                    display_x, self.view_data[column], x_label
                )
            except Exception as error:
                self.fit_errors[column] = str(error)
        if not self.fit_results:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "Could not fit series",
                "No visible series could be fitted. At least six valid points are required.",
            )
        self.fit_button.setText("Refit Curves")
        self.draw()
    def draw(self):
        self.figure.clear(); ax=self.figure.add_subplot(111); display_x, x_label=self._display_x(self.view_data)
        visible_columns = [column for column in self.y_columns if self.series_visible.get(column, True)]
        for column in visible_columns:
            ax.plot(display_x, self.view_data[column], color=self.colours[column], label=column)
            # Anomaly classification is anchored to the inspector's full plotted X range.
            # Zooming/selecting only changes which already-classified points are visible.
            full_an = detect_anomalies(self.plot_data, column, self.sigma_threshold)
            mask = full_an['mask'].reindex(self.view_data.index, fill_value=False)
            if self.anomaly_toggle.isChecked() and mask.any():
                ax.scatter(display_x.loc[mask], self.view_data.loc[mask,column], s=60, facecolors='none', edgecolors='#d32f2f', linewidths=1.8, zorder=5)
            fit_result = self.fit_results.get(column)
            if fit_result:
                ax.plot(fit_result["x"], fit_result["y"], color=self.colours[column],
                        linestyle="--", linewidth=2.0, label=f"{column} best fit")
        if visible_columns:
            ax.set_title(visible_columns[0] if len(visible_columns)==1 else 'Overlay: ' + ', '.join(visible_columns), fontweight='bold')
            ax.set_ylabel(visible_columns[0] if len(visible_columns)==1 else 'Value')
            ax.relim(); ax.autoscale_view()
            if len(visible_columns) > 1 or self.fit_results:
                ax.legend(loc="best", fontsize=8)
        else:
            ax.set_title('No series visible', fontweight='bold'); ax.set_ylabel('Value')
        ax.set_xlabel(x_label); ax.grid(True)
        if self.using_mjd and self.is_time_axis: ax.ticklabel_format(axis='x', style='plain', useOffset=False)
        if self.is_time_axis and not self.using_mjd: self.figure.autofmt_xdate()
        self.figure.tight_layout(); self.stats_label.setText(self._stats_html())
        self.fit_label.setText(self._fit_summary_html(visible_columns))
        self.canvas.draw_idle()
        self.span=SpanSelector(ax, self.select_range, 'horizontal', useblit=True, props=dict(alpha=.18, facecolor='#1976d2'), interactive=True, drag_from_anywhere=True)

    def change_time_axis(self, text):
        if not self.is_time_axis: return
        self.using_mjd = text == "MJD"; self._clear_fit_results(); self.draw()

    def select_range(self, xmin, xmax):
        display_x, _=self._display_x(self.plot_data)
        if self.is_time_axis and not self.using_mjd:
            vals=mdates.date2num(pd.to_datetime(display_x).dt.to_pydatetime())
        else: vals=pd.to_numeric(display_x, errors='coerce').to_numpy()
        mask=pd.Series((vals >= min(xmin,xmax)) & (vals <= max(xmin,xmax)), index=self.plot_data.index)
        if not mask.any(): return
        self._clear_fit_results()
        self.range_data = self.plot_data.loc[mask].copy()
        self.range_label.setText(f"Selected range: {len(self.range_data)} points")
        self._refresh_view_data()
        self.draw()

    def set_anomalies_removed(self, removed):
        self._clear_fit_results()
        self.anomalies_removed = bool(removed)
        self.remove_anomalies_button.setText(
            "Restore anomalies" if self.anomalies_removed else "Remove anomalies"
        )
        self._refresh_view_data()
        self.draw()

    def _refresh_view_data(self):
        if not self.anomalies_removed:
            self.view_data = self.range_data.copy()
            return

        anomaly_rows = pd.Series(False, index=self.range_data.index, dtype=bool)
        for column in self.y_columns:
            result = detect_anomalies(self.plot_data, column, self.sigma_threshold)
            anomaly_rows |= result["mask"].reindex(self.range_data.index, fill_value=False)

        filtered = self.range_data.loc[~anomaly_rows].copy()
        if filtered.empty:
            self.anomalies_removed = False
            self.remove_anomalies_button.blockSignals(True)
            self.remove_anomalies_button.setChecked(False)
            self.remove_anomalies_button.blockSignals(False)
            self.remove_anomalies_button.setText("Remove anomalies")
            self.view_data = self.range_data.copy()
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                "No data left to plot",
                "Every point in this range was classified as an anomaly. The original data is still shown.",
            )
            return
        self.view_data = filtered

    def reset_all(self):
        self._clear_fit_results()
        self.range_data = self.plot_data.copy()
        self.view_data = self.range_data.copy()
        self.range_label.setText("Full plotted range")
        self.anomalies_removed = False
        self.remove_anomalies_button.blockSignals(True)
        self.remove_anomalies_button.setChecked(False)
        self.remove_anomalies_button.blockSignals(False)
        self.remove_anomalies_button.setText("Remove anomalies")
        self.anomaly_toggle.blockSignals(True)
        self.anomaly_toggle.setChecked(True)
        self.anomaly_toggle.blockSignals(False)
        self.using_mjd = self.initial_using_mjd
        self.axis_selector.blockSignals(True)
        self.axis_selector.setCurrentText("MJD" if self.initial_using_mjd else "Date / Time")
        self.axis_selector.blockSignals(False)
        for column, checkbox in self.series_visibility_checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(True)
            checkbox.blockSignals(False)
            self.series_visible[column] = True
        self.draw()

    def save_plot(self):
        default = self.y_columns[0] if len(self.y_columns) == 1 else "overlay-report"
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Plot Report",
            f"{default}.png",
            "PNG Image (*.png);;SVG Vector Image (*.svg);;PDF Document (*.pdf);;JPEG Image (*.jpg *.jpeg)",
        )
        if not path:
            return

        visible_columns = [
            column for column in self.y_columns
            if self.series_visible.get(column, True)
        ]
        if not visible_columns:
            return

        try:
            path = ensure_export_extension(path, selected_filter)
            display_x, x_label = self._display_x(self.view_data)
            statistics = {
                column: calculate_statistics(self.view_data, column)
                for column in visible_columns
            }
            anomalies = {}
            for column in visible_columns:
                anomaly = detect_anomalies(self.plot_data, column, self.sigma_threshold)
                visible_mask = anomaly["mask"].reindex(self.range_data.index, fill_value=False)
                anomalies[column] = {
                    **anomaly,
                    "count": int(visible_mask.sum()),
                    "mask": visible_mask,
                }
            dataset_name = "Loaded dataset"
            parent = self.parent()
            if parent is not None and hasattr(parent, "file_label"):
                from pathlib import Path

                dataset_name = Path(parent.file_label.text()).name
            series_title = ", ".join(visible_columns[:3])
            if len(visible_columns) > 3:
                series_title += f" +{len(visible_columns) - 3} more"
            title = f"{series_title} vs {x_label}"
            figure = build_plot_export(
                self.view_data,
                display_x,
                visible_columns,
                self.colours,
                x_label,
                statistics,
                anomalies,
                title=title,
                dataset_name=dataset_name,
                layout="Overlay",
                show_anomalies=self.anomaly_toggle.isChecked(),
                using_mjd=self.using_mjd,
                sigma_threshold=self.sigma_threshold,
                range_note=self.range_label.text(),
            )
            figure.savefig(path, dpi=300, bbox_inches="tight", facecolor=figure.get_facecolor())
            figure.clear()
        except Exception as error:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Could not save plot", str(error))










