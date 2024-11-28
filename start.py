from tkinter import messagebox
from Interface.Connection.ConnectionUI import ConnectionUI
from Interface.FileUpload.FileUploadUI import FileUploadUI
from Interface.Mapper.mapper import Mapper
from Interface.TimeSelector.TimeSelector import TimeSelector
import Xes
import xmlschema
import tkinter as tk
import pm4py
import pandas as pd
import time
import numpy as np
from Functions.StringManipulation import get_value_To_string, check_if_string_is_not_None, remove_case_append
from Class.log import log
from Class.objects import objects
import re


filesXes = Xes.Xes()
status = ""
fileToRead = ""
counter = 0

listOfEmpty = []


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
    node = f'''TimeStampType:"{field}", TimeStamp:"{log[field]}", Id:"{log["Id"]}"
                                    , journey:"{log["case:journey"]}", Label:"{log["EventType"]}"'''
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
    global listOfEmpty
    is_planned = False
    try:
        if np.isnan(log['case:isPlanned']):
            is_planned = False
        else:
            is_planned = log['case:isPlanned']
    except: 
        is_planned = False
    for field in timestampNames:
        if field in log:
            if not (pd.isnull(log[field])) and not (is_planned):
                create_subevent(connector, log, mapping, field, session)

    if(log['initiatorsLabel'] not in listOfEmpty):
        connector.create_class(append_log_metadata(
            mapping.get_field_string(log),
            log), session, is_planned)

    connector.create_class_event_relationship(log["Id"],
                                              log["case:journey"], session)

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
    for index, i in enumerate(fields):

        query = query + "e." + i.name \
                 + " = " \
                 + get_value_To_string(log[i.name])

        if index != len(fields) - 1:
            query = query + ", "

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
        keys = [m for m in insert_elements
                if m.entity_type == previous_entity_type]
        values = [m for m in insert_elements
                  if m.entity_type == current_entity_type]

        for index, i in enumerate(keys):
            mock_other_type_keys = mock_other_type_keys + alias + i.name \
                                   + sign \
                                   + f'''\'{log[values[index].name]}\''''

            if len(keys) - 1 > index:
                mock_other_type_keys = mock_other_type_keys + ","

    return mock_other_type_keys


def check_if_node_exists(connector, query, session):
    return connector.check_node_existance(query, session)


def get_actor_insert_value_str(log, mapping,
                               event, entity_type,
                               connnector, session):
    insert = ""
    user_type = ""

    if (mapping.check_if_array_has_identifier()):
        insert_elements = [m for m in event if m.to_type == "Entity"]
        insert = get_query_using_array(insert_elements, log, entity_type)

    node_exists = check_if_node_exists(connnector, insert, session)
    sign = "=" if node_exists else ":"

    if node_exists:
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
        regexMatch = re.search("[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}", log[user_to_pick])
        user_type = user_type \
                    + "EntityType"\
                    + sign\
                    + '"End user"' if log["case:enduser"] == log[user_to_pick] or regexMatch is not None \
                    else "EntityType"+sign+'"Service Provider"'

        insert = insert + "," + user_type

    insert = insert + "," + mock_values
    return insert, node_exists


def get_actors_Identifier(log, mapping, entity_type, event):
    reuquest = ""
    if (mapping.check_if_array_has_identifier()):
        insert_elements = [m for m in event if m.to_type == "Entity"]
        fields = [m for m in insert_elements if (m.entity_type == entity_type
                  or m.entity_type == "Both")
                  and m.to_type == "Entity"]

        for index, f in enumerate(fields):
            reuquest = reuquest + f.name + ":'" + str(log[f.name]) +"'" # check main field to make sure it is not nan, if nan skip
            if len(fields) - 1 > index:
                reuquest = reuquest + ","
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
    for field in fields:
        if field == "channel":
            if not(pd.isna(log[field])):
                edge_fields = edge_fields \
                              + field \
                              + ":" \
                              + get_value_To_string(log[field]) + ","

        else:
            edge_fields = edge_fields \
                          + "Actor:" \
                          + get_value_To_string(log[field])

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

    query_to_get_event_node = "ev.Id = " \
        + f'''"{log["Id"]}" AND ev.journey="{log["case:journey"]}"'''

    query = get_where_clause_to_match_other_node(mapping,
                                                 "Event",
                                                 "Entity",
                                                 type_of_connection,
                                                 log,
                                                 event)
    
    connector.create_connection_touchpoint_entity(query_to_get_class_node,
                                                      query_to_get_event_node,
                                                      query,
                                                      type_of_connection,
                                                      properties, session)

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
    master = tk.Tk()
    listOfJourneys = []
    connector = connectUI.get_connector()
    
    if fileUploadUI.getFileLocation() != "" and \
        xmlschema.is_valid(fileUploadUI.getFileLocation(), '.\Xes.xsd'):
        logs2 = pm4py.read_xes(fileUploadUI.getFileLocation())

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
            for index, row in logs2.iterrows():
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
            listOfJourneys = list(set(listOfJourneys))
            with connector.driver.session() as session:
                connector.direct_follows_fix(session)
                for journey in listOfJourneys:
                    connector.has_to_events(session)
                connector.removeNullDF(session)
                print(mapper)
                attributesToRemove = getToRemoveAttributes(mapper)
                connector.removePropertiesOfActors(session, attributesToRemove)
        except Exception as e:
            messagebox.showerror("Error occured", "Upload has stoped due to:" + e)
    else:
          messagebox.showerror("Error occured", "XML is not complient with XSD")


if __name__ == "__main__":
    main()
