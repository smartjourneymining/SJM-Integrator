from tkinter import messagebox
from Interface.Connection.ConnectionUI import ConnectionUI
from Interface.FileUpload.FileUploadUI import FileUploadUI
from Interface.Preprocessor.PreprocessorUI import PreprocessorUI
from Interface.Mapper.mapper import Mapper
from Interface.TimeSelector.TimeSelector import TimeSelector
import Xes
import xmlschema
import tkinter as tk
import pm4py
import pandas as pd
import time
import numpy as np
import os
from Functions.StringManipulation import get_value_To_string, check_if_string_is_not_None, remove_case_append
from Class.log import log
from Class.objects import objects
import re


filesXes = Xes.Xes()
status = ""
fileToRead = ""
counter = 0


def create_log(connector, logs, mapping, session,
               file_name, time_stamp, rating):
    connector.create_journey(mapping.get_field_string(logs), session)
    connector.create_log(file_name, time_stamp, session)

    log_where = mapping.get_field_string(logs)

    connector.associate_log_with_journey(session, log_where,
                                         file_name, time_stamp)

    if (rating.getLength() > 0 and rating.mapping_values_are_defined(
                                                              logs
                                                              ) > 0):
        logInfo = mapping.filter_out_mapping_start_with("case:")
        journey_data = logInfo.get_field_string(logs)
        case_mapping = rating.filter_out_mapping_start_with("case:")
        values = case_mapping.get_range_field_string(logs)
        if values != '':
            connector.associate_experience_with_journey(session,
                                                        journey_data,
                                                        values)


def append_log_metadata(string_of_values, log):
    return string_of_values + f''', journey: "{log["case:journey"]}"
                                    , LogID: "{log["case:LogID"]}"'''


def create_subevent(connector, log, mapping, field, session):
    # Include all primary keys from Event mapping to ensure proper matching with Touchpoints
    primary_keys = mapping.get_primary_keys()
    primary_key_string = ""
    if primary_keys.getLength() > 0:
        primary_key_string = ", " + primary_keys.get_field_string(log)
    
    # Also include Entity-related fields (foreign_key == 1, to_type == "Entity") 
    # These are needed for Corr relationship matching
    entity_fields_string = ""
    for m in mapping:
        if m.foreign_key and m.to_type == "Entity":
            if m.name in log and not pd.isna(log[m.name]) and log[m.name] != "":
                if entity_fields_string:
                    entity_fields_string += ", "
                entity_fields_string += f'''{remove_case_append(m.name)}:{get_value_To_string(log[m.name])}'''
    
    if entity_fields_string:
        entity_fields_string = ", " + entity_fields_string
    
    node = f'''TimeStampType:"{field}", TimeStamp:"{log[field]}", Id:"{log["Id"]}"
                                    , journey:"{log["case:journey"]}", Label:"{log["EventType"]}"{primary_key_string}{entity_fields_string}'''
    connector.create_subevent(node, session)


def get_fields_from_list(log, mapping, session, connector):
    listSize = len(log[mapping["Object"][0].name]['children'])
    for index_array in range(0, listSize):
        log_insert = ""
        first_value = False
        primary_from_touchpoint = get_primary_keys(mapping, "Event")
        for index, fields in enumerate(mapping["Object"]):
            insertValue = get_value_To_string(log[fields.name]['children'][index_array][1])

            if check_if_string_is_not_None(insertValue):
                if first_value:
                    log_insert = log_insert + ","
                log_insert = log_insert + f'''{remove_case_append(fields.name)}:{insertValue}'''
                first_value = True
        connector.associate_object_with_touchpoint(session,
                                                   get_field_string(log, primary_from_touchpoint),
                                                   log_insert)


