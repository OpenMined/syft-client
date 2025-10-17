import csv

import syft_client as sc

data_path = "syft://private/crop_data/data.csv"
resolved_path = sc.resolve_path(data_path)

with open(resolved_path, "r") as file:
    csv_reader = csv.DictReader(file)
    total_quantity = 0
    for row in csv_reader:
        quantity = int(row["Quantity"])
        total_quantity += quantity

    print(f"Total Quantity: {total_quantity}")
