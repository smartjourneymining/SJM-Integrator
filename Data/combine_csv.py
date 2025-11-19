import csv
import os
from pathlib import Path
from collections import OrderedDict

def combine_csv_files(data_dir='.', output_file='combined.csv'):
    """
    Combine all CSV files in the current directory into a single CSV file.
    Handles different column orders and additional columns by collecting all unique columns.
    """
    data_path = Path(data_dir)
    csv_files = sorted([f for f in data_path.glob('*.csv') if f.name != 'combined.csv'])
    
    if not csv_files:
        print(f"No CSV files found in {data_dir}")
        return
    
    print(f"Found {len(csv_files)} CSV files to combine")
    
    # First pass: collect all unique columns from all files
    all_columns = OrderedDict()
    column_order = ['*.uuid', '*.event', '*.timestamp']  # Core columns that should be first
    
    print("\nScanning files to collect all columns...")
    for csv_file in csv_files:
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                if reader.fieldnames:
                    for col in reader.fieldnames:
                        if col not in all_columns:
                            all_columns[col] = None
        except Exception as e:
            print(f"  Warning: Could not read {csv_file.name}: {e}")
    
    # Build final column order: core columns first, then others
    final_columns = []
    for col in column_order:
        if col in all_columns:
            final_columns.append(col)
            all_columns.pop(col, None)
    
    # Add remaining columns in the order they were encountered
    final_columns.extend(all_columns.keys())
    
    print(f"Found {len(final_columns)} unique columns")
    print(f"Column order: {', '.join(final_columns[:5])}...")
    
    # Second pass: read all data
    all_rows = []
    
    for csv_file in csv_files:
        print(f"Processing {csv_file.name}...")
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                
                if not reader.fieldnames:
                    print(f"  Warning: {csv_file.name} has no header, skipping")
                    continue
                
                row_count = 0
                for row in reader:
                    # Create a new row with all columns, filling missing ones with empty strings
                    mapped_row = {}
                    for col in final_columns:
                        mapped_row[col] = row.get(col, '')
                    
                    all_rows.append(mapped_row)
                    row_count += 1
                
                print(f"  Added {row_count} rows from {csv_file.name}")
        
        except Exception as e:
            print(f"  Error processing {csv_file.name}: {e}")
            continue
    
    # Write the combined CSV file
    if all_rows:
        print(f"\nWriting combined CSV file with {len(all_rows)} total rows...")
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=final_columns, delimiter=';')
            writer.writeheader()
            writer.writerows(all_rows)
        
        print(f"Successfully created {output_file}")
        print(f"Total rows: {len(all_rows)}")
        print(f"Total columns: {len(final_columns)}")
    else:
        print("No rows to write")

if __name__ == '__main__':
    combine_csv_files()