def create_entities(connector, log, mapping, session, timestampNames, rating, journey, objects):
    is_planned = False
    try:
        if np.isnan(log['case:isPlanned']):
            is_planned = False
        else:
            is_planned = log['case:isPlanned']
    except: 
        is_planned = False
    
    # Create Event nodes for each timestamp field
    event_created = False
    for field in timestampNames:
        if field in log:
            if not (pd.isnull(log[field])) and not (is_planned):
                create_subevent(connector, log, mapping, field, session)
                event_created = True
    
    # If no timestamp fields, create a main Event node without timestamp
    if not event_created and not is_planned:
        primary_keys = mapping.get_primary_keys()
        primary_key_string = ""
        if primary_keys.getLength() > 0:
            primary_key_string = ", " + primary_keys.get_field_string(log)
        
        # Also include Entity-related fields (foreign_key == 1, to_type == "Entity") 
        # These are needed for Corr relationship matching
        entity_fields_string = ""
        for m in mapping:
            if hasattr(m, 'foreign_key') and m.foreign_key == 1 and hasattr(m, 'to_type') and m.to_type == "Entity":
                if m.name in log and not pd.isna(log[m.name]) and log[m.name] != "":
                    if entity_fields_string:
                        entity_fields_string += ", "
                    entity_fields_string += f'''{remove_case_append(m.name)}:{get_value_To_string(log[m.name])}'''
        
        if entity_fields_string:
            entity_fields_string = ", " + entity_fields_string
        
        event_node = f'''Id:"{log["Id"]}", journey:"{log["case:journey"]}", Label:"{log["EventType"]}"{primary_key_string}{entity_fields_string}'''
        connector.create_subevent(event_node, session)

    # Create Touchpoint if initiatorsLabel exists and has a value
    if 'initiatorsLabel' in log and not pd.isna(log.get('initiatorsLabel')) and log.get('initiatorsLabel') != "":
        # Pass primary keys, journey, and log to create_class to enable MERGE and prevent duplicates
        primary_keys = mapping.get_primary_keys()
        connector.create_class(append_log_metadata(
            mapping.get_field_string(log),
            log), session, is_planned, primary_keys, log["case:journey"], log)

    # Use primary keys from Event mapping to match Events to Touchpoints
    primary_keys = mapping.get_primary_keys()
    connector.create_class_event_relationship(
        log, primary_keys, log["case:journey"], session)

    if(not(pd.isna(log["channel"]))):
        connector.create_communication_node(session, log["channel"])

    primary_from_touchpoint = mapping.get_primary_keys()

    if(not(pd.isna(log["channel"]))):
        connector.associate_touchpoint_and_communication(log["channel"],
                                                     primary_from_touchpoint.get_field_string(log) + ', journey: "'+ log["case:journey"] + '"', session)

    if is_planned:
        connector.create_planned_touchpoint_connection(session, log["case:journey"])

    if (objects.getLength() > 0 and objects.mapping_values_are_defined(log)
            < objects.getLength()):
        values, index = objects.get_field_string(log)
        connector.associate_object_with_touchpoint(session,
                                                   primary_from_touchpoint.get_field_string(log),
                                                   values)

    if (rating.getLength() > 0 and rating.mapping_values_are_defined(
                                                                 log
                                                                 ) < rating.getLength()):
        primary_from_touchpoint = mapping.get_primary_keys()
        case_mapping = rating.filter_out_mapping_notstart_with("case:")
        values = case_mapping.get_range_field_string(log)
        if values != '':
            connector.associate_experience_with_touchpoint(session,
                                                           primary_from_touchpoint.get_field_string(log),
                                                           f'''journey:"{log["case:journey"]}"''',
                                                           values)
            connector.associate_experience_with_event(session,
                                                      primary_from_touchpoint.get_field_string(log),
                                                      f'''journey:"{log["case:journey"]}"''',
                                                      values)


def get_array_idefiying_fields(mapping, from_type, to_type,
                               type_of_connection, event):
    fields_to_map = []

    if (mapping.check_if_array_has_identifier()):
        fields_to_map = [m for m in event if m.to_type == to_type
                         and m.foreign_key == 1
                         and (m.entity_type == type_of_connection
                              or m.entity_type == "Both")]

    else:
        fields_to_map = [m for m in mapping if m.identifier == 1
                         and (m.entity_type == type_of_connection
                              or m.entity_type == "Both")]

    return fields_to_map


