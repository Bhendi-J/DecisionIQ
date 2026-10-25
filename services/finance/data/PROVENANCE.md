# Demonstration sales data

Source: Daqing Chen, **Online Retail**, UCI Machine Learning Repository (2015).
DOI: https://doi.org/10.24432/C5BW33
Source page: https://archive.ics.uci.edu/dataset/352/online%2Bretail
License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The original source describes transactions for a single UK retailer from December 1,
2010 to December 9, 2011. Unit prices are in pounds sterling (GBP).

`demo_sales.csv` is an adaptation: nonpositive prices and zero quantities are excluded. Signed
negative quantities, including cancellations and returns, are retained. Non-merchandise codes (postage, manual adjustments, fees) are excluded by requiring
a five-digit SKU with optional letter suffix. For each of the UK, France, and Germany customer
country segments, the twelve products with the highest remaining sales value are
retained. Rows aggregate quantity and quantity × unit price by date and product.
These are **net recorded sales values**, including signed returns/cancellations,
not received cash, profit, or complete retailer revenue. The selected product subset is fixed using
the full historical dataset for demonstration; forecast evaluation is conditional
on that selected series and is not an unbiased evaluation of product selection.

Aster Trading, Maison Supply, and Nordhaus are fictional demonstration workspaces
assigned to those country segments. They are not independently observed companies.
The interface displays the source segment and historical analysis cutoff.

Reproduce with `python -m scripts.prepare_demo_data --input /path/to/OnlineRetail.xlsx`.
The original workbook is deliberately not bundled. `revenue_history.csv` is the
separate all-retailer positive-sales aggregate retained for the legacy model API.
