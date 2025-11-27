"""
build_malaria_district_csv.py

Purpose:
  - Download known MOH / RCDC PDF reports (you can add more URLs)
  - Extract tables that appear to contain "Malaria" or "Malaria Cases"
  - Parse district-level rows and produce a unified CSV:
      columns: district, year, cases_total, cases_imported, cases_indigenous, notes, source_url

Requirements:
  - Python 3.9+
  - pip install requests pandas camelot-py[cv] tabulate pdfplumber
  - camelot requires ghostscript and Tk/java (platform dependent). Alternatively use tabula-py (needs Java).
  - You may need to tweak page/table selection per PDF because PDFs vary widely.

Usage:
  python build_malaria_district_csv.py
"""

import os
import re
import io
import requests
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse

# Optional: try camelot if installed and system supports it
try:
    import camelot
    HAVE_CAMELOT = True
except Exception:
    HAVE_CAMELOT = False

OUT_DIR = Path("malaria_reports")
OUT_DIR.mkdir(exist_ok=True)

# Add MOH/RCDC PDF URLs you want to extract from (examples discovered earlier)
PDF_SOURCES = [
    # Replace/add URLs you want to use. Example entries (update to the correct URLs if changed):
    "https://moh.gov.bt/wp-content/uploads/2025/01/Annual-Health-Bulletin-2015.pdf",
    "https://moh.gov.bt/wp-content/uploads/2025/01/Annual-Health-Bulletin-2016.pdf",
    "https://moh.gov.bt/wp-content/uploads/2025/01/Health-Bulletin_2018.pdf",
    "https://www.rcdc.gov.bt/web/wp-content/uploads/2024/07/RCDC-2nd-Quarterly-Bulletin_2024.pdf",
    # add more PDFs (annual bulletins for other years)...
]

def download_pdf(url, out_dir=OUT_DIR):
    filename = Path(urlparse(url).path).name
    out_path = out_dir / filename
    if out_path.exists():
        print(f"Using cached: {out_path}")
        return out_path
    print(f"Downloading {url} ...")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    out_path.write_bytes(r.content)
    print(f"Saved {out_path}")
    return out_path