def construct_where_clause(fields_to_map, fields_from_map):
    query = ""
    if not fields_to_map or not fields_from_map:
        print(f"    [WARN] Empty field mapping in WHERE clause construction")
        return query
    
    for indexi, i in enumerate(fields_to_map):
        for index, j in enumerate(fields_from_map):
            query = query + "e." + i.name.replace("case:", "") \
                + "= en." + j.name.replace("case:", "")

            if index != len(fields_from_map) - 1:
                query = query + " OR "

        if indexi != len(fields_to_map) - 1:
            query = query + " OR "

    return query


def get_where_clause_to_match_other_node(
        mapping,
        from_type, to_type,
        type_of_connection,
        log,
        event):
    query = ""

    fields_to_map = get_array_idefiying_fields(mapping, from_type,
                                               to_type, type_of_connection, event)

    fields_from_map = get_array_idefiying_fields(mapping, from_type,
                                                 to_type, type_of_connection, event)

    query = construct_where_clause(fields_to_map, fields_from_map)
    return query


def get_where_clause_to_find_node(log, mapping, node_type):
    query = ""    
    fields = [m for m in mapping if m.identifier == 1]
    
    if not fields:
        return query
    
    for index, i in enumerate(fields):
        # Check if field exists in log and has a value
        if i.name in log and not pd.isna(log[i.name]) and log[i.name] != "":
            if query:  # Add AND if not first field
                query = query + " AND "
            query = query + "e." + i.name \
                     + " = " \
                     + get_value_To_string(log[i.name])
    
    return query


def get_query_using_array(array, log, entity_type, equal_sign=False):
    insert = ""
    alias = "e." if equal_sign else ""
    sign = "=" if equal_sign else ":"

    fields = [m for m in array if m.entity_type == entity_type
              or m.entity_type == "Both"]

    for index, i in enumerate(fields):
        if check_if_string_is_not_None(log[i.name]):
            insert = insert + alias + i.name \
                     + sign \
                     + get_value_To_string(log[i.name])

            if index != len(fields) - 1:
                insert = insert + ", "

    return insert


def get_other_type_keys(mapping, log, current_entity_type,
                        previous_entity_type, event, equal_sign=False):
    mock_other_type_keys = ""
    alias = "e." if equal_sign else ""
    sign = "=" if equal_sign else ":"

    if (mapping.check_if_array_has_identifier()):
        insert_elements = [m for m in event if m.to_type == "Entity"]
        # Include fields with entity_type == "Both" in both lists
        keys = [m for m in insert_elements
                if m.entity_type == previous_entity_type or m.entity_type == "Both"]
        values = [m for m in insert_elements
                  if m.entity_type == current_entity_type or m.entity_type == "Both"]

        # Validate that we have matching pairs
        if len(keys) != len(values):
            print(f"    [WARN] Mismatch: {len(keys)} {previous_entity_type} keys vs {len(values)} {current_entity_type} values")
            print(f"           Keys: {', '.join([k.name for k in keys])}")
            print(f"           Values: {', '.join([v.name for v in values])}")
            # Only process up to the minimum length to avoid IndexError
            min_length = min(len(keys), len(values))
            if min_length == 0:
                return mock_other_type_keys
        else:
            min_length = len(keys)

        for index in range(min_length):
            key_field = keys[index]
            value_field = values[index]
            
            # Check if the value field exists in log and has a value
            if value_field.name not in log or pd.isna(log[value_field.name]) or log[value_field.name] == "":
                continue
            
            if mock_other_type_keys:  # Add comma if not first field
                mock_other_type_keys = mock_other_type_keys + ","
            
            mock_other_type_keys = mock_other_type_keys + alias + key_field.name \
                                   + sign \
                                   + f'''\'{log[value_field.name]}\''''

    return mock_other_type_keys


def check_if_node_exists(connector, query, session):
    return connector.check_node_existance(query, session)


