import csv

def augment_csv(input_file, output_file):
    """
    Augment the CSV with computed.sender and computed.receiver columns.
    
    Logic:
    - computed.sender: Use *.uuid if *.properties.sender is empty/not bookis/not BRING, 
                       otherwise use *.properties.sender
    - computed.receiver: Use *.uuid if sender is bookis or BRING, otherwise use 'bookis'
    """
    
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile, delimiter=';')
        
        # Get the original fieldnames and add new columns
        fieldnames = reader.fieldnames + ['computed.sender', 'computed.receiver']
        
        rows = []
        for row in reader:
            uuid = row['*.uuid']
            original_sender = row['*.properties.sender'].strip()
            
            # Determine computed.sender
            if original_sender in ['bookis', 'BRING']:
                computed_sender = original_sender
            else:
                # Empty or other value - use user ID
                computed_sender = uuid
            
            # Determine computed.receiver
            if original_sender in ['bookis', 'BRING']:
                # Service provider sent it, so user is receiver
                computed_receiver = uuid
            else:
                # User sent it (or empty), so bookis is receiver
                computed_receiver = 'bookis'
            
            row['computed.sender'] = computed_sender
            row['computed.receiver'] = computed_receiver
            rows.append(row)
    
    # Write the augmented CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"✓ Augmented CSV saved to {output_file}")
    print(f"✓ Added columns: computed.sender, computed.receiver")
    print(f"✓ Processed {len(rows)} rows")

if __name__ == "__main__":
    augment_csv('Data/combined.csv', 'Data/combined-augmented.csv')

