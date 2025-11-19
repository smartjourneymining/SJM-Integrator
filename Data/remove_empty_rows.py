import csv
from pathlib import Path

def remove_empty_rows(input_file='combined.csv', output_file='combined.csv'):
    """
    Remove empty rows from a CSV file.
    A row is considered empty if all fields are empty or contain only whitespace.
    """
    rows_read = 0
    rows_kept = 0
    rows_removed = 0
    
    all_rows = []
    
    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        
        # Read header
        header = next(reader)
        all_rows.append(header)
        rows_read += 1
        
        # Read data rows
        for row in reader:
            rows_read += 1
            
            # Check if row is empty (all fields are empty or whitespace)
            is_empty = all(not field or not field.strip() for field in row)
            
            if not is_empty:
                all_rows.append(row)
                rows_kept += 1
            else:
                rows_removed += 1
    
    print(f"Read {rows_read} total rows (including header)")
    print(f"Removed {rows_removed} empty rows")
    print(f"Keeping {rows_kept} data rows")
    
    # Write the cleaned CSV file
    print(f"\nWriting cleaned data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerows(all_rows)
    
    print(f"Successfully updated {output_file}")
    print(f"Total rows in output: {len(all_rows)} (1 header + {rows_kept} data rows)")

if __name__ == '__main__':
    remove_empty_rows()

