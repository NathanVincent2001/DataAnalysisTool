from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def load_csv(filepath):
    """
    Load a CSV file and return it as a pandas DataFrame.
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    if filepath.suffix.lower() != ".csv":
        raise ValueError("File must be a CSV file.")

    dataframe = pd.read_csv(filepath)

    if dataframe.empty:
        raise ValueError("CSV file contains no data.")

    return dataframe


def inspect_data(dataframe):
    """
    Display basic information about the imported dataset.
    """
    print("\nColumns:")
    for index, column in enumerate(dataframe.columns):
        print(f"{index}: {column}")

    print(f"\nRows: {len(dataframe)}")
    print(f"Columns: {len(dataframe.columns)}")

    numeric_columns = dataframe.select_dtypes(
        include="number"
    ).columns.tolist()

    return numeric_columns


def select_column(columns, message="Select column"):
    """
    Allow the user to select a column by number.
    """
    if not columns:
        raise ValueError("No suitable columns were found.")

    print("\nAvailable columns")
    print("-" * 30)

    for index, column in enumerate(columns, start=1):
        print(f"{index}: {column}")

    while True:
        selection = input(f"\n{message}: ").strip()

        try:
            selection = int(selection)

            if 1 <= selection <= len(columns):
                return columns[selection - 1]

        except ValueError:
            pass

        print("Please enter one of the numbers shown above.")


def detect_time_column(dataframe):
    """
    Look for column names that appear to contain timestamps.
    """
    timestamp_columns = [
        column for column in dataframe.columns
        if "time" in column.lower()
        or "date" in column.lower()
    ]

    if timestamp_columns:
        return timestamp_columns[0]

    return None


def select_time_range(dataframe, time_column):
    """
    Display available time range and allow selection
    of a smaller interval.
    """
    start_available = dataframe[time_column].min()
    end_available = dataframe[time_column].max()

    print("\nAvailable time range")
    print("-" * 30)
    print(f"Start: {start_available}")
    print(f"End:   {end_available}")

    print("\nPress Enter to use the full available range.")

    start_input = input("Start time: ").strip()
    end_input = input("End time:   ").strip()

    start_time = (
        pd.to_datetime(start_input)
        if start_input
        else start_available
    )

    end_time = (
        pd.to_datetime(end_input)
        if end_input
        else end_available
    )

    if start_time > end_time:
        raise ValueError("Start time must be before end time.")

    if start_time < start_available:
        raise ValueError("Start time is outside the available data.")

    if end_time > end_available:
        raise ValueError("End time is outside the available data.")

    selected_data = dataframe[
        (dataframe[time_column] >= start_time)
        & (dataframe[time_column] <= end_time)
    ].copy()

    if selected_data.empty:
        raise ValueError("No data exists within that time range.")

    print("\nSelected time range")
    print("-" * 30)
    print(f"Start:  {start_time}")
    print(f"End:    {end_time}")
    print(f"Points: {len(selected_data)}")

    return selected_data


def calculate_statistics(dataframe, column):
    """
    Calculate basic statistics for a numerical column.
    """
    series = dataframe[column].dropna()

    if series.empty:
        raise ValueError("No numerical data available for statistics.")

    return {
        "count": series.count(),
        "mean": series.mean(),
        "median": series.median(),
        "std_dev": series.std(),
        "min": series.min(),
        "max": series.max(),
        "range": series.max() - series.min()
    }


def display_statistics(statistics):
    """
    Print calculated statistics.
    """
    print("\nStatistics")
    print("-" * 30)

    for name, value in statistics.items():

        if name == "count":
            print(f"{name:<10}: {value}")
        else:
            print(f"{name:<10}: {value:.6g}")


def plot_data(dataframe, x_column, y_column):
    """
    Plot one column against another.
    """
    fig, ax = plt.subplots()

    ax.plot(
        dataframe[x_column],
        dataframe[y_column]
    )

    ax.set_xlabel(x_column)
    ax.set_ylabel(y_column)
    ax.set_title(f"{y_column} vs {x_column}")
    ax.grid(True)

    fig.autofmt_xdate()
    fig.tight_layout()

    plt.show()


def run_analysis(dataframe, numeric_columns, x_column, is_time_series):
    """
    Run one analysis cycle on an already-loaded dataset.
    """

    y_columns = [
        column for column in numeric_columns
        if column != x_column
    ]

    y_column = select_column(
        y_columns,
        "Select Y-axis signal"
    )

    if is_time_series:
        selected_data = select_time_range(
            dataframe,
            x_column
        )
    else:
        selected_data = dataframe

    statistics = calculate_statistics(
        selected_data,
        y_column
    )

    display_statistics(statistics)

    plot_data(
        selected_data,
        x_column,
        y_column
    )


def main():

    filepath = input("Enter CSV filepath: ").strip('"')

    try:
        data = load_csv(filepath)

        numeric_columns = inspect_data(data)

        if len(data.columns) < 2:
            raise ValueError(
                "At least two columns are required for plotting."
            )

        time_series = input(
            "Is this time-series data? [Y/n]: "
        ).strip().lower()

        is_time_series = time_series in ("", "y", "yes")

        if is_time_series:
            x_column = detect_time_column(data)

            if x_column:
                data[x_column] = pd.to_datetime(
                    data[x_column]
                )

                print(
                    f"\nUsing '{x_column}' as the time axis."
                )

            else:
                print(
                    "\nNo timestamp column automatically detected."
                )

                x_column = select_column(
                    list(data.columns),
                    "Select time column"
                )

                data[x_column] = pd.to_datetime(
                    data[x_column]
                )

        else:
            x_column = select_column(
                list(data.columns),
                "Select X-axis column"
            )

        # Dataset remains loaded while analyses are repeated
        while True:

            try:
                run_analysis(
                    data,
                    numeric_columns,
                    x_column,
                    is_time_series
                )

            except Exception as error:
                print(f"\nAnalysis error: {error}")

            again = input(
                "\nCreate another plot from this dataset? [Y/n]: "
            ).strip().lower()

            if again not in ("", "y", "yes"):
                print("\nExiting Data Analysis Tool.")
                break

    except Exception as error:
        print(f"\nError: {error}")


if __name__ == "__main__":
    main()