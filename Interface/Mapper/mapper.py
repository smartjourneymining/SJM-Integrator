
from tkinter import Button, Canvas, Checkbutton, Frame, IntVar, Label, Scrollbar, filedialog, messagebox, TclError
from tkinter.ttk import Combobox
from Class.map import field
from AutoMapper.autoMapper import check_field_belongs
from Class.log import log
from Class.event import touchpoint
from Class.objects import objects
# sort out scrolling
import json
import os


class Mapper:
    def __init__(self, master, mappingFor, fields):
        self.entryBox = []
        self.attributes = []
        self.attribute_owner = []
        self.attribute_identifier = []
        self.attribute_foreign_identifier = []
        self.attribute_foreign_owner = []
        self.attribute_actor_field = []

        self.master = master
        master.title("Field mapping: Input to CJML event knowledge graph" )
        master.columnconfigure(0, weight=1)
        master.columnconfigure(1, weight=1)
        master.rowconfigure(0, weight=1)
        self.label = Label(master, text="Fields")
        self.label.pack()
        self.frame = Frame(master, height=1500)
        self.frame.pack(side="top", fill="x")
        self.createTable(self.frame, fields)

        # Try to load settings.json, fall back to settings.cjml.json if it doesn't exist
        # This must be called after createTable so the UI elements exist
        self.loaded_settings = {}
        self.load_settings_if_exists()
        self.apply_loaded_settings()

        self.import_setings = Button(self.master,
                                     text="Import settings",
                                     command=lambda:
                                     self.import_setings_from_file(master))

        self.Finish = Button(self.master,
                             text="Finish",
                             command=lambda:
                             self.convert_inputs_to_object(master))
        self.Finish.pack()
        self.import_setings.pack()
        master.geometry("{}x{}".format(1000, 800))
        master.minsize(1000,800)
    
    def load_settings_if_exists(self):
        """Load settings from settings.json or settings.cjml.json if available"""
        settings_file = None
        if os.path.exists("settings.json"):
            settings_file = "settings.json"
            print("[DEBUG] Loading settings from settings.json")
        elif os.path.exists("settings.cjml.json"):
            settings_file = "settings.cjml.json"
            print("[DEBUG] Loading settings from settings.cjml.json (settings.json not found)")
        
        if settings_file:
            try:
                with open(settings_file, "r", encoding='utf-8') as f:
                    json_parse = json.load(f)
                
                # Convert to the format expected by the mapper
                # Map "Entity" -> "Actor" for compatibility
                if "Entity" in json_parse:
                    json_parse["Actor"] = json_parse["Entity"]
                
                # Store all settings in a dictionary keyed by field name for easy lookup
                self.loaded_settings = {}
                for category in ["Actor", "Event", "Log", "Rating", "Object"]:
                    if category in json_parse:
                        for field_def in json_parse[category]:
                            if "name" in field_def:
                                field_name = field_def["name"]
                                self.loaded_settings[field_name] = {
                                    "type_map": field_def.get("type_map", ""),
                                    "identifier": field_def.get("identifier", 0),
                                    "foreign_key": field_def.get("foreign_key", 0),
                                    "to_type": field_def.get("to_type", ""),
                                    "entity_type": field_def.get("entity_type", "Field belongs")
                                }
                
                print(f"[DEBUG] Loaded {len(json_parse.get('Actor', []))} Actor fields, "
                      f"{len(json_parse.get('Event', []))} Event fields, "
                      f"{len(json_parse.get('Log', []))} Log fields")
                print(f"[DEBUG] Total fields loaded: {len(self.loaded_settings)}")
            except Exception as e:
                print(f"[WARNING] Could not load settings from {settings_file}: {e}")
                self.loaded_settings = {}
    
    def apply_loaded_settings(self):
        """Apply loaded settings to the UI elements"""
        if not self.loaded_settings:
            return
        
        applied_count = 0
        for i in range(len(self.attributes)):
            field_name = self.attributes[i].cget("text")
            
            if field_name in self.loaded_settings:
                settings = self.loaded_settings[field_name]
                applied_count += 1
                
                # Apply type_map (Field belongs)
                type_map = settings.get("type_map", "")
                if type_map and type_map in ["Entity", "Event", "Log", "Rating", "Object"]:
                    try:
                        values = ["", "Entity", "Event", "Log", "Rating", "Object"]
                        if type_map in values:
                            index = values.index(type_map)
                            self.attribute_owner[i].current(index)
                    except (ValueError, IndexError) as e:
                        print(f"[WARNING] Could not set type_map '{type_map}' for field '{field_name}': {e}")
                
                # Apply identifier
                identifier = settings.get("identifier", 0)
                self.attribute_identifier[i].set(1 if identifier else 0)
                
                # Apply foreign_key
                foreign_key = settings.get("foreign_key", 0)
                self.attribute_foreign_identifier[i].set(1 if foreign_key else 0)
                
                # Trigger foreign key dropdown visibility update
                if foreign_key:
                    self.enableForeigKeyDropDown(i)
                
                # Apply to_type (Key relates to) - only if foreign_key is set
                to_type = settings.get("to_type", "")
                if foreign_key and to_type:
                    try:
                        values = ["", "Entity", "Event", "Log", "Rating", "Object"]
                        if to_type in values:
                            index = values.index(to_type)
                            self.attribute_foreign_owner[i].current(index)
                    except (ValueError, IndexError) as e:
                        print(f"[WARNING] Could not set to_type '{to_type}' for field '{field_name}': {e}")
                
                # Apply entity_type (Relates to type of actor) - only if type_map is Entity or to_type is Entity
                entity_type = settings.get("entity_type", "Field belongs")
                if entity_type != "Field belongs" and entity_type in ["Sender", "Receiver", "Both"]:
                    if type_map == "Entity" or (foreign_key and to_type == "Entity"):
                        try:
                            # The combobox values are ["Sender", "Receiver", "Both"] (no "Field belongs")
                            # Get the actual values from the combobox to ensure we use the correct list
                            combobox_values = list(self.attribute_actor_field[i]["values"])
                            if entity_type in combobox_values:
                                index = combobox_values.index(entity_type)
                                self.attribute_actor_field[i].current(index)
                            else:
                                print(f"[WARNING] entity_type '{entity_type}' not found in combobox values: {combobox_values}")
                        except (ValueError, IndexError, TclError) as e:
                            print(f"[WARNING] Could not set entity_type '{entity_type}' for field '{field_name}': {e}")
                
                # Trigger actor field dropdown visibility update
                self.enable_receiver_sender_dropdown(
                    self.attribute_owner[i],
                    self.attribute_foreign_owner[i],
                    self.attribute_actor_field[i]
                )
                
                print(f"[DEBUG] Applied settings for field '{field_name}': type_map={type_map}, identifier={identifier}, foreign_key={foreign_key}, to_type={settings.get('to_type', '')}, entity_type={entity_type}")
        
        print(f"[DEBUG] Applied settings to {applied_count} fields out of {len(self.attributes)} total fields")

    def import_setings_from_file(self, master):
        self.fileToRead = filedialog.askopenfilename(initialdir=os.getcwd(),
                                                     title="Select file",
                                                     filetypes=[("Json", '*.json'),
                                                                ("All files", "*.*")])

        if self.fileToRead != "":
            with open(self.fileToRead, "r") as outfile:
                file_content = outfile.read()
            json_parse = json.loads(file_content)
            self.converted = {}
            # Handle both "Actor" and "Entity" keys for compatibility
            entity_key = "Entity" if "Entity" in json_parse else "Actor"
            actor = [field(**e) for e in json_parse[entity_key]]
            event = [field(**e) for e in json_parse["Event"]]
            logs = [field(**e) for e in json_parse["Log"]]
            rating = [field(**e) for e in json_parse["Rating"]]
            objFields = [field(**e) for e in json_parse["Object"]]

            self.actor = touchpoint(actor)
            self.event = touchpoint(event)
            self.logs = log(logs)
            self.rating = touchpoint(rating)
            self.objects = objects(objFields)
        master.destroy()

    def create_labels(self, select_frame):
        Label(select_frame, text="Field name").grid(row=0,
                                                    column=0,
                                                    sticky='nsew',
                                                    padx=20)

        Label(select_frame, text="Property of").grid(row=0,
                                                     column=1,
                                                     sticky='nsew',
                                                     padx=20)

        Label(select_frame, text="Identifier").grid(row=0,
                                                    column=2,
                                                    sticky='we',
                                                    padx=20)

        Label(select_frame, text="Foreign key").grid(row=0,
                                                     column=3,
                                                     sticky='we',
                                                     padx=20)

        Label(select_frame, text="Key relates to").grid(row=0,
                                                        column=4,
                                                        sticky='we',
                                                        padx=20)

        Label(select_frame, text="Relates to type of actor").grid(row=0,
                                                                  column=5,
                                                                  sticky='we',
                                                                  padx=20)

    def create_dropdown(self, select_frame, text, column, rowVisualization, setValue=""):
        values = ["",
                  "Entity",
                  "Event",
                  "Log",
                  "Rating",
                  "Object"]

        dropDown = Combobox(select_frame,  state="readonly", values=values)
        print("ID: "+str(values.index(setValue)))

        dropDown.set(text)
        dropDown.current(values.index(setValue))
        dropDown.grid(row=rowVisualization, column=column, padx=20)
        dropDown.grid_remove()
        return dropDown

    def create_checkbutton(self, select_frame, text, column, row, checked):
        c_v1 = IntVar()
        c_v1.set(1 if checked else 0)
        ChkBttn = Checkbutton(select_frame,
                              text=text,
                              variable=c_v1,
                              onvalue=1,
                              offvalue=0)

        ChkBttn.grid(row=row, column=column, padx=20)
        return ChkBttn, c_v1

    def create_sorting_fame(self, select_frame, fields):
        row = 1
        for line in fields:
            field_type, identifier, foreign_key = check_field_belongs(line)
            text = Label(select_frame, text=line)
            text.grid(row=row, column=0, padx=20)
            self.attributes.append(text)

            dropDown = self.create_dropdown(select_frame,
                                            "Field belongs",
                                            1,
                                            row,
                                            field_type)
            dropDown.grid()
            self.attribute_owner.append(dropDown)

            bttn, c_v1 = self.create_checkbutton(select_frame,
                                                 "Identifier",
                                                 2,
                                                 row,
                                                 identifier)
            self.attribute_identifier.append(c_v1)

            dropDown2 = self.create_dropdown(select_frame,
                                             "Field belongs",
                                             4,
                                             row)
            self.attribute_foreign_owner.append(dropDown2)

            bttn2, c_v2 = self.create_checkbutton(select_frame,
                                                  "Foreign key",
                                                  3,
                                                  row,
                                                  foreign_key)

            bttn2.configure(command=lambda id=row:
                            self.enableForeigKeyDropDown(id-1))

            self.attribute_foreign_identifier.append(c_v2)

            actorTypefield = Combobox(select_frame,
                                      state="readonly",
                                      values=["Sender",
                                              "Receiver",
                                              "Both"])

            actorTypefield.set("Field belongs")
            actorTypefield.grid(row=row, column=5, padx=20)
            actorTypefield.grid_remove()
            self.attribute_actor_field.append(actorTypefield)

            dropDown2.bind('<<ComboboxSelected>>',
                           lambda event, entry=dropDown,
                           entry2=dropDown2, actor=actorTypefield:
                           self.enable_receiver_sender_dropdown(entry,
                                                                entry2,
                                                                actor))

            dropDown.bind('<<ComboboxSelected>>',
                          lambda event, entry=dropDown,
                          entry2=dropDown2, actor=actorTypefield:
                          self.enable_receiver_sender_dropdown(entry,
                                                               entry2,
                                                               actor))

            row = row + 1

    def createTable(self, master, fields):
        row = 1
        frame = Frame(master, height=1500)
        frame.pack(side="top", fill="x")
        frame.columnconfigure(0, weight="1")
        frame.rowconfigure(0, weight="1")
        frame.rowconfigure(1, minsize="700")

        self.canvas = Canvas(frame)
        select_frame = Frame(master)
        self.canvas.grid(row=1, columnspan=6, rowspan=10, sticky='nswe')
        self.canvas.create_window((0, 0), window=select_frame,  anchor='nw')

        select_frame.config()
        self.create_labels(select_frame)
        self.create_sorting_fame(select_frame, fields)

        sbb = Scrollbar(frame,  orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sbb.set)
        select_frame.bind("<Configure>", self.onFrameConfigure)
        sbb.grid(row=1, column=6, rowspan=row, sticky="nsew")

    def onFrameConfigure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def enable_receiver_sender_dropdown(self, row, entry2, actor):
        if (not actor.winfo_ismapped()) and (row.get() == "Entity"
                                             or entry2.get() == "Entity"):
            actor.grid()
        elif actor.winfo_ismapped() and not (row.get() == "Entity"
                                             or entry2.get() == "Entity"):
            actor.grid_remove()

    def enableForeigKeyDropDown(self, row):
        if not self.attribute_foreign_owner[row].winfo_ismapped():
            self.attribute_foreign_owner[row].grid()
        else:
            self.attribute_foreign_owner[row].grid_remove()

    def convert_inputs_to_object(self, master):
        print("[DEBUG] Starting conversion of inputs to objects...")
        self.converted = {}
        self.converted["Entity"] = []
        self.converted["Event"] = []
        self.converted["Log"] = []
        self.converted["Rating"] = []
        self.converted["Object"] = []

        mapped_count = 0
        for i in range(0, len(self.attributes)):
            place = self.attribute_owner[i].get()
            if place != "":
                field_name = self.attributes[i].cget("text")
                
                # Validate field name
                if not field_name or field_name.strip() == "":
                    print(f"[WARNING] Empty field name at index {i}, skipping")
                    continue
                
                # Get field properties
                identifier = self.attribute_identifier[i].get()
                foreign_key = self.attribute_foreign_identifier[i].get()
                foreign_owner = self.attribute_foreign_owner[i].get()
                actor_field = self.attribute_actor_field[i].get()
                
                # Validate foreign key relationship
                if foreign_key and (not foreign_owner or foreign_owner == ""):
                    error_msg = f"Field '{field_name}' is marked as a foreign key but no 'Key relates to' is specified.\n\nPlease select a target type for the foreign key relationship."
                    messagebox.showerror("Invalid Mapping", error_msg)
                    print(f"[ERROR] Invalid foreign key mapping for '{field_name}'")
                    return
                
                # Validate actor field for Entity type
                if place == "Entity" and (not actor_field or actor_field == "Field belongs"):
                    error_msg = f"Field '{field_name}' is mapped to Entity but no actor type (Sender/Receiver/Both) is specified.\n\nPlease select an actor type."
                    messagebox.showerror("Invalid Mapping", error_msg)
                    print(f"[ERROR] Missing actor type for Entity field '{field_name}'")
                    return
                
                try:
                    mapping = field(field_name,
                                    place,
                                    identifier,
                                    foreign_key,
                                    foreign_owner,
                                    actor_field)
                    
                    if place == "Log":
                        self.converted[place].append(log([mapping]))
                    else:
                        self.converted[place].append(touchpoint([mapping]))
                    
                    mapped_count += 1
                    print(f"[DEBUG] Mapped '{field_name}' to {place} (identifier={identifier}, foreign_key={foreign_key})")
                except Exception as e:
                    error_msg = f"Error creating mapping for field '{field_name}': {str(e)}"
                    messagebox.showerror("Mapping Error", error_msg)
                    print(f"[ERROR] Failed to create mapping for '{field_name}': {e}")
                    return

        print(f"[DEBUG] Total fields mapped: {mapped_count}")
        print(f"[DEBUG] Entity fields: {len(self.converted['Entity'])}")
        print(f"[DEBUG] Event fields: {len(self.converted['Event'])}")
        print(f"[DEBUG] Log fields: {len(self.converted['Log'])}")
        print(f"[DEBUG] Rating fields: {len(self.converted['Rating'])}")
        print(f"[DEBUG] Object fields: {len(self.converted['Object'])}")
        
        # Validate that we have at least some mappings
        total_mappings = sum(len(self.converted[key]) for key in self.converted)
        if total_mappings == 0:
            error_msg = "No fields were mapped. Please map at least one field before continuing."
            messagebox.showerror("Invalid Mapping", error_msg)
            print("[ERROR] No fields mapped")
            return

        # Extract field objects from log/touchpoint objects and convert to dictionaries
        print("[DEBUG] Converting to JSON structure...")
        try:
            structure = {
                'Actor': [field_obj.__dict__ for elem in self.converted["Entity"] for field_obj in elem.dataFields],
                'Event': [field_obj.__dict__ for elem in self.converted["Event"] for field_obj in elem.dataFields],
                'Log': [field_obj.__dict__ for elem in self.converted["Log"] for field_obj in elem.dataFields],
                'Rating': [field_obj.__dict__ for elem in self.converted["Rating"] for field_obj in elem.dataFields],
                'Object': [field_obj.__dict__ for elem in self.converted["Object"] for field_obj in elem.dataFields]
            }
            
            print(f"[DEBUG] JSON structure created: {len(structure['Actor'])} Actor, {len(structure['Event'])} Event, {len(structure['Log'])} Log, {len(structure['Rating'])} Rating, {len(structure['Object'])} Object")
            
            # Save to settings.json
            # Note: settings.cjml.json is read-only and only used as a reference for column mapping
            with open("settings.json", "w", encoding='utf-8') as outfile:
                json.dump(structure, outfile, indent=4, ensure_ascii=False)
            
            print("[DEBUG] Settings saved to settings.json successfully")
            
            # Create the actor, event, logs, objects, and rating attributes from converted data
            # Extract field objects from the converted structure
            actor_fields = []
            for elem in self.converted["Entity"]:
                actor_fields.extend(elem.dataFields)
            
            event_fields = []
            for elem in self.converted["Event"]:
                event_fields.extend(elem.dataFields)
            
            log_fields = []
            for elem in self.converted["Log"]:
                log_fields.extend(elem.dataFields)
            
            rating_fields = []
            for elem in self.converted["Rating"]:
                rating_fields.extend(elem.dataFields)
            
            object_fields = []
            for elem in self.converted["Object"]:
                object_fields.extend(elem.dataFields)
            
            # Create the objects as expected by start.py
            self.actor = touchpoint(actor_fields)
            self.event = touchpoint(event_fields)
            self.logs = log(log_fields)
            self.rating = touchpoint(rating_fields)
            self.objects = objects(object_fields)
            
            print(f"[DEBUG] Created mapper attributes: actor={len(actor_fields)} fields, event={len(event_fields)} fields, logs={len(log_fields)} fields, rating={len(rating_fields)} fields, objects={len(object_fields)} fields")
            
        except Exception as e:
            error_msg = f"Error saving settings.json: {str(e)}"
            messagebox.showerror("Save Error", error_msg)
            print(f"[ERROR] Failed to save settings.json: {e}")
            return
        
        master.destroy()
