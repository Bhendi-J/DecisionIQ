"""Derive compact, attributed country/product series from UCI Online Retail."""

import argparse
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    frame = pd.read_excel(args.input)
    frame = frame[(frame.Quantity != 0) & (frame.UnitPrice > 0)].copy()
    # Retain merchandise SKUs; postage, manual adjustments, and other nonproduct codes
    # must not be ranked as products or used to infer product demand.
    frame = frame[frame.StockCode.astype(str).str.match(r"^\d{5}[A-Za-z]*$")]
    frame["date"] = pd.to_datetime(frame.InvoiceDate).dt.strftime("%Y-%m-%d")
    frame["sales"] = frame.Quantity * frame.UnitPrice
    results = []
    for country, company in [
        ("United Kingdom", "aster"),
        ("France", "maison"),
        ("Germany", "nordhaus"),
    ]:
        part = frame[frame.Country == country]
        products = part.groupby("StockCode").sales.sum().nlargest(12).index
        part = part[part.StockCode.isin(products)]
        grouped = (
            part.groupby(["date", "StockCode"])
            .agg(
                product=("Description", "first"), units=("Quantity", "sum"), sales=("sales", "sum")
            )
            .reset_index()
            .rename(columns={"StockCode": "product_id"})
        )
        grouped["company_id"] = company
        results.append(grouped)
    output = Path(__file__).resolve().parents[1] / "services/finance/data/demo_sales.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(results).to_csv(output, index=False, float_format="%.2f")
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
