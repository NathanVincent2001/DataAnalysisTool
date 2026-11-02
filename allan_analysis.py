"""Interactive Allan deviation analysis for one uniformly sampled series."""

import numpy as np
import pandas as pd

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

try:
    import allantools
except ImportError:  # Keep the main application usable if the optional package is absent.
    allantools = None


_PHASE_UNITS = {
    "seconds (s)": 1.0,
    "milliseconds (ms)": 1e-3,
    "microseconds (μs)": 1e-6,
    "nanoseconds (ns)": 1e-9,
    "picoseconds (ps)": 1e-12,
}


def _uniform_samples(x_values, y_values, native_mjd):
    """Return ordered, finite Y values and their verified uniform sample period."""
    y = pd.to_numeric(pd.Series(y_values), errors="coerce").to_numpy(dtype=float)
    if native_mjd:
        x = pd.to_numeric(pd.Series(x_values), errors="coerce").to_numpy(dtype=float) * 86400.0
        valid_x = np.isfinite(x)
    else:
        timestamps = pd.to_datetime(pd.Series(x_values), errors="coerce", utc=True)
        valid_x = timestamps.notna().to_numpy()
        x = timestamps.astype("int64").to_numpy(dtype=float) / 1e9

    valid = valid_x & np.isfinite(y)
    x, y = x[valid], y[valid]
    if len(y) < 3:
        raise ValueError("At least three valid, time-stamped samples are required.")

    order = np.argsort(x)
    x, y = x[order], y[order]
    intervals = np.diff(x)
    if np.any(intervals <= 0):
        raise ValueError("The time column contains duplicate or non-increasing timestamps.")

    tau0 = float(np.median(intervals))
    tolerance = max(1e-9, tau0 * 0.01)
    if not np.all(np.abs(intervals - tau0) <= tolerance):
        raise ValueError(
            "ADEV/OADEV require evenly spaced samples. The selected data has gaps or irregular timing."
        )
    return x, y, tau0


