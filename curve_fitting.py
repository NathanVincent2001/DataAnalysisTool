"""Automatic candidate fitting for numeric and time-based plotted series."""

import numpy as np
import pandas as pd


def _equation_polynomial(coefficients):
    equation = f"y = {coefficients[0]:.5g}"
    for degree, coefficient in enumerate(coefficients[1:], start=1):
        sign = "+" if coefficient >= 0 else "−"
        power = "z" if degree == 1 else f"z^{degree}"
        equation += f" {sign} {abs(coefficient):.5g}·{power}"
    return equation


def _aicc(y, predicted, parameter_count):
    sample_count = len(y)
    if sample_count <= parameter_count + 1:
        return float("inf")
    residual_sum = float(np.sum((y - predicted) ** 2))
    scale = max(
        float(np.sum((y - np.mean(y)) ** 2)),
        float(np.sum(y ** 2)),
        np.finfo(float).tiny,
    )
    residual_sum = max(residual_sum, np.finfo(float).eps * scale)
    return (
        sample_count * np.log(residual_sum / sample_count)
        + 2 * parameter_count
        + 2 * parameter_count * (parameter_count + 1)
        / (sample_count - parameter_count - 1)
    )


def _fit_candidate(model, z, y):
    if model.startswith("polynomial"):
        degree = int(model[-1])
        design = np.polynomial.polynomial.polyvander(z, degree)
        coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
        predictor = lambda values: np.polynomial.polynomial.polyval(values, coefficients)
        return predictor(z), degree + 1, _equation_polynomial(coefficients), "", predictor

    if model == "logarithmic":
        z_min = float(np.min(z))
        u = z - z_min + 1e-6
        log_u = np.log(u)
        design = np.column_stack((np.ones_like(log_u), log_u))
        coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
        predictor = lambda values: (
            coefficients[1] * np.log(values - z_min + 1e-6) + coefficients[0]
        )
        auxiliary = f"u = z − ({z_min:.5g}) + 1e−6"
        equation = f"y = {coefficients[1]:.5g}·ln(u) {coefficients[0]:+.5g}"
        return predictor(z), 2, equation, auxiliary, predictor

    if model == "power law":
        if np.any(y <= 0):
            raise ValueError("Power law requires positive Y values.")
        z_min = float(np.min(z))
        u = z - z_min + 1e-6
        design = np.column_stack((np.ones_like(u), np.log(u)))
        log_coefficients, *_ = np.linalg.lstsq(design, np.log(y), rcond=None)
        amplitude = float(np.exp(log_coefficients[0]))
        exponent = float(log_coefficients[1])
        predictor = lambda values: amplitude * np.power(values - z_min + 1e-6, exponent)
        auxiliary = f"u = z − ({z_min:.5g}) + 1e−6"
        equation = f"y = {amplitude:.5g}·u^{exponent:.5g}"
        return predictor(z), 2, equation, auxiliary, predictor

    if model == "exponential":
        from scipy.optimize import curve_fit

        def exponential(values, amplitude, exponent, offset):
            return amplitude * np.exp(np.clip(exponent * values, -60, 60)) + offset

        y_scale = max(float(np.std(y)), abs(float(np.mean(y))), np.finfo(float).tiny)
        scaled_y = y / y_scale
        initial = (float(np.ptp(scaled_y)) or 1.0, 1.0, float(np.min(scaled_y)))
        parameters, _ = curve_fit(
            exponential,
            z,
            scaled_y,
            p0=initial,
            bounds=([-np.inf, -20, -np.inf], [np.inf, 20, np.inf]),
            maxfev=12000,
        )
        amplitude, exponent, offset = parameters
        amplitude *= y_scale
        offset *= y_scale

        def predictor(values):
            return exponential(values, amplitude / y_scale, exponent, offset / y_scale) * y_scale

        equation = f"y = {amplitude:.5g}·exp({exponent:.5g}·z) {offset:+.5g}"
        return predictor(z), 3, equation, "", predictor

    raise ValueError(f"Unsupported fit model: {model}")


