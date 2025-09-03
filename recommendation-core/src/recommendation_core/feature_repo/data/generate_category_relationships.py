"""
This script is not called by the application or any job.
It was used to generate the category_relationships.parquet file that is
in turn used to load the category table by the init_backend.py file. 
This script takes as its source the recommendation_items.parquet file. If the
recommendations_items.parquet file never changes, there is no need to run this script again.
"""

import pandas as pd
import io

try:
    raw_item_data_file = "./recommendation_items.parquet"
    df_raw = pd.read_parquet(raw_item_data_file, columns=['category'])

    # Use a set to store unique relationships to avoid duplicates
    unique_relationships = set()

    # Process each row (each category path)
    for category_path in df_raw['category'].tolist():
        # Split the path by '|' to get individual categories
        path_components = category_path.split('|')
        
        # Generate parent-child relationships
        for i, category in enumerate(path_components):
            parent_category = path_components[i-1] if i > 0 else None
            # Add the relationship as a tuple to the set
            unique_relationships.add((category.strip(), parent_category))

    # Convert the set of unique relationships to a list of dictionaries for the DataFrame
    data = [{'Category': cat, 'Parent Category': parent} for cat, parent in unique_relationships]

    # Create a Pandas DataFrame from the relationships
    df_relationships = pd.DataFrame(data)

    # Sort the DataFrame for better readability
    df_relationships.sort_values(by=['Parent Category', 'Category'], inplace=True, na_position='first')

    # Save the resulting DataFrame to a new Parquet file
    output_parquet_path = './category_relationships.parquet'
    df_relationships.to_parquet(output_parquet_path, index=False)

except FileNotFoundError:
    print(f"Error: The file '{raw_item_data_file}' was not found. Please check the file path.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")