def find_candidate_pages_for_keyword(pdf_path, keyword="Malaria"):
    """Return a list of page numbers (1-indexed) that contain the keyword."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if keyword.lower() in text.lower():
                pages.append(i)
    return pages

def extract_tables_from_pdf(pdf_path, pages):
    """Try camelot first, fallback to pdfplumber table parsing.
       Returns list of pandas.DataFrame objects and (page_no, method) used."""
    tables = []
    for p in pages:
        page_spec = str(p)
        print(f"Extracting tables from {pdf_path.name} page {p} ...")
        extracted = []
        # Try camelot:
        if HAVE_CAMELOT:
            try:
                # Camelot expects pages range like '3'
                camel_tables = camelot.read_pdf(str(pdf_path), pages=page_spec, flavor="stream")
                for t in camel_tables:
                    df = t.df
                    extracted.append(("camelot", p, df))
            except Exception as e:
                print("Camelot failed on page", p, ":", e)
        # Fallback: pdfplumber table extraction
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page = pdf.pages[p-1]
                pdf_tables = page.extract_tables()
                for tbl in pdf_tables:
                    df = pd.DataFrame(tbl)
                    extracted.append(("pdfplumber", p, df))
        except Exception as e:
            print("pdfplumber failed on page", p, ":", e)
        # collect
        for item in extracted:
            tables.append(item)
    return tables

def normalize_table_df(raw_df):
    """
    Try to identify columns like 'District' and years or 'Cases' and convert to long format.
    This is heuristic — you will often need to tweak column mapping per PDF.
    """
    df = raw_df.copy()
    # drop fully empty rows/cols
    df = df.dropna(how="all").dropna(axis=1, how="all")
    # reset header if first row looks like header
    # find a row that contains 'district' or 'dzongkhag' (Bhutanese term)
    header_row = None
    for i in range(min(3, len(df))):
        row = " ".join([str(x) for x in df.iloc[i].astype(str)])
        if re.search(r"district|dzongkhag|dzongkhags|distrito", row, flags=re.I):
            header_row = i
            break
    if header_row is not None:
        df.columns = df.iloc[header_row].astype(str).tolist()
        df = df.drop(index=range(0, header_row+1)).reset_index(drop=True)
    # simplify column names
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    # attempt to find district column
    district_col = None
    for c in df.columns:
        if re.search(r"district|dzongkhag|dzongkhags|name", str(c), flags=re.I):
            district_col = c
            break
    # attempt to find year columns (4-digit)
    year_cols = [c for c in df.columns if re.search(r"20\d{2}|19\d{2}", str(c))]
    # If year columns exist -> melt to long
    if district_col and year_cols:
        df_long = df.melt(id_vars=[district_col], value_vars=year_cols, var_name="year", value_name="cases_raw")
        df_long["year"] = df_long["year"].astype(str).str.extract(r"(20\d{2}|19\d{2})")
        df_long = df_long.rename(columns={district_col: "district"})
        return df_long[["district", "year", "cases_raw"]]
    # Otherwise, if table looks like district | total | imported | indigenous
    else:
        # heuristic column names mapping
        mapping = {}
        for c in df.columns:
            lc = c.lower()
            if "district" in lc or "dzongkhag" in lc:
                mapping[c] = "district"
            elif "import" in lc:
                mapping[c] = "cases_imported"
            elif "indigenous" in lc or "local" in lc:
                mapping[c] = "cases_indigenous"
            elif re.search(r"case|total", lc):
                mapping[c] = "cases_total"
        if mapping:
            out = df.rename(columns=mapping)
            needed = ["district", "cases_total", "cases_imported", "cases_indigenous"]
            for n in needed:
                if n not in out.columns:
                    out[n] = pd.NA
            # If year not present, try infer from filename or prompt user to set year.
            return out[[c for c in ["district", "cases_total", "cases_imported", "cases_indigenous"] if c in out.columns]]
    # If nothing matched, return None
    return None

def parse_and_aggregate(pdf_path, source_url):
    pages = find_candidate_pages_for_keyword(pdf_path, "Malaria")
    if not pages:
        print(f"No candidate pages containing 'Malaria' found in {pdf_path.name}")
        return pd.DataFrame()
    raw_tables = extract_tables_from_pdf(pdf_path, pages)
    collected = []
    for method, page, raw_df in raw_tables:
        norm = normalize_table_df(raw_df)
        if norm is None:
            continue
        # add metadata
        norm["source_url"] = source_url
        norm["source_pdf"] = pdf_path.name
        norm["source_page"] = page
        collected.append(norm)
    if collected:
        merged = pd.concat(collected, ignore_index=True, sort=False)
        return merged
    else:
        return pd.DataFrame()

def infer_year_from_filename(filename):
    m = re.search(r"(19|20)\d{2}", filename)
    if m:
        return int(m.group(0))
    return None

def clean_and_standardize(df):
    """Make final adjustments: strip district names, parse case numbers, set year."""
    if df.empty:
        return df
    df = df.copy()
    # if a 'year' column exists but is messy, clean it
    if "year" in df.columns:
        df["year"] = df["year"].astype(str).str.extract(r"(20\d{2}|19\d{2})")
    # if year missing, try to infer from source_pdf
    if "year" not in df.columns or df["year"].isna().all():
        df["year"] = df["source_pdf"].apply(lambda x: infer_year_from_filename(x))
    # clean district names
    df["district"] = df["district"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    # parse cases to numeric (from cases_raw or total fields)
    if "cases_raw" in df.columns:
        df["cases_total"] = pd.to_numeric(df["cases_raw"].astype(str).str.replace(r"[^0-9\-]", "", regex=True), errors="coerce")
    if "cases_total" in df.columns:
        df["cases_total"] = pd.to_numeric(df["cases_total"].astype(str).str.replace(r"[^0-9\-]", "", regex=True), errors="coerce")
    if "cases_imported" in df.columns:
        df["cases_imported"] = pd.to_numeric(df["cases_imported"].astype(str).str.replace(r"[^0-9\-]", "", regex=True), errors="coerce")
    if "cases_indigenous" in df.columns:
        df["cases_indigenous"] = pd.to_numeric(df["cases_indigenous"].astype(str).str.replace(r"[^0-9\-]", "", regex=True), errors="coerce")
    # keep relevant columns
    keep_cols = ["district", "year", "cases_total", "cases_imported", "cases_indigenous", "source_url", "source_pdf", "source_page"]
    for c in keep_cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[keep_cols]

def main():
    all_records = []
    for url in PDF_SOURCES:
        try:
            pdf_path = download_pdf(url)
        except Exception as e:
            print("Download failed:", url, e)
            continue
        parsed = parse_and_aggregate(pdf_path, url)
        if parsed.empty:
            print("No tables parsed from", pdf_path.name)
            continue
        cleaned = clean_and_standardize(parsed)
        all_records.append(cleaned)
    if not all_records:
        print("No data extracted. You may need to update PDF_SOURCES or tweak parsing heuristics.")
        return
    df_all = pd.concat(all_records, ignore_index=True, sort=False)
    # normalize district names (optional: map local spellings to canonical names)
    df_all.to_csv(OUT_DIR / "malaria_districts_raw_extracted.csv", index=False)
    print("Saved raw extracted CSV to", OUT_DIR / "malaria_districts_raw_extracted.csv")
    # Post-processing / aggregation example: group by district+year
    df_group = df_all.groupby(["district", "year"], dropna=False).agg({
        "cases_total": "sum",
        "cases_imported": "sum",
        "cases_indigenous": "sum",
    }).reset_index()
    df_group.to_csv(OUT_DIR / "malaria_districts_by_year_aggregated.csv", index=False)
    print("Saved aggregated CSV to", OUT_DIR / "malaria_districts_by_year_aggregated.csv")
    print("Done. Inspect the CSVs, then you may want to manually validate entries against PDFs.")

if __name__ == "__main__":
    main()
