"""Backward-compatible exports for data analysis and the legacy CLI."""

from data_analysis import (
    _datetime_parse_candidate,
    calculate_statistics,
    detect_anomalies,
    detect_time_column,
    load_csv,
)
from analysis_cli import (
    display_statistics,
    inspect_data,
    plot_data,
    run_analysis,
    select_column,
    select_time_range,
)


def main():
    from analysis_cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
