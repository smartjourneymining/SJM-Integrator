from tkinter import Button, Canvas, Frame, Label, Scrollbar, Entry, IntVar, Checkbutton, messagebox
from tkinter.ttk import Combobox
import json
import os
import pandas as pd


class PreprocessorUI:
    def __init__(self, master, dataframe, csv_columns):
        self.dataframe = dataframe.copy()
        self.csv_columns = list(csv_columns)
        self.standard_fields = self.load_standard_fields()
        self.mappings = {}  # standard_field -> csv_column
        self.auto_generate = {}  # standard_field -> generation type (applied if column is NULL)
        self.static_values = {}  # standard_field -> static value (applied if column is NULL)
        self.skip_fields = set()  # standard_fields to skip (not create in output)
        
        # Load saved configuration if it exists (before creating UI)
        self.load_preprocessing_config()
        
        self.master = master
        master.title("Data Preprocessing: Column Mapping")
        master.geometry("{}x{}".format(1200, 800))
        master.minsize(1200, 800)
        
        # Create main frame
        main_frame = Frame(master)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        Label(main_frame, text="Map CSV columns to standard field names", 
              font=('TkDefaultFont', 12, 'bold')).pack(anchor='w', pady=(0, 10))
        Label(main_frame, 
              text="Map your CSV columns to standard fields. For missing fields, set static values or enable auto-generation. Use 'Skip Field' to exclude fields you don't need.",
              font=('TkDefaultFont', 9)).pack(anchor='w', pady=(0, 5))
        
        # Instructions
        instructions_frame = Frame(main_frame)
        instructions_frame.pack(anchor='w', pady=(0, 10))
        Label(instructions_frame, text="Behavior:", font=('TkDefaultFont', 9, 'bold')).pack(anchor='w')
        Label(instructions_frame, text="- If CSV Column is selected alone: Use column value", 
              font=('TkDefaultFont', 8)).pack(anchor='w', padx=(10, 0))
        Label(instructions_frame, text="- If CSV Column + Static Value: Use column value, fallback to static if NULL", 
              font=('TkDefaultFont', 8)).pack(anchor='w', padx=(10, 0))
        Label(instructions_frame, text="- If CSV Column + Auto-Generate: Use column value, fallback to auto-generation if NULL", 
              font=('TkDefaultFont', 8)).pack(anchor='w', padx=(10, 0))
        Label(instructions_frame, text="- If Static Value alone: Always use static value", 
              font=('TkDefaultFont', 8)).pack(anchor='w', padx=(10, 0))
        Label(instructions_frame, text="- If Auto-Generate alone: Always auto-generate", 
              font=('TkDefaultFont', 8)).pack(anchor='w', padx=(10, 0))
        
        # Legend for field priority
        legend_frame = Frame(main_frame)
        legend_frame.pack(anchor='w', pady=(0, 10))
        Label(legend_frame, text="Legend:", font=('TkDefaultFont', 9, 'bold')).pack(side='left', padx=(0, 10))
        Label(legend_frame, text="* Critical (required)", bg="#fff3cd", font=('TkDefaultFont', 8)).pack(side='left', padx=5)
        Label(legend_frame, text="- Used in mapping", bg="#e7f3ff", font=('TkDefaultFont', 8)).pack(side='left', padx=5)
        Label(legend_frame, text="Optional", font=('TkDefaultFont', 8)).pack(side='left', padx=5)
        
        # Create scrollable frame
        canvas_frame = Frame(main_frame)
        canvas_frame.pack(fill="both", expand=True)
        
        self.canvas = Canvas(canvas_frame)
        scrollbar = Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create mapping table (will use loaded config if available)
        self.create_mapping_table()
        
        # Apply loaded configuration to UI widgets
        self.apply_loaded_config_to_ui()
        
        # Buttons
        button_frame = Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        self.finish_button = Button(button_frame, text="Finish & Continue", 
                                    command=self.finish_preprocessing)
        self.finish_button.pack(side="right", padx=5)
        
        self.cancel_button = Button(button_frame, text="Cancel", 
                                   command=lambda: master.destroy())
        self.cancel_button.pack(side="right", padx=5)
        
        self.preprocessed_dataframe = None
    
    def load_standard_fields(self):
        """Load all standard field names from settings.json and categorize by usage"""
        standard_fields = set()
        mapped_fields = set()  # Fields used in mapping (Entity, Event, Log, Rating, Object)
        
        try:
            if os.path.exists("settings.cjml.json"):
                with open("settings.cjml.json", "r", encoding='utf-8') as f:
                    settings = json.load(f)
                    # Get all field names from all categories
                    for category in ["Entity", "Event", "Log", "Rating", "Object"]:
                        if category in settings:
                            for field_def in settings[category]:
                                if "name" in field_def:
                                    field_name = field_def["name"]
                                    standard_fields.add(field_name)
                                    mapped_fields.add(field_name)
        except Exception as e:
            print(f"Warning: Could not load settings.json: {e}")
        
        # Critical fields that are hardcoded in the code (required for Neo4j generation)
        critical_fields = {
            "case:journey",  # Used extensively for journey relationships
            "Id",  # Used for event identification
            "channel",  # Used for communication nodes
            "initiatorsLabel", 
            "receiversLabel",
            "initiator",
            "receiverID",
            "initiatorID", 
            "case:LogID",  # Used in log metadata
            "case:enduser",  # Used to determine entity type
            "EventType",  # Used in subevent creation
            "receiver"  # Required for Receiver entity creation (can be mapped to customer or other)
        }
        
        # Add system fields that might not be in settings.json
        standard_fields.update(critical_fields)
        
        # Categorize fields by priority
        self.field_priority = {}
        for field in standard_fields:
            if field in critical_fields:
                self.field_priority[field] = 0  # Highest priority - critical
            elif field in mapped_fields:
                self.field_priority[field] = 1  # Medium priority - used in mapping
            else:
                self.field_priority[field] = 2  # Lower priority - optional
        
        # Sort fields: critical first, then mapped fields, then others
        sorted_fields = sorted(list(standard_fields), 
                               key=lambda x: (self.field_priority.get(x, 2), x))
        
        return sorted_fields
    
    def create_mapping_table(self):
        """Create the mapping table UI"""
        # Headers
        headers = ["Standard Field", "Map from CSV Column", "Static Value (fallback if column NULL)", 
                  "Auto-Generate (fallback if column NULL)", "Generation Type", "Skip Field"]
        
        for col, header in enumerate(headers):
            Label(self.scrollable_frame, text=header, font=('TkDefaultFont', 9, 'bold'),
                 relief="solid", borderwidth=1).grid(row=0, column=col, sticky='nsew', padx=2, pady=2)
        
        # Configure column weights
        for i in range(len(headers)):
            self.scrollable_frame.columnconfigure(i, weight=1)
        
        # Create rows for each standard field
        self.field_widgets = {}
        csv_options = [""] + self.csv_columns
        generation_types = ["", "Auto-increment (numeric)", "Auto-increment (ID1, ID2, ...)", 
                           "UUID", "Row number"]
        
        for row_idx, field_name in enumerate(self.standard_fields, start=1):
            widgets = {}
            
            # Standard field name with priority indicator
            priority = self.field_priority.get(field_name, 2)
            field_label_text = field_name
            if priority == 0:
                field_label_text = field_name + " *"  # Critical field indicator
            elif priority == 1:
                field_label_text = field_name + " -"  # Used in mapping indicator
            
            field_label = Label(self.scrollable_frame, text=field_label_text, anchor='w',
                 relief="solid", borderwidth=1)
            
            # Color code based on priority
            if priority == 0:
                field_label.config(bg="#fff3cd")  # Light yellow for critical
            elif priority == 1:
                field_label.config(bg="#e7f3ff")  # Light blue for mapped
            
            field_label.grid(row=row_idx, column=0, sticky='nsew', padx=2, pady=2)
            
            # CSV column mapping dropdown
            csv_combo = Combobox(self.scrollable_frame, state="readonly", 
                               values=csv_options, width=30)
            csv_combo.set("")
            csv_combo.grid(row=row_idx, column=1, sticky='nsew', padx=2, pady=2)
            csv_combo.bind('<<ComboboxSelected>>', 
                         lambda e, field=field_name: self.on_csv_selected(field))
            widgets['csv_combo'] = csv_combo
            
            # Static value entry (acts as fallback if CSV column selected)
            static_entry = Entry(self.scrollable_frame, width=20)
            static_entry.grid(row=row_idx, column=2, sticky='nsew', padx=2, pady=2)
            static_entry.bind('<KeyRelease>', 
                            lambda e, field=field_name: self.on_static_value_changed(field))
            widgets['static_entry'] = static_entry
            
            # Auto-generate checkbox (acts as fallback if CSV column selected)
            auto_var = IntVar()
            auto_check = Checkbutton(self.scrollable_frame, variable=auto_var,
                                   command=lambda field=field_name: self.on_auto_generate_toggled(field))
            auto_check.grid(row=row_idx, column=3, sticky='nsew', padx=2, pady=2)
            widgets['auto_check'] = auto_check
            widgets['auto_var'] = auto_var
            
            # Generation type dropdown
            gen_combo = Combobox(self.scrollable_frame, state="readonly",
                               values=generation_types, width=25)
            gen_combo.set("")
            gen_combo.grid(row=row_idx, column=4, sticky='nsew', padx=2, pady=2)
            gen_combo.bind('<<ComboboxSelected>>',
                         lambda e, field=field_name: self.on_generation_type_selected(field))
            widgets['gen_combo'] = gen_combo
            
            # Skip field checkbox (disabled for critical fields)
            skip_var = IntVar()
            skip_check = Checkbutton(self.scrollable_frame, variable=skip_var,
                                   command=lambda field=field_name: self.on_skip_toggled(field))
            # Disable skip checkbox for critical fields
            if priority == 0:  # Critical field
                skip_check.config(state='disabled')
            skip_check.grid(row=row_idx, column=5, sticky='nsew', padx=2, pady=2)
            widgets['skip_check'] = skip_check
            widgets['skip_var'] = skip_var
            
            self.field_widgets[field_name] = widgets
            
            # Try to auto-detect mapping based on field name (only if not already loaded from config)
            if field_name not in self.mappings:
                mapping_found = self.auto_detect_mapping(field_name, csv_combo)
            else:
                mapping_found = True  # Already mapped from saved config
            
            # Auto-skip non-required fields that aren't mapped (only if not loaded from config)
            if priority > 0:  # Not critical (priority 0)
                if field_name not in self.skip_fields and not mapping_found and field_name not in self.static_values and field_name not in self.auto_generate:
                    # No mapping found, auto-skip it
                    skip_var.set(1)
                    self.skip_fields.add(field_name)
        
        # Make rows expandable
        self.scrollable_frame.rowconfigure(0, weight=0)
        for i in range(1, len(self.standard_fields) + 1):
            self.scrollable_frame.rowconfigure(i, weight=0)
    
    def auto_detect_mapping(self, field_name, csv_combo):
        """Try to auto-detect CSV column mapping based on field name. Returns True if mapping found."""
        field_lower = field_name.lower().replace(":", "").replace("_", "").replace("-", "")
        field_base = field_name.split(":")[-1].lower()  # Remove case: prefix if present
        
        for csv_col in self.csv_columns:
            csv_lower = csv_col.lower().replace("*", "").replace(".", "").replace(":", "").replace("_", "").replace("-", "")
            
            # Direct match
            if field_lower == csv_lower or field_base == csv_lower:
                csv_combo.set(csv_col)
                self.mappings[field_name] = csv_col
                return True
            
            # Check if field name appears at the end of CSV column (common pattern)
            if csv_col.lower().endswith(field_lower) or csv_col.lower().endswith(field_base):
                csv_combo.set(csv_col)
                self.mappings[field_name] = csv_col
                return True
            
            # Check for properties pattern: *.properties.channel -> channel
            if "properties" in csv_col.lower():
                prop_parts = csv_col.split(".")
                if len(prop_parts) > 0:
                    last_part = prop_parts[-1].lower()
                    if last_part == field_lower or last_part == field_base:
                        csv_combo.set(csv_col)
                        self.mappings[field_name] = csv_col
                        return True
                    # Also check for partial matches like "sender" -> "initiator"
                    if "sender" in last_part and "initiator" in field_lower:
                        csv_combo.set(csv_col)
                        self.mappings[field_name] = csv_col
                        return True
        
        return False
    
    def on_csv_selected(self, field_name):
        """Handle CSV column selection - static value and auto-generate can now act as fallbacks"""
        widgets = self.field_widgets[field_name]
        selected = widgets['csv_combo'].get()
        
        if selected:
            self.mappings[field_name] = selected
            # Only clear skip field (static and auto-generate can stay as fallbacks)
            widgets['skip_var'].set(0)
            if field_name in self.skip_fields:
                self.skip_fields.remove(field_name)
        elif field_name in self.mappings:
            del self.mappings[field_name]
    
    def on_static_value_changed(self, field_name):
        """Handle static value entry - can act as fallback if CSV column selected"""
        widgets = self.field_widgets[field_name]
        value = widgets['static_entry'].get()
        
        if value:
            self.static_values[field_name] = value
            # If static value is set, it conflicts with auto-generate, so clear that
            # But CSV mapping can stay (static becomes fallback)
            widgets['auto_var'].set(0)
            widgets['gen_combo'].set("")
            widgets['skip_var'].set(0)
            if field_name in self.auto_generate:
                del self.auto_generate[field_name]
            if field_name in self.skip_fields:
                self.skip_fields.remove(field_name)
        elif field_name in self.static_values:
            del self.static_values[field_name]
    
    def on_auto_generate_toggled(self, field_name):
        """Handle auto-generate checkbox - can act as fallback if CSV column selected"""
        widgets = self.field_widgets[field_name]
        is_checked = widgets['auto_var'].get() == 1
        
        if is_checked:
            # If auto-generate is set, it conflicts with static value, so clear that
            # But CSV mapping can stay (auto-generate becomes fallback)
            widgets['static_entry'].delete(0, 'end')
            widgets['skip_var'].set(0)
            if field_name in self.static_values:
                del self.static_values[field_name]
            if field_name in self.skip_fields:
                self.skip_fields.remove(field_name)
        else:
            if field_name in self.auto_generate:
                del self.auto_generate[field_name]
            widgets['gen_combo'].set("")
    
    def on_generation_type_selected(self, field_name):
        """Handle generation type selection"""
        widgets = self.field_widgets[field_name]
        gen_type = widgets['gen_combo'].get()
        
        if gen_type:
            self.auto_generate[field_name] = gen_type
            # Ensure checkbox is checked
            widgets['auto_var'].set(1)
            # Clear skip if auto-generate is selected
            widgets['skip_var'].set(0)
            if field_name in self.skip_fields:
                self.skip_fields.remove(field_name)
        elif field_name in self.auto_generate:
            del self.auto_generate[field_name]
    
    def on_skip_toggled(self, field_name):
        """Handle skip checkbox toggle"""
        # Prevent skipping critical fields
        priority = self.field_priority.get(field_name, 2)
        if priority == 0:  # Critical field
            widgets = self.field_widgets[field_name]
            widgets['skip_var'].set(0)  # Force uncheck
            messagebox.showwarning("Cannot Skip Critical Field", 
                                 f"'{field_name}' is a critical field and cannot be skipped.\n\n"
                                 "Please provide a mapping, static value, or enable auto-generation.")
            return
        
        widgets = self.field_widgets[field_name]
        is_checked = widgets['skip_var'].get() == 1
        
        if is_checked:
            # Add to skip set and clear all other options
            self.skip_fields.add(field_name)
            widgets['csv_combo'].set("")
            widgets['static_entry'].delete(0, 'end')
            widgets['auto_var'].set(0)
            widgets['gen_combo'].set("")
            if field_name in self.mappings:
                del self.mappings[field_name]
            if field_name in self.static_values:
                del self.static_values[field_name]
            if field_name in self.auto_generate:
                del self.auto_generate[field_name]
        else:
            # Remove from skip set
            if field_name in self.skip_fields:
                self.skip_fields.remove(field_name)
    
    def finish_preprocessing(self):
        """Apply mappings and generate preprocessed dataframe"""
        print("[DEBUG] Starting preprocessing...")
        print(f"[DEBUG] Total fields to process: {len(self.standard_fields)}")
        print(f"[DEBUG] Mappings: {len(self.mappings)} fields mapped")
        print(f"[DEBUG] Static values: {len(self.static_values)} fields")
        print(f"[DEBUG] Auto-generated: {len(self.auto_generate)} fields")
        print(f"[DEBUG] Skipped fields: {len(self.skip_fields)} fields")
        
        # Validate critical fields are not skipped and are properly mapped
        critical_skipped = []
        critical_unmapped = []
        for field_name in self.standard_fields:
            priority = self.field_priority.get(field_name, 2)
            if priority == 0:  # Critical field
                # Check if field is skipped
                if field_name in self.skip_fields:
                    critical_skipped.append(field_name)
                # Check if field has no mapping, static value, or auto-generation
                elif field_name not in self.mappings and field_name not in self.static_values and field_name not in self.auto_generate:
                    critical_unmapped.append(field_name)
        
        if critical_skipped:
            error_msg = f"The following critical fields cannot be skipped:\n" + "\n".join(f"  - {f}" for f in critical_skipped)
            error_msg += "\n\nPlease uncheck 'Skip Field' and provide a mapping, static value, or enable auto-generation."
            messagebox.showerror("Critical Fields Skipped", error_msg)
            print(f"[ERROR] Critical fields skipped: {critical_skipped}")
            return
        
        if critical_unmapped:
            error_msg = f"The following critical fields must be mapped:\n" + "\n".join(f"  - {f}" for f in critical_unmapped)
            error_msg += "\n\nPlease map these fields to a CSV column, set a static value, or enable auto-generation before continuing."
            messagebox.showerror("Critical Fields Missing", error_msg)
            print(f"[ERROR] Critical fields unmapped: {critical_unmapped}")
            return
        
        # Validate CSV column mappings exist in dataframe
        invalid_mappings = []
        for standard_field, csv_column in self.mappings.items():
            if csv_column not in self.dataframe.columns:
                invalid_mappings.append(f"{standard_field} -> {csv_column}")
        
        if invalid_mappings:
            error_msg = f"The following CSV columns do not exist in the data:\n" + "\n".join(f"  - {m}" for m in invalid_mappings)
            error_msg += "\n\nPlease check your mappings."
            messagebox.showerror("Invalid Mapping", error_msg)
            print(f"[ERROR] Invalid CSV column mappings: {invalid_mappings}")
            return
        
        # Create a copy of the dataframe
        processed_df = self.dataframe.copy()
        print(f"[DEBUG] Original dataframe shape: {processed_df.shape}")
        
        # Filter out skipped fields from all operations
        # Group mappings by CSV column to handle one-to-many mappings (excluding skipped fields)
        csv_to_standards = {}
        for standard_field, csv_column in self.mappings.items():
            if standard_field not in self.skip_fields:
                if csv_column not in csv_to_standards:
                    csv_to_standards[csv_column] = []
                csv_to_standards[csv_column].append(standard_field)
        
        print(f"[DEBUG] CSV columns to map: {len(csv_to_standards)}")
        
        # Apply mappings: if one CSV column maps to one standard field, rename it
        # If one CSV column maps to multiple standard fields, copy the column to all standard field names
        column_rename_map = {}
        columns_to_copy = {}
        
        for csv_column, standard_fields in csv_to_standards.items():
            # Filter out skipped fields
            standard_fields = [f for f in standard_fields if f not in self.skip_fields]
            if not standard_fields:
                continue
                
            if csv_column in processed_df.columns:
                if len(standard_fields) == 1:
                    # One-to-one: rename the column
                    column_rename_map[csv_column] = standard_fields[0]
                else:
                    # One-to-many: copy the column to all standard field names
                    # Keep original column name and create copies
                    columns_to_copy[csv_column] = standard_fields
        
        # First, copy columns for one-to-many mappings (before renaming)
        print(f"[DEBUG] One-to-many mappings: {len(columns_to_copy)} columns")
        columns_to_remove_after_copy = []  # Track columns to remove after copying
        for csv_column, standard_fields in columns_to_copy.items():
            if csv_column in processed_df.columns:
                for standard_field in standard_fields:
                    if standard_field not in self.skip_fields:
                        processed_df[standard_field] = processed_df[csv_column].copy()
                        print(f"[DEBUG] Copied '{csv_column}' -> '{standard_field}'")
                # Mark original column for removal after copying
                columns_to_remove_after_copy.append(csv_column)
            else:
                print(f"[WARNING] CSV column '{csv_column}' not found in dataframe for one-to-many mapping")
        
        # Remove original columns after copying (for one-to-many mappings)
        if columns_to_remove_after_copy:
            print(f"[DEBUG] Removing original columns after copying: {columns_to_remove_after_copy}")
            processed_df.drop(columns=columns_to_remove_after_copy, inplace=True)
        
        # Then rename one-to-one mappings
        print(f"[DEBUG] One-to-one mappings: {len(column_rename_map)} columns")
        for old_name, new_name in column_rename_map.items():
            print(f"[DEBUG] Renaming '{old_name}' -> '{new_name}'")
        processed_df.rename(columns=column_rename_map, inplace=True)
        
        # Apply static values as fallbacks (where column mapping exists but value is NULL)
        # or as primary values (where no column mapping exists)
        print(f"[DEBUG] Processing {len(self.static_values)} static value fields")
        for standard_field, static_value in self.static_values.items():
            if standard_field not in self.skip_fields:
                if standard_field in self.mappings:
                    # Field has a CSV column mapping - use static as fallback for NULL values
                    if standard_field in processed_df.columns:
                        null_mask = processed_df[standard_field].isna() | (processed_df[standard_field] == "")
                        null_count = null_mask.sum()
                        if null_count > 0:
                            processed_df.loc[null_mask, standard_field] = static_value
                            print(f"[DEBUG] Filled {null_count} NULL values in '{standard_field}' with fallback static '{static_value}'")
                    else:
                        print(f"[WARNING] Mapped field '{standard_field}' not found in dataframe")
                else:
                    # No CSV column mapping - use static value for all rows
                    processed_df[standard_field] = static_value
                    print(f"[DEBUG] Set all rows of '{standard_field}' to static value '{static_value}'")
        
        # Apply auto-generated values as fallbacks (where column mapping exists but value is NULL)
        # or as primary values (where no column mapping exists)
        print(f"[DEBUG] Processing {len(self.auto_generate)} auto-generate fields")
        for standard_field, gen_type in self.auto_generate.items():
            if standard_field not in self.skip_fields:
                if standard_field in self.mappings:
                    # Field has a CSV column mapping - auto-generate only for NULL values
                    if standard_field in processed_df.columns:
                        null_mask = processed_df[standard_field].isna() | (processed_df[standard_field] == "")
                        null_count = null_mask.sum()
                        if null_count > 0:
                            # Generate values only for NULL rows
                            if gen_type == "Auto-increment (numeric)":
                                # Get current max value and increment from there
                                try:
                                    max_val = processed_df[standard_field].dropna().astype(int).max()
                                    start_val = int(max_val) + 1 if not pd.isna(max_val) else 1
                                except:
                                    start_val = 1
                                null_indices = processed_df[null_mask].index
                                processed_df.loc[null_mask, standard_field] = range(start_val, start_val + len(null_indices))
                                print(f"[DEBUG] Auto-generated numeric increment for {null_count} NULL values in '{standard_field}'")
                            elif gen_type == "Auto-increment (ID1, ID2, ...)":
                                # Get current max ID number and increment from there
                                try:
                                    existing_ids = processed_df[standard_field].dropna().astype(str)
                                    max_id = max([int(id.replace('ID', '')) for id in existing_ids if id.startswith('ID')])
                                    start_val = max_id + 1
                                except:
                                    start_val = 1
                                null_indices = processed_df[null_mask].index
                                processed_df.loc[null_mask, standard_field] = [f"ID{i}" for i in range(start_val, start_val + len(null_indices))]
                                print(f"[DEBUG] Auto-generated ID increment for {null_count} NULL values in '{standard_field}'")
                            elif gen_type == "UUID":
                                import uuid
                                processed_df.loc[null_mask, standard_field] = [str(uuid.uuid4()) for _ in range(null_count)]
                                print(f"[DEBUG] Auto-generated UUID for {null_count} NULL values in '{standard_field}'")
                            elif gen_type == "Row number":
                                processed_df.loc[null_mask, standard_field] = processed_df[null_mask].index + 1
                                print(f"[DEBUG] Auto-generated row numbers for {null_count} NULL values in '{standard_field}'")
                    else:
                        print(f"[WARNING] Mapped field '{standard_field}' not found in dataframe")
                else:
                    # No CSV column mapping - auto-generate for all rows
                    if gen_type == "Auto-increment (numeric)":
                        processed_df[standard_field] = range(1, len(processed_df) + 1)
                        print(f"[DEBUG] Auto-generated numeric increment for all rows in '{standard_field}'")
                    elif gen_type == "Auto-increment (ID1, ID2, ...)":
                        processed_df[standard_field] = [f"ID{i}" for i in range(1, len(processed_df) + 1)]
                        print(f"[DEBUG] Auto-generated ID increment for all rows in '{standard_field}'")
                    elif gen_type == "UUID":
                        import uuid
                        processed_df[standard_field] = [str(uuid.uuid4()) for _ in range(len(processed_df))]
                        print(f"[DEBUG] Auto-generated UUID for all rows in '{standard_field}'")
                    elif gen_type == "Row number":
                        processed_df[standard_field] = processed_df.index + 1
                        print(f"[DEBUG] Auto-generated row numbers for all rows in '{standard_field}'")
        
        # Remove skipped fields from the dataframe (if they exist)
        for field in self.skip_fields:
            if field in processed_df.columns:
                processed_df.drop(columns=[field], inplace=True)
        
        # Remove ALL remaining original CSV columns that weren't renamed
        # After renaming and copying, any remaining CSV column names should be removed
        # The dataframe should only contain standard field names at this point
        columns_to_remove = []
        for col in processed_df.columns:
            # If this column is an original CSV column name (not a standard field we created),
            # it should be removed because it wasn't mapped or was already handled
            if col in self.csv_columns:
                columns_to_remove.append(col)
                print(f"[DEBUG] Found unmapped CSV column '{col}' to remove")
        
        # Remove all remaining original CSV columns
        if columns_to_remove:
            print(f"[DEBUG] Removing {len(columns_to_remove)} remaining original CSV columns: {columns_to_remove}")
            processed_df.drop(columns=columns_to_remove, inplace=True)
        
        print(f"[DEBUG] Final dataframe shape: {processed_df.shape}")
        print(f"[DEBUG] Final columns: {list(processed_df.columns)}")
        print("[DEBUG] Preprocessing completed successfully")
        
        # Save configuration for next time
        self.save_preprocessing_config()
        
        self.preprocessed_dataframe = processed_df
        self.master.destroy()
    
    def get_preprocessed_dataframe(self):
        """Get the preprocessed dataframe"""
        return self.preprocessed_dataframe
    
    def save_preprocessing_config(self):
        """Save the current preprocessing configuration to a JSON file"""
        config = {
            "mappings": self.mappings,
            "static_values": self.static_values,
            "auto_generate": self.auto_generate,
            "skip_fields": list(self.skip_fields),
            "csv_columns": self.csv_columns  # Save for validation on load
        }
        
        try:
            with open("preprocessing_config.json", "w", encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print("[DEBUG] Preprocessing configuration saved to preprocessing_config.json")
        except Exception as e:
            print(f"[WARNING] Failed to save preprocessing configuration: {e}")
    
    def load_preprocessing_config(self):
        """Load saved preprocessing configuration from JSON file into data structures"""
        config_file = "preprocessing_config.json"
        
        if not os.path.exists(config_file):
            print("[DEBUG] No saved preprocessing configuration found")
            return
        
        try:
            with open(config_file, "r", encoding='utf-8') as f:
                config = json.load(f)
            
            # Validate that CSV columns match (warn if they don't)
            saved_csv_columns = set(config.get("csv_columns", []))
            current_csv_columns = set(self.csv_columns)
            
            if saved_csv_columns != current_csv_columns:
                print(f"[WARNING] CSV columns have changed. Saved: {saved_csv_columns}, Current: {current_csv_columns}")
                print("[WARNING] Some mappings may not apply correctly")
            
            # Load mappings (only if CSV column still exists)
            loaded_mappings = 0
            for standard_field, csv_column in config.get("mappings", {}).items():
                if standard_field in self.standard_fields:
                    if csv_column in self.csv_columns:
                        self.mappings[standard_field] = csv_column
                        loaded_mappings += 1
                    else:
                        print(f"[WARNING] Saved CSV column '{csv_column}' for '{standard_field}' not found in current data")
            
            # Load static values
            loaded_static = 0
            for standard_field, static_value in config.get("static_values", {}).items():
                if standard_field in self.standard_fields:
                    self.static_values[standard_field] = static_value
                    loaded_static += 1
            
            # Load auto-generate settings
            loaded_auto = 0
            for standard_field, gen_type in config.get("auto_generate", {}).items():
                if standard_field in self.standard_fields:
                    self.auto_generate[standard_field] = gen_type
                    loaded_auto += 1
            
            # Load skip fields
            loaded_skip = 0
            for standard_field in config.get("skip_fields", []):
                if standard_field in self.standard_fields:
                    self.skip_fields.add(standard_field)
                    loaded_skip += 1
            
            print(f"[DEBUG] Loaded preprocessing configuration: {loaded_mappings} mappings, {loaded_static} static values, {loaded_auto} auto-generated, {loaded_skip} skipped")
            
        except json.JSONDecodeError as e:
            print(f"[WARNING] preprocessing_config.json is not valid JSON: {e}")
        except Exception as e:
            print(f"[WARNING] Failed to load preprocessing configuration: {e}")
    
    def apply_loaded_config_to_ui(self):
        """Apply loaded configuration to UI widgets after table is created"""
        if not hasattr(self, 'field_widgets'):
            return
        
        applied_count = 0
        
        # Apply mappings to UI
        for standard_field, csv_column in self.mappings.items():
            if standard_field in self.field_widgets:
                self.field_widgets[standard_field]['csv_combo'].set(csv_column)
                applied_count += 1
        
        # Apply static values to UI
        for standard_field, static_value in self.static_values.items():
            if standard_field in self.field_widgets:
                self.field_widgets[standard_field]['static_entry'].delete(0, 'end')
                self.field_widgets[standard_field]['static_entry'].insert(0, static_value)
                applied_count += 1
        
        # Apply auto-generate settings to UI
        for standard_field, gen_type in self.auto_generate.items():
            if standard_field in self.field_widgets:
                self.field_widgets[standard_field]['auto_var'].set(1)
                self.field_widgets[standard_field]['gen_combo'].set(gen_type)
                applied_count += 1
        
        # Apply skip fields to UI
        for standard_field in self.skip_fields:
            if standard_field in self.field_widgets:
                self.field_widgets[standard_field]['skip_var'].set(1)
                applied_count += 1
        
        if applied_count > 0:
            print(f"[DEBUG] Applied {applied_count} configuration settings to UI")