def get_actor_insert_value_str(log, mapping,
                               event, entity_type,
                               connnector, session):
    insert = ""
    user_type = ""
    insert_elements = None

    if (mapping.check_if_array_has_identifier()):
        insert_elements = [m for m in event if m.to_type == "Entity"]
        
        # Validate that we have identifier fields for this entity type
        entity_fields = [m for m in insert_elements 
                        if m.entity_type == entity_type or m.entity_type == "Both"]
        if not entity_fields:
            print(f"    [WARN] No {entity_type} identifier fields in Event mapping")
        
        insert = get_query_using_array(insert_elements, log, entity_type)

    node_exists = check_if_node_exists(connnector, insert, session)
    sign = "=" if node_exists else ":"

    if node_exists and insert_elements is not None:
        insert = get_query_using_array(insert_elements, log, entity_type, True)
    if len(insert) > 0 and mapping.getLength() > 0:
        insert = insert + ", "

    user_to_pick = "initiator" if entity_type == "Sender" else "receiver"

    insert = insert + get_query_using_array(mapping,
                                            log,
                                            entity_type,
                                            node_exists)
    entity_type_alternative = "Receiver" if entity_type == 'Sender' else "Sender"

    mock_values = get_other_type_keys(mapping,
                                      log,
                                      entity_type,
                                      entity_type_alternative,
                                      event,
                                      node_exists)
    

    if not node_exists:
        # Validate that user_to_pick field exists in log
        if user_to_pick not in log or pd.isna(log[user_to_pick]):
            print(f"    [ERROR] Missing '{user_to_pick}' field - cannot create {entity_type} entity")
            return "", False
        
        regexMatch = re.search("[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}", log[user_to_pick])
        user_type = user_type \
                    + "EntityType"\
                    + sign\
                    + '"End user"' if log["case:enduser"] == log[user_to_pick] or regexMatch is not None \
                    else "EntityType"+sign+'"Service Provider"'

        insert = insert + "," + user_type

    # Only add mock_values if it's not empty
    if mock_values and mock_values.strip():
        # Handle leading comma if insert already has content
        if insert and insert.strip():
            insert = insert + "," + mock_values
        else:
            insert = mock_values
    
    # Clean up trailing/leading commas and whitespace
    insert = insert.strip().strip(',').strip()
    
    return insert, node_exists


def get_actors_Identifier(log, mapping, entity_type, event):
    reuquest = ""
    if (mapping.check_if_array_has_identifier()):
        insert_elements = [m for m in event if m.to_type == "Entity"]
        fields = [m for m in insert_elements if (m.entity_type == entity_type
                  or m.entity_type == "Both")
                  and m.to_type == "Entity"]

        # Validate that we have identifier fields for this entity type
        if not fields:
            print(f"    [WARN] No {entity_type} identifier fields configured")

        for index, f in enumerate(fields):
            # Check if field value is not null/NaN before adding to query
            if f.name in log and not pd.isna(log[f.name]) and log[f.name] != "":
                if reuquest:  # Add comma if not first field
                    reuquest = reuquest + ","
                reuquest = reuquest + f.name + ":'" + str(log[f.name]) +"'"
            elif f.name not in log:
                print(f"    [WARN] Field '{f.name}' not in log data (entity_type={entity_type})")
            elif pd.isna(log[f.name]) or log[f.name] == "":
                print(f"    [WARN] Field '{f.name}' is empty (entity_type={entity_type})")
    
    if not reuquest or reuquest.strip() == "":
        print(f"    [WARN] No identifier values found for {entity_type} entity")
    
    return reuquest


def create_actors(connector, log, mapping, session, event):
    global counter
    insert, node_exists = get_actor_insert_value_str(log,
                                                     mapping,
                                                     event,
                                                     "Sender",
                                                     connector,
                                                     session)

    where_clause = get_actors_Identifier(log, mapping, "Sender", event)
    connector.create_entity(insert, node_exists, session, where_clause)
    counter = counter + 1
    if(not(pd.isna(log["channel"]))):
        insert, node_exists = get_actor_insert_value_str(log,
                                                         mapping,
                                                         event,
                                                         "Receiver",
                                                         connector, session)
        where_clause = get_actors_Identifier(log, mapping, "Receiver", event)
        connector.create_entity(insert, node_exists, session, where_clause)
        counter = counter + 1


