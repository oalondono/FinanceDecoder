import glob
import os
import sys
import pandas as pd


def tidy_from_file(path: str) -> pd.DataFrame:
    """
    Convert one workbook to tidy long format.

    Rules
    -----
    1. Keep the sheet’s own formula results – no recalculation in Python.
    2. Skip **rows ≥ 29** (1‑indexed) **when their value is exactly 0**.
    3. Do **not** include a given year at all when **every** value for that year
       in worksheet rows 1‑28 is either blank/NaN or 0 (handles MB_Steinbach 2024 case).
    """
    base = os.path.basename(path)
    name_no_ext = os.path.splitext(base)[0]

    # ── state & city from filename ────────────────────────────────
    if "_" in name_no_ext:
        state, city = name_no_ext.split("_", 1)
    else:
        state, city = None, name_no_ext

    # ── read sheet exactly as‑is ─────────────────────────────────-
    df = pd.read_excel(path, sheet_name="Input", header=None, engine="openpyxl")

    # Find header row: first numeric year appearing in column E (index 4)
    year_row = df[ df[4].apply(lambda x: isinstance(x, (int, float)) and 1900 <= x <= 2100) ].index[0]

    raw_years = df.loc[year_row, 4:].tolist()

    # Determine which year columns actually have data in rows ≤ 28
    valid_years: list[int] = []      # list of year values
    valid_cols:  list[int] = []      # matching absolute column indices in df

    for offset, yr in enumerate(raw_years):
        if pd.isna(yr):
            continue  # blank header cell

        col_idx = 4 + offset  # absolute column index in the DataFrame

        # rows to inspect: from first data row (year_row+2) up to worksheet row 28
        start_idx = year_row + 2
        end_idx   = min(27, df.shape[0] - 1)  # 0‑based index 27 == worksheet row 28

        if start_idx > end_idx:
            # workbook has fewer than (year_row+2) rows – unlikely but guard anyway
            continue

        segment = df.loc[start_idx:end_idx, col_idx]

        has_data = segment.apply(lambda x: pd.notna(x) and x != 0).any()
        if has_data:
            valid_years.append(int(yr))
            valid_cols.append(col_idx)

    # ── collect variable labels (column A) ────────────────────────
    var_rows: list[tuple[str, int]] = []
    empty_streak = 0
    for r in range(year_row + 2, df.shape[0]):
        label = df.iloc[r, 0]
        if pd.isna(label) or str(label).strip() == "":
            empty_streak += 1
            if empty_streak >= 5:
                break  # assume table ended after 5 consecutive blank lines
            continue
        empty_streak = 0
        var_rows.append((str(label).strip(), r))

    # ── build tidy records ───────────────────────────────────────
    records = []
    for label, r in var_rows:
        for yr, col_idx in zip(valid_years, valid_cols):
            val = df.iat[r, col_idx]
            # skip blanks
            if pd.isna(val):
                continue
            records.append(
                {
                    "state": state,
                    "city": city,
                    "variable": label,
                    "year": yr,
                    "value": val,
                }
            )

    return pd.DataFrame.from_records(records)


# ── batch‑process workbooks (recursive search) ───────────────────

def find_workbooks(folder: str) -> list[str]:
    """Return list of .xls/.xlsx/.xlsm files under *folder* (recursively)."""
    pattern = os.path.join(folder, "**", "*.xls*")
    return [p for p in glob.glob(pattern, recursive=True) if not os.path.basename(p).startswith("~$")]


def main() -> None:
    root = "/media/oscar/Files/Projects/Financial Decoder Dash/Scrape/downloaded_xls"
    workbooks = find_workbooks(root)
    if not workbooks:
        print(f"No Excel files found beneath: {root}")
        sys.exit(1)

    frames: list[pd.DataFrame] = []
    for wb in workbooks:
        try:
            df = tidy_from_file(wb)
            if not df.empty:
                frames.append(df)
        except Exception as exc:
            print(f"⚠️  Skipping {wb}: {exc}")

    if not frames:
        print("No usable data extracted from any workbook.")
        sys.exit(1)

    tidy_data = pd.concat(frames, ignore_index=True)
    out_csv = os.path.join(root, "financials_tidy.csv")
    tidy_data.to_csv(out_csv, index=False)

    print(
        f"✓ Wrote {len(tidy_data):,} rows from {len(frames)} workbook(s) to {out_csv}"
    )


if __name__ == "__main__":
    main()