def fit_best_curve(x_values, y_values, x_label="x"):
    """Fit standard candidate models and select the one with lowest AICc."""
    x_series = pd.Series(x_values).reset_index(drop=True)
    y_series = pd.to_numeric(pd.Series(y_values).reset_index(drop=True), errors="coerce")
    is_datetime = pd.api.types.is_datetime64_any_dtype(x_series)
    if is_datetime:
        times = pd.to_datetime(x_series, errors="coerce", utc=True, format="mixed")
        x_numeric = times.astype("int64").to_numpy(dtype=float) / 1e9
        x_valid = times.notna().to_numpy()
    else:
        x_numeric = pd.to_numeric(x_series, errors="coerce").to_numpy(dtype=float)
        x_valid = np.isfinite(x_numeric)

    y_numeric = y_series.to_numpy(dtype=float)
    valid = x_valid & np.isfinite(x_numeric) & np.isfinite(y_numeric)
    x_numeric, y_numeric = x_numeric[valid], y_numeric[valid]
    if len(y_numeric) < 6:
        raise ValueError("At least six valid points are required for automatic model selection.")
    order = np.argsort(x_numeric)
    x_numeric, y_numeric = x_numeric[order], y_numeric[order]
    x_center = float((np.min(x_numeric) + np.max(x_numeric)) / 2)
    x_scale = float((np.max(x_numeric) - np.min(x_numeric)) / 2)
    if not np.isfinite(x_scale) or x_scale <= 0:
        raise ValueError("The X values must span a non-zero range.")
    z = (x_numeric - x_center) / x_scale

    candidates = []
    models = ("polynomial1", "polynomial2", "polynomial3", "exponential", "logarithmic", "power law")
    for model in models:
        try:
            predicted, parameter_count, equation, auxiliary, predictor = _fit_candidate(model, z, y_numeric)
            if not np.all(np.isfinite(predicted)):
                continue
            score = _aicc(y_numeric, predicted, parameter_count)
            if np.isfinite(score):
                candidates.append((score, model, predicted, equation, auxiliary, predictor))
        except (ValueError, RuntimeError, FloatingPointError, OverflowError):
            continue
    if not candidates:
        raise ValueError("No supported model could be fitted to this series.")

    score, model, predicted, equation, auxiliary, predictor = min(candidates, key=lambda result: result[0])
    residuals = y_numeric - predicted
    total_sum = float(np.sum((y_numeric - np.mean(y_numeric)) ** 2))
    r_squared = 1.0 - float(np.sum(residuals ** 2)) / total_sum if total_sum > 0 else 1.0
    rmse = float(np.sqrt(np.mean(residuals ** 2)))
    curve_numeric = np.linspace(float(np.min(x_numeric)), float(np.max(x_numeric)), 400)
    curve_z = (curve_numeric - x_center) / x_scale
    curve_y = predictor(curve_z)
    if is_datetime:
        curve_x = pd.to_datetime(np.rint(curve_numeric * 1e9).astype("int64"), utc=True).tz_localize(None)
        center_label = pd.to_datetime(x_center, unit="s", utc=True).strftime("%Y-%m-%d %H:%M:%S UTC")
        x_definition = f"z = (t − {center_label}) / {x_scale:.5g} s"
    else:
        curve_x = curve_numeric
        x_definition = f"z = ({x_label} − {x_center:.6g}) / {x_scale:.6g}"
    return {
        "x": curve_x,
        "y": curve_y,
        "model": {"polynomial1": "linear", "polynomial2": "quadratic polynomial", "polynomial3": "cubic polynomial"}.get(model, model),
        "equation": equation,
        "auxiliary": auxiliary,
        "x_definition": x_definition,
        "r_squared": r_squared,
        "rmse": rmse,
        "aicc": score,
    }