def get_connection_properties(log, mapping, type_of_connection):
    fields = ["channel", "initiator" if type_of_connection == "Sender"
              else "receiver"]

    edge_fields = ""
    first_field = True
    for field in fields:
        if field == "channel":
            if field in log and not(pd.isna(log[field])):
                if not first_field:
                    edge_fields = edge_fields + ","
                edge_fields = edge_fields \
                              + field \
                              + ":" \
                              + get_value_To_string(log[field])
                first_field = False
        else:
            # Check if field exists in log before accessing
            if field in log and not(pd.isna(log[field])):
                if not first_field:
                    edge_fields = edge_fields + ","
                edge_fields = edge_fields \
                          + "Actor:" \
                          + get_value_To_string(log[field])
                first_field = False
            else:
                print(f"[WARNING] Field '{field}' not found in log data for {type_of_connection} connection")

    # Remove any trailing commas (safety check)
    edge_fields = edge_fields.rstrip(',').strip()
    return edge_fields


def getToRemoveAttributes(mapper):
    deleteTo = ""
    first = True
    for fieldId in mapper.event:
        if fieldId.to_type == "Entity":
            if not first:
                deleteTo += ","
            deleteTo += "n."+ fieldId.name
            first = False
    return deleteTo

def create_connection_between_actor_event(connector,
                                          log, mapping, type_of_connection,
                                          session, event):
    properties = get_connection_properties(log,
                                           mapping,
                                           type_of_connection)

    query_to_get_class_node = get_where_clause_to_find_node(log,
                                                            event,
                                                            "Event")

    query_to_get_class_node = query_to_get_class_node \
        + f''' AND e.journey="{log["case:journey"]}"'''

    query_to_get_event_node = "e.Id = " \
        + f'''"{log["Id"]}" AND e.journey="{log["case:journey"]}"'''

    query = get_where_clause_to_match_other_node(mapping,
                                                 "Event",
                                                 "Entity",
                                                 type_of_connection,
                                                 log,
                                                 event)
    
    # Validate query is not empty before creating relationship
    if not query or query.strip() == "":
        print(f"    [WARN] Empty match query for {type_of_connection} relationship - skipping")
        return
    
    connector.create_connection_touchpoint_entity(query_to_get_class_node,
                                                      query_to_get_event_node,
                                                      query,
                                                      type_of_connection,
                                                      properties, session)

    # Also validate for event-entity connection
    if query and query.strip():
        connector.create_connection_event_entity(query_to_get_class_node,
                                                 query_to_get_event_node,
                                                 query,
                                                 properties, session)


def create_connection_between_toucpoint_log(connecector, row, mapping, session, event):

    touchpoint_where = event.get_primary_where(row)
    log_where = mapping.get_primary_where(row)

    match_clause = 'e.LogID = en.LogID AND e.journey = en.journey'
    connecector.create_connection_event_journey(touchpoint_where,
                                                log_where,
                                                match_clause,
                                                session)