class AllanAnalysisDialog(QDialog):
    """Calculate and display ADEV and OADEV for one selected Y column."""

    def __init__(self, parent, x_values, y_values, series_name, native_mjd=False):
        super().__init__(parent)
        self.x_values = x_values.copy() if hasattr(x_values, "copy") else x_values
        self.y_values = y_values.copy() if hasattr(y_values, "copy") else y_values
        self.series_name = str(series_name)
        self.native_mjd = native_mjd
        self.setWindowTitle(f"ADEV / OADEV — {self.series_name}")
        self.resize(980, 720)

        root = QVBoxLayout(self)
        controls = QFormLayout()
        self.data_type_selector = QComboBox()
        self.data_type_selector.addItem("Phase / time error", "phase")
        self.data_type_selector.addItem("Fractional frequency", "freq")
        self.phase_unit_selector = QComboBox()
        self.phase_unit_selector.addItems(_PHASE_UNITS)
        self.tau_selector = QComboBox()
        self.tau_selector.addItem("Octave (recommended)", "octave")
        self.tau_selector.addItem("Decade", "decade")
        self.sample_info = QLabel()
        self.sample_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        controls.addRow("Y data represents", self.data_type_selector)
        controls.addRow("Phase units", self.phase_unit_selector)
        controls.addRow("Averaging-time spacing", self.tau_selector)
        controls.addRow("Sampling", self.sample_info)
        root.addLayout(controls)

        help_text = QLabel(
            "Phase values are converted to seconds before analysis. Frequency values must be "
            "fractional frequency (dimensionless). The time column supplies the sample interval."
        )
        help_text.setWordWrap(True)
        root.addWidget(help_text)

        self.figure = Figure(figsize=(10, 6), facecolor="white")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        root.addWidget(self.toolbar)
        root.addWidget(self.canvas, 1)
        self.status_label = QLabel("")
        root.addWidget(self.status_label)

        actions = QHBoxLayout()
        actions.addStretch()
        self.calculate_button = QPushButton("Calculate")
        self.calculate_button.setObjectName("calculateAllanButton")
        self.save_button = QPushButton("Save ADEV plot")
        self.save_button.setObjectName("saveAllanButton")
        self.save_button.setEnabled(False)
        close_button = QPushButton("Close")
        close_button.setObjectName("closeAllanButton")
        actions.addWidget(self.calculate_button)
        actions.addWidget(self.save_button)
        actions.addWidget(close_button)
        root.addLayout(actions)

        self.setStyleSheet("""
            QDialog { background: #f4f7fb; }
            QLabel { color: #243447; }
            QPushButton#calculateAllanButton {
                background: #1976d2; color: white; border: none;
                border-radius: 7px; padding: 9px 18px; font-size: 13px; font-weight: 800;
            }
            QPushButton#calculateAllanButton:hover { background: #125fae; }
            QPushButton#saveAllanButton {
                background: #008b95; color: white; border: none;
                border-radius: 7px; padding: 9px 18px; font-size: 13px; font-weight: 800;
            }
            QPushButton#saveAllanButton:hover { background: #006f77; }
            QPushButton#saveAllanButton:disabled { background: #aab8c4; color: #edf1f5; }
            QPushButton#closeAllanButton {
                background: #7c3aed; color: white; border: none;
                border-radius: 7px; padding: 9px 18px; font-size: 13px; font-weight: 800;
            }
            QPushButton#closeAllanButton:hover { background: #6426cf; }
        """)

        self.data_type_selector.currentIndexChanged.connect(self._update_phase_units)
        self.calculate_button.clicked.connect(self.calculate)
        self.save_button.clicked.connect(self.save_plot)
        close_button.clicked.connect(self.accept)
        self._update_phase_units()
        self._update_sample_info()
        self.calculate()

    def _update_phase_units(self):
        self.phase_unit_selector.setEnabled(self.data_type_selector.currentData() == "phase")

    def _update_sample_info(self):
        try:
            _, y, tau0 = _uniform_samples(self.x_values, self.y_values, self.native_mjd)
            self.sample_info.setText(f"{len(y):,} valid samples · interval {tau0:.9g} s")
        except ValueError as error:
            self.sample_info.setText(str(error))

    @staticmethod
    def _draw_curve(ax, result, label, colour, marker):
        taus, deviations, errors, _ = result
        taus = np.asarray(taus, dtype=float)
        deviations = np.asarray(deviations, dtype=float)
        errors = np.asarray(errors, dtype=float)
        valid = np.isfinite(taus) & np.isfinite(deviations) & (taus > 0) & (deviations > 0)
        if not valid.any():
            return False

        taus, deviations, errors = taus[valid], deviations[valid], errors[valid]
        valid_errors = np.isfinite(errors) & (errors >= 0)
        if valid_errors.any():
            errors = errors[valid_errors]
            error_taus = taus[valid_errors]
            error_deviations = deviations[valid_errors]
            lower = np.minimum(errors, error_deviations * 0.95)
            upper = errors
            ax.errorbar(error_taus, error_deviations, yerr=np.vstack([lower, upper]),
                        fmt=marker, color=colour, capsize=2, linewidth=1.2,
                        markersize=5, label=label)
        else:
            ax.loglog(taus, deviations, marker=marker, color=colour,
                      linewidth=1.5, markersize=5, label=label)
        return True

    def calculate(self):
        if allantools is None:
            self.status_label.setText("AllanTools is not installed in this environment.")
            return
        try:
            _, values, tau0 = _uniform_samples(
                self.x_values, self.y_values, self.native_mjd
            )
            data_type = self.data_type_selector.currentData()
            if data_type == "phase":
                values = values * _PHASE_UNITS[self.phase_unit_selector.currentText()]
            rate = 1.0 / tau0
            tau_choice = self.tau_selector.currentData()
            adev_result = allantools.adev(
                values, rate=rate, data_type=data_type, taus=tau_choice
            )
            oadev_result = allantools.oadev(
                values, rate=rate, data_type=data_type, taus=tau_choice
            )
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            has_adev = self._draw_curve(ax, adev_result, "ADEV", "#2563eb", "o")
            has_oadev = self._draw_curve(ax, oadev_result, "OADEV", "#d97706", "s")
            if not has_adev and not has_oadev:
                raise ValueError("Not enough usable samples to calculate positive ADEV/OADEV values.")

            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.set_xlabel("Averaging time τ (s)")
            y_label = "Allan deviation"
            if data_type == "phase":
                unit = self.phase_unit_selector.currentText().split("(")[-1].rstrip(")")
                y_label += f" ({unit})"
            else:
                y_label += " (fractional frequency)"
            ax.set_ylabel(y_label)
            ax.set_title(f"{self.series_name}: ADEV and OADEV", fontweight="bold")
            ax.grid(True, which="both", color="#dce4ee", linewidth=0.7)
            ax.legend(frameon=False)
            self.figure.tight_layout()
            self.canvas.draw_idle()
            self.save_button.setEnabled(True)
            self.status_label.setText(
                f"Calculated from {len(values):,} samples at {tau0:.9g} s spacing · "
                f"{data_type} input · {tau_choice} τ values."
            )
        except Exception as error:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.axis("off")
            ax.text(0.5, 0.5, str(error), ha="center", va="center",
                    wrap=True, color="#9b1c1c", transform=ax.transAxes)
            self.canvas.draw_idle()
            self.save_button.setEnabled(False)
            self.status_label.setText("ADEV/OADEV could not be calculated for this series.")

    def save_plot(self):
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save ADEV / OADEV Plot",
            f"{self.series_name}_adev.png",
            "PNG Image (*.png);;SVG Vector Image (*.svg);;PDF Document (*.pdf)",
        )
        if not path:
            return
        if not path.lower().endswith((".png", ".svg", ".pdf")):
            extension = ".png"
            if "SVG" in selected_filter:
                extension = ".svg"
            elif "PDF" in selected_filter:
                extension = ".pdf"
            path += extension
        self.figure.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")



