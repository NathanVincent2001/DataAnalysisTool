import csv
import io
import re
from collections import Counter
from pathlib import Path

import pandas as pd


_DELIMITERS = (",", ";", "\t", "|", "^", "~")
_WHITESPACE_DELIMITER = r"\s{2,}"
_SINGLE_SPACE_DELIMITER = r"\s+"


def _decode_csv(raw_bytes):
    """Decode common spreadsheet and instrument-export encodings."""
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return raw_bytes.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode this CSV using UTF-8, UTF-16 or Windows text encodings.")


def _split_sample(lines, delimiter):
    sample = "\n".join(lines)
    if delimiter in (_WHITESPACE_DELIMITER, _SINGLE_SPACE_DELIMITER):
        return [
            [part.strip() for part in re.split(delimiter, line.strip())]
            if line.strip() else []
            for line in lines
        ]
    return list(csv.reader(io.StringIO(sample), delimiter=delimiter, skipinitialspace=True))


def _detect_csv_layout(text):
    """Find the most consistent supported delimiter and likely table header."""
    lines = text.splitlines()
    directive_delimiter = None
    directive_line = None
    for index, line in enumerate(lines[:20]):
        match = re.match(r"^\s*sep=(.)\s*$", line, flags=re.IGNORECASE)
        if match:
            directive_delimiter = match.group(1)
            directive_line = index
            break

    eligible = [
        index for index, line in enumerate(lines)
        if line.strip() and not line.lstrip().startswith(("#", "//"))
        and not re.match(r"^\s*sep=.", line, flags=re.IGNORECASE)
    ]
    candidates = ((directive_delimiter,) if directive_delimiter else _DELIMITERS + (_WHITESPACE_DELIMITER, _SINGLE_SPACE_DELIMITER))
    starts = eligible[:20]
    best = None

    for delimiter in candidates:
        for start in starts:
            parsed = _split_sample(lines[start:start + 50], delimiter)
            widths = [len(row) for row in parsed if row and any(cell.strip() for cell in row)]
            widths = [width for width in widths if width > 1]
            if len(widths) < 2:
                continue
            counts = Counter(widths)
            width_count, width = max((count, width) for width, count in counts.items())
            consistency = width_count / len(widths)
            if consistency < 0.8:
                continue
            matching_rows = [row for row in parsed if len(row) == width]
            if not matching_rows:
                continue
            header_offset = next(
                offset for offset, row in enumerate(parsed) if len(row) == width
            )
            header_line = start + header_offset
            score = (consistency, width_count, width, -header_line)
            if best is None or score > best[0]:
                best = (score, delimiter, header_line, matching_rows)

    if best is None:
        raise ValueError(
            "Could not identify a table with at least two columns. Supported separators include comma, semicolon, tab, pipe, caret, tilde and spaces."
        )

    _, delimiter, header_line, sample_rows = best
    if directive_line is not None and delimiter == directive_delimiter:
        header_line = max(header_line, directive_line + 1)
    data_lines = lines[header_line + 1:header_line + 101]
    parsed_data = _split_sample(data_lines, delimiter)
    tokens = [cell.strip() for row in parsed_data for cell in row]
    european = sum(bool(re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+,\d+", token)) for token in tokens)
    american = sum(bool(re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+\.\d+", token)) for token in tokens)
    comma_decimal = sum(bool(re.fullmatch(r"[+-]?\d+,\d+", token)) for token in tokens)
    if european:
        decimal, thousands = ",", "."
    elif american:
        decimal, thousands = ".", ","
    elif comma_decimal and delimiter != ",":
        decimal, thousands = ",", None
    else:
        decimal, thousands = ".", None
    return delimiter, header_line, decimal, thousands


def _clean_column_names(dataframe):
    names = []
    used = set()
    for index, original in enumerate(dataframe.columns, start=1):
        name = str(original).replace("\ufeff", "").strip()
        if not name or name.lower().startswith("unnamed:"):
            name = f"Column {index}"
        candidate = name
        suffix = 2
        while candidate in used:
            candidate = f"{name} ({suffix})"
            suffix += 1
        used.add(candidate)
        names.append(candidate)
    dataframe.columns = names
    return dataframe


def load_csv(filepath):
    """Load delimited text from common CSV, spreadsheet and instrument exports."""
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    if filepath.suffix.lower() != ".csv":
        raise ValueError("File must be a CSV file.")

    text, _encoding = _decode_csv(filepath.read_bytes())
    delimiter, header_line, decimal, thousands = _detect_csv_layout(text)
    options = {
        "sep": delimiter,
        "engine": "python",
        "skiprows": header_line,
        "skipinitialspace": True,
        "decimal": decimal,
        "on_bad_lines": "error",
    }
    if thousands:
        options["thousands"] = thousands
    if any(line.lstrip().startswith("#") for line in text.splitlines()):
        options["comment"] = "#"

    try:
        dataframe = pd.read_csv(io.StringIO(text), **options)
    except (pd.errors.ParserError, UnicodeError, ValueError) as error:
        raise ValueError(f"Could not parse CSV using the detected format: {error}") from error

    if dataframe.empty:
        raise ValueError("CSV file contains no data rows.")
    dataframe = _clean_column_names(dataframe)
    for column in dataframe.columns:
        dtype = dataframe[column].dtype
        if pd.api.types.is_object_dtype(dtype) or isinstance(dtype, pd.StringDtype):
            dataframe[column] = dataframe[column].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )
    return dataframe

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
    parsed = pd.to_datetime(sample, errors="coerce", utc=True, format="mixed")
    return float(parsed.notna().mean()) >= minimum_success


def detect_time_column(dataframe):
    """Detect a likely timestamp column from its type, name, or values."""
    # Prefer already parsed datetime columns and explicit naming hints.
    for column in dataframe.columns:
        series = dataframe[column]
        name = str(column).lower()
        if pd.api.types.is_datetime64_any_dtype(series):
            return column
        if ("time" in name or "date" in name) and _datetime_parse_candidate(series):
            return column
    # Fall back to content-based detection for blank/misleading headers.
    for column in dataframe.columns:
        if _datetime_parse_candidate(dataframe[column]):
            return column
    return None
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


def detect_anomalies(dataframe, column, sigma_threshold=5.0):
    """
    Flag potential anomalies whose absolute deviation from the mean is
    greater than or equal to ``sigma_threshold * standard deviation``.

    The calculation is performed only on the supplied dataframe, so callers
    can pass an already filtered time range. The returned mask preserves the
    dataframe index for straightforward plotting.
    """
    if sigma_threshold <= 0:
        raise ValueError("Sigma threshold must be greater than zero.")

    series = pd.to_numeric(dataframe[column], errors="coerce")
    valid = series.dropna()
    mask = pd.Series(False, index=dataframe.index, dtype=bool)

    if valid.empty:
        return {
            "mask": mask,
            "count": 0,
            "threshold": float(sigma_threshold),
            "max_deviation_sigma": 0.0,
        }

    mean = valid.mean()
    std_dev = valid.std()

    # A constant series, or a series with too few values for sample standard
    # deviation, cannot produce a meaningful sigma-based anomaly score.
    if pd.isna(std_dev) or std_dev == 0:
        return {
            "mask": mask,
            "count": 0,
            "threshold": float(sigma_threshold),
            "max_deviation_sigma": 0.0,
        }

    sigma_distance = (series - mean).abs() / std_dev
    mask = sigma_distance.ge(float(sigma_threshold)) & series.notna()

    return {
        "mask": mask,
        "count": int(mask.sum()),
        "threshold": float(sigma_threshold),
        "max_deviation_sigma": float(sigma_distance.max()),
    }