def main():
    master = tk.Tk()
    connectUI = ConnectionUI(master)
    master.mainloop()
    master = tk.Tk()
    fileUploadUI = FileUploadUI(master)
    master.mainloop()
    
    listOfJourneys = []
    connector = connectUI.get_connector()
    
    # Get file location first - check if user actually selected a file
    try:
        file_location = fileUploadUI.getFileLocation()
    except AttributeError:
        # User closed the window without selecting a file
        file_location = ""
    
    # Check if file is valid and determine file type
    if file_location == "":
        messagebox.showerror("Error occurred", "No file selected")
        return
    
    # Clean database if user requested it - only after confirming a file was selected
    if connectUI.should_clean_database():
        print("[INFO] Cleaning database before processing...")
        with connector.driver.session() as session:
            connector.clean_database(session)
        print("[INFO] Database cleaned successfully")
    
    logs2 = None
    
    # Read file based on type
    if fileUploadUI.isCsvFile():
        # Read CSV file directly with pandas
        # Try semicolon delimiter first (common in European CSV files)
        # If that fails, fall back to comma delimiter
        try:
            logs2 = pd.read_csv(file_location, sep=';', encoding='utf-8-sig')
        except Exception:
            try:
                logs2 = pd.read_csv(file_location, sep=',', encoding='utf-8-sig')
            except Exception as e:
                messagebox.showerror("Error occurred", f"Failed to read CSV file: {str(e)}")
                return
        
        # Strip BOM (Byte Order Mark) from column names if present
        logs2.columns = logs2.columns.str.replace('\ufeff', '', regex=False)
    elif fileUploadUI.isXesFile():
        # Validate XES file against XSD schema
        xsd_path = os.path.join(os.path.dirname(__file__), 'Xes.xsd')
        if not xmlschema.is_valid(file_location, xsd_path):
            messagebox.showerror("Error occurred", "XES file is not compliant with XSD")
            return
        # Read XES file with pm4py
        try:
            logs2 = pm4py.read_xes(file_location)
        except Exception as e:
            messagebox.showerror("Error occurred", f"Failed to read XES file: {str(e)}")
            return
    else:
        messagebox.showerror("Error occurred", "Unsupported file type. Please select a .xes or .csv file")
        return
    
    # Process the file (same for both CSV and XES)
    if logs2 is not None and not logs2.empty:
        # Preprocessing step: Map CSV columns to standard field names
        master = tk.Tk()
        preprocessor = PreprocessorUI(master, logs2, logs2.columns)
        master.mainloop()
        
        # Get preprocessed dataframe
        logs2 = preprocessor.get_preprocessed_dataframe()
        if logs2 is None:
            messagebox.showerror("Error occurred", "Preprocessing was cancelled")
            return
        
        # Continue with mapper using preprocessed data
        master = tk.Tk()
        mapper = Mapper(master, "Test", logs2.columns)
        master.mainloop()

        file_name = fileUploadUI.getFileName()
        
        time_stamp = int(time.time())
        actor, event, logs, objects, rating = mapper.actor, mapper.event, mapper.logs, mapper.objects, mapper.rating

        master = tk.Tk()
        selector = TimeSelector(master, event)
        datefields = selector.fieldList
        master.mainloop()
        try:
            print(f"\n{'='*80}")
            print(f"[INFO] Processing {len(logs2)} rows...")
            print(f"{'='*80}\n")
            
            for index, row in logs2.iterrows():
                print(f"\n[ROW {index + 1}/{len(logs2)}] Event: {row.get('EventType', 'N/A')}, Journey: {row.get('case:journey', 'N/A')}")
                
                with connector.driver.session() as session:
                    create_log(connector, row, logs,
                               session, file_name, time_stamp, rating)

                    listOfJourneys.append(row["case:journey"])

                    create_entities(connector, row,
                                    event, session,
                                    datefields, rating, logs, objects)

                    create_actors(connector, row,
                                  actor, session, event)

                    create_connection_between_actor_event(connector,
                                                          row,
                                                          actor,
                                                          "Sender",
                                                          session, event)
                    if(not(pd.isna(row["channel"]))):
                        create_connection_between_actor_event(connector,
                                                              row,
                                                              actor,
                                                              "Receiver",
                                                              session, event)

                    connector.create_directly_follows_tx(row["case:journey"],
                                                         session)
                    create_connection_between_toucpoint_log(connector,
                                                            row,
                                                            logs,
                                                            session, event)
            
            print(f"\n{'='*80}")
            print(f"[INFO] Finalizing graph structure...")
            print(f"{'='*80}\n")
            
            listOfJourneys = list(set(listOfJourneys))
            with connector.driver.session() as session:
                print("[POST] Creating entity-based directly-follows relationships...")
                connector.direct_follows_fix(session)
                
                print("[POST] Linking logs to events...")
                for journey in listOfJourneys:
                    connector.has_to_events(session)
                
                print("[POST] Removing null directly-follows relationships...")
                connector.removeNullDF(session)
                
                print("[POST] Cleaning up temporary entity properties...")
                attributesToRemove = getToRemoveAttributes(mapper)
                connector.removePropertiesOfActors(session, attributesToRemove)
            
            print(f"\n{'='*80}")
            print(f"[SUCCESS] Graph upload completed!")
            print(f"{'='*80}\n")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"[ERROR] Upload failed with exception:")
            print(error_details)
            print(f"[ERROR] Error message: {str(e)}")
            messagebox.showerror("Error occurred", f"Upload has stopped due to: {str(e)}\n\nCheck console for details.")
    else:
        messagebox.showerror("Error occurred", "File is empty or could not be processed")


if __name__ == "__main__":
    main()
