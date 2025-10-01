import csv
import random
import string
from pathlib import Path

def generate_crop_data(num_rows: int, output_path: str):
    """
    Generates a CSV file with mock organic crop stock data.
    Each crop appears only once with a unique fixed ID.
    All units are in 'kgs'.

    Args:
        num_rows (int): Number of unique crop rows to generate (max limited to number of crops).
        output_path (str): Path to save the CSV file.
    """
    crops = [
        "Carrots", "Spinach", "Kale", "Tomatoes", "Zucchini",
        "Potatoes", "Onions", "Beets", "Radishes", "Garlic",
        "Ginger", "Cabbage", "Cauliflower", "Broccoli", "Peas"
    ]
    
    # Limit rows to number of available crops
    if num_rows > len(crops):
        raise ValueError(f"Can only generate up to {len(crops)} unique crops, got {num_rows}.")

    unit = "kgs"

    # Assign fixed unique IDs to each crop
    crop_id_map = {
        crop: 'U' + ''.join(random.choices(string.digits, k=4))
        for crop in crops
    }

    # Select a non-repeating subset of crops
    selected_crops = random.sample(crops, num_rows)

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["ID", "Product name", "Quantity", "Price ($)", "Unit"])

        for crop in selected_crops:
            crop_id = crop_id_map[crop]
            quantity = random.randint(1, 500)
            price = f"{round(random.uniform(1.0, 10.0) * quantity, 2)}"
            writer.writerow([crop_id, crop, quantity, price, unit])

    print(f"Crop data with {num_rows} unique crops saved to {output_path}")