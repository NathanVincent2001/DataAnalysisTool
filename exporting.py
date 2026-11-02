"""Build clean, publication-style figures for saved plot exports."""

from matplotlib.figure import Figure


_PAGE = "#f4f7fb"
_INK = "#172b4d"
_MUTED = "#52637a"
_GRID = "#dce4ee"


def _format_value(value):
    try:
        return f"{float(value):.6g}"
    except (TypeError, ValueError):
        return "—"


def _format_range(values):
    valid = values.dropna() if hasattr(values, "dropna") else values
    if len(valid) == 0:
        return "No valid X values"
    start, end = valid.min(), valid.max()
    if hasattr(start, "strftime"):
        return f"{start:%Y-%m-%d %H:%M:%S} to {end:%Y-%m-%d %H:%M:%S}"
    return f"{_format_value(start)} to {_format_value(end)}"


def ensure_export_extension(path, selected_filter):
    """Append the selected file format when the save dialog returned no suffix."""
    from pathlib import Path

    if Path(path).suffix:
        return path
    suffix = ".png"
    for label, extension in (("SVG", ".svg"), ("PDF", ".pdf"), ("JPEG", ".jpg")):
        if label in selected_filter:
            suffix = extension
            break
    return path + suffix


def build_plot_export(
    data,
    display_x,
    y_columns,
    colours,
    x_label,
    statistics,
    anomalies,
    *,
    title,
    dataset_name,
    layout="Overlay",
    show_anomalies=True,
    using_mjd=False,
    sigma_threshold=None,
    range_note=None,
):
    """Create a self-contained chart and summary table for the selected plot."""
    y_columns = list(y_columns)
    separate = layout == "Separate plots" and len(y_columns) > 1
    plot_count = len(y_columns) if separate else 1
    figure_height = max(8.5, 5.0 + plot_count * 2.7 + len(y_columns) * 0.30)
    figure = Figure(figsize=(16, figure_height), facecolor=_PAGE)
    figure.suptitle(title, x=0.075, y=0.975, ha="left", va="top",
                    fontsize=21, fontweight="bold", color=_INK)

    time_range = _format_range(display_x)
    details = [f"Dataset: {dataset_name}", f"X axis: {x_label}",
               f"Points: {len(data):,}", f"Range: {time_range}",
               f"Layout: {layout}"]
    if range_note and range_note != "Full plotted range":
        details.append(f"View: {range_note}")
    if sigma_threshold is not None:
        details.append(f"Anomaly threshold: {sigma_threshold:g}σ")
    figure.text(0.076, 0.932, "   ·   ".join(details), ha="left", va="top",
                fontsize=9.5, color=_MUTED)

    row_count = plot_count + 1
    ratios = [3.0] * plot_count + [max(1.0, 0.42 * len(y_columns))]
    grid = figure.add_gridspec(row_count, 1, height_ratios=ratios,
                               left=0.085, right=0.975, top=0.89,
                               bottom=0.07, hspace=0.58)
    axes = []
    for index in range(plot_count):
        axes.append(figure.add_subplot(grid[index, 0], sharex=axes[0] if axes else None))

    groups = [[column] for column in y_columns] if separate else [y_columns]
    for ax, columns in zip(axes, groups):
        for column in columns:
            series = data[column]
            ax.plot(display_x, series, color=colours.get(column, "#2563eb"),
                    linewidth=1.65, label=column, zorder=3)
            anomaly = anomalies.get(column, {})
            mask = anomaly.get("mask")
            if show_anomalies and mask is not None:
                mask = mask.reindex(data.index, fill_value=False)
                if mask.any():
                    ax.scatter(display_x.loc[mask], series.loc[mask], s=48,
                               facecolors="white", edgecolors="#d64545",
                               linewidths=1.5, marker="o", zorder=5,
                               label="Potential anomaly" if not any(
                                   item.get_label() == "Potential anomaly"
                                   for item in ax.collections
                               ) else "_nolegend_")
        ax.set_facecolor("white")
        ax.grid(True, color=_GRID, linewidth=0.8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(_GRID)
        ax.spines["bottom"].set_color(_GRID)
        ax.tick_params(colors=_MUTED, labelsize=8.5)
        ax.set_ylabel(columns[0] if separate or len(columns) == 1 else "Value",
                      color=_INK, fontsize=9, fontweight="medium")
        if not separate:
            ax.set_title("Series", loc="left", color=_INK, fontsize=10,
                         fontweight="bold", pad=8)
            ax.legend(loc="upper left", bbox_to_anchor=(1.005, 1),
                      frameon=False, fontsize=8.5)
    axes[-1].set_xlabel(x_label, color=_INK, fontsize=9, fontweight="medium")
    if using_mjd:
        for ax in axes:
            ax.ticklabel_format(axis="x", style="plain", useOffset=False)

    stats_ax = figure.add_subplot(grid[-1, 0])
    stats_ax.axis("off")
    stats_ax.text(0, 1.08, "Series summary", transform=stats_ax.transAxes,
                  ha="left", va="bottom", fontsize=11, fontweight="bold", color=_INK)
    headers = ["Series", "Points", "Mean", "Median", "Std dev", "Min", "Max", "Range", "Anomalies"]
    rows = []
    for column in y_columns:
        values = statistics.get(column, {})
        anomaly_count = anomalies.get(column, {}).get("count", 0)
        rows.append([
            column,
            f"{values.get('count', len(data)):,}",
            _format_value(values.get("mean")),
            _format_value(values.get("median")),
            _format_value(values.get("std_dev")),
            _format_value(values.get("min")),
            _format_value(values.get("max")),
            _format_value(values.get("range")),
            str(anomaly_count),
        ])
    table = stats_ax.table(cellText=rows, colLabels=headers, cellLoc="center",
                           colLoc="center", bbox=[0, 0, 1, 0.92],
                           colWidths=[0.16, 0.09, 0.105, 0.105, 0.11,
                                      0.10, 0.10, 0.10, 0.13])
    table.auto_set_font_size(False)
    table.set_fontsize(8.2 if len(rows) < 12 else 7.2)
    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor(_GRID)
        cell.set_linewidth(0.55)
        if row == 0:
            cell.set_facecolor("#e8eef6")
            cell.set_text_props(color=_INK, weight="bold")
        else:
            cell.set_facecolor("white" if row % 2 else "#f8fafd")
            cell.set_text_props(color=colours.get(y_columns[row - 1], _INK)
                                if column == 0 else _INK)
    if show_anomalies:
        figure.text(0.976, 0.025,
                    "○ Potential anomalies · classified against the full plotted range",
                    ha="right", va="bottom", fontsize=8, color=_MUTED)
    figure.subplots_adjust()
    return figure



