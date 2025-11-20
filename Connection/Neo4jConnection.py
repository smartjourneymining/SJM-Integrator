from neo4j import GraphDatabase
import pandas as pd


class Neo4jConnection:

    def __init__(self, uri, userName, password):
        self.driver = GraphDatabase.driver(uri=uri, auth=(userName, password))

    def close(self):
        self.driver.close()

    def check_connection(self):
        try:
            self.driver.verify_connectivity()
        except:
            return False
        return True

    def check_authentification(self):
        result = self.driver.verify_authentication()
        return result

    def create_journey_tx(self, tx, journey):
        q_create_journey = f''' Merge (l:Journey:Entity {{{journey}}})'''

        tx.run(q_create_journey)

    def create_journey(self, journey_query, session):
        session.execute_write(self.create_journey_tx, journey_query)

    def create_log(self, file_name, time_stamp, session):
        session.execute_write(self.create_log_tx, file_name, time_stamp)

    def create_log_tx(self, tx, file_name, time_stamp):
        q_create_log = f'''MERGE  (en:Log {{fileName:"{file_name}",
        timeStamp:{time_stamp}}})'''
        tx.run(q_create_log)

    def associate_log_with_journey(self, session, log_where,
                                   file_name, time_stamp):
        session.execute_write(self.associate_log_with_journey_tx, log_where,
                              file_name, time_stamp)

    def associate_log_with_journey_tx(self, tx,  log_where,
                                      file_name, time_stamp):
        q_associate_log_with_journey = f'''
        MATCH (l:Log {{fileName:"{file_name}",timeStamp:{time_stamp}}})
        MATCH (j:Journey {{{log_where}}})
        MERGE (l)-[:Has]->(j)
        '''
        tx.run(q_associate_log_with_journey)

    def create_event_tx(self, tx, attributes):
        column = "{"
        q_Create_Event = ' Create (e:Event  '
        column += attributes
        q_Create_Event += column
        q_Create_Event += ", Activity:TouchpointEvent"
        q_Create_Event += "})"

        tx.run(q_Create_Event)

    def removePropertiesOfActors(self,  session, attributes):
        session.execute_write(self.removePropertiesOfActors_tx, attributes)

    def removePropertiesOfActors_tx(self, tx, attributes):
        q_remove_properties = f'''Match (n:Entity) Remove {attributes} return n'''
        tx.run(q_remove_properties)

    def create_subevent(self, attributes, session):
        session.execute_write(self.create_subevent_tx, attributes)

    def create_subevent_tx(self, tx, attributes):
        q_create_subevent = f'''Create (n: Event {{{attributes}}})'''
        tx.run(q_create_subevent)

    def create_event(self, event, session):
        session.execute_write(self.create_event_tx, event)

    def create_entity(self, insert_values, node_exists, session, identifier=""):
        if node_exists:
            # Validate that we have something to update
            if not insert_values or insert_values.strip() == "":
                return
            session.execute_write(self.update_Entity_tx,
                                  insert_values,
                                  identifier)
        else:
            session.execute_write(self.create_Entity_tx, insert_values)

    def create_Entity_tx(self, tx, insert_values):
        # Validate insert_values is not empty
        if not insert_values or insert_values.strip() == "":
            return
        
        # Clean up trailing/leading commas
        insert_values = insert_values.strip().strip(',').strip()
        if not insert_values:
            return
        
        try:
            q_create_entity = f'''
            MERGE (en:Entity {{{insert_values}}})'''
            
            print(f"  [CREATE] Entity node: {insert_values[:100]}{'...' if len(insert_values) > 100 else ''}")
            tx.run(q_create_entity)
        except Exception as e:
            print(f"    [ERROR] Entity creation failed: {e}")
            raise

    def add_journey(self, connection, journeyID):
        qAddJourney = f''' Create (:Journey:Entity {{ID: "{journeyID}", EntityType="{"Journey"}"}})'''
        connection.run(qAddJourney)

    def create_connection_event_journey(self, event_where, journey_where,
                                        match, session):
        session.execute_write(self.connect_journey_to_event, journey_where,
                              event_where, match)

    def connect_journey_to_event(self, connection, journey_where, 
                                 event_where, match):
        q_link_events_to_journey = f'''
            MATCH (en:Touchpoint {{{event_where}}})
            MATCH (e: Journey {{{journey_where}}})
            WHERE {match}
            MERGE (e)-[:Contains]->(en)
        '''
        connection.run(q_link_events_to_journey)

    def create_entity_touchpoint_relationship(self, connection,
                                         where_clause,
                                         query_to_get_event_node,
                                         match_clause,
                                         type_of_connection,
                                         properties):
        # Validate WHERE clauses are not empty
        if not where_clause or where_clause.strip() == "":
            print(f"    [ERROR] Empty WHERE clause for {type_of_connection} relationship")
            return
        
        if not match_clause or match_clause.strip() == "":
            print(f"    [ERROR] Empty MATCH clause for {type_of_connection} relationship")
            return
        
        # Clean up properties string - remove trailing commas and whitespace
        if properties:
            properties = properties.strip().rstrip(',').strip()
        
        # Convert Event WHERE clause to Touchpoint WHERE clause by replacing 'e.' with 'tp.'
        # The where_clause is for Events, but we need to match Touchpoints
        touchpoint_where = where_clause.replace("e.", "tp.")
        
        # Convert match_clause to use Touchpoint alias instead of Event alias
        # The match_clause compares Event fields (e.) to Entity fields (en.)
        # We need to compare Touchpoint fields (tp.) to Entity fields (en.)
        touchpoint_match_clause = match_clause.replace("e.", "tp.")
        
        try:
            # Use proper Neo4j syntax: MATCH ... WHERE ... instead of MATCH ... WHERE ... in the same clause
            # Handle empty properties - if properties exist, add them, otherwise just the relationship type
            if properties and properties.strip():
                q_entity_event_relationship = f'''
                MATCH (tp:Touchpoint)
                WHERE {touchpoint_where}
                MATCH (en:Entity)
                WHERE {touchpoint_match_clause}
                MERGE (tp)-[:{type_of_connection} {{{properties}}}]->(en)'''
            else:
                q_entity_event_relationship = f'''
                MATCH (tp:Touchpoint)
                WHERE {touchpoint_where}
                MATCH (en:Entity)
                WHERE {touchpoint_match_clause}
                MERGE (tp)-[:{type_of_connection}]->(en)'''
            
            print(f"  [LINK] Touchpoint -> {type_of_connection} -> Entity")
            print(f"    WHERE: {touchpoint_where[:80]}{'...' if len(touchpoint_where) > 80 else ''}")
            print(f"    MATCH: {touchpoint_match_clause[:80]}{'...' if len(touchpoint_match_clause) > 80 else ''}")
            connection.run(q_entity_event_relationship)
        except Exception as e:
            print(f"    [ERROR] Failed to link Touchpoint -> {type_of_connection} -> Entity: {e}")
            raise

    def create_connection_touchpoint_entity(self, where_clause,
                                            query_to_get_event_node, 
                                            field_name,
                                            type_of_connection, properties,
                                            session):
        session.execute_write(self.create_entity_touchpoint_relationship,
                              where_clause, query_to_get_event_node,
                              field_name, type_of_connection, properties)

    def create_entity_event_relationship(self, connection,
                                         where_clause,
                                         query_to_get_event_node,
                                         match_clause,
                                         properties):
        # Validate WHERE clauses are not empty
        if not where_clause or where_clause.strip() == "":
            print(f"    [ERROR] Empty WHERE clause for Event-Entity relationship")
            return
        
        if not query_to_get_event_node or query_to_get_event_node.strip() == "":
            print(f"    [ERROR] Empty Event node query")
            return
        
        if not match_clause or match_clause.strip() == "":
            print(f"    [ERROR] Empty MATCH clause for Event-Entity relationship")
            return
        
        try:
            # Match Event and Entity directly, then create Corr relationship
            # where_clause is not needed here - it's only used for Touchpoint-Entity relationships
            # Both query_to_get_event_node and match_clause use 'e.' for Event, so they're consistent
            q_entity_event_relationship = f'''
            MATCH (e:Event WHERE {query_to_get_event_node})
            MATCH (en:Entity WHERE {match_clause})
            MERGE (e)-[cr:Corr]->(en)'''
            
            print(f"  [LINK] Event -> Corr -> Entity")
            print(f"    Event WHERE: {query_to_get_event_node[:80]}{'...' if len(query_to_get_event_node) > 80 else ''}")
            print(f"    Entity WHERE: {match_clause[:80]}{'...' if len(match_clause) > 80 else ''}")
            connection.run(q_entity_event_relationship)
        except Exception as e:
            print(f"    [ERROR] Failed to link Event -> Corr -> Entity: {e}")
            raise

    def create_connection_event_entity(self, where_clause,
                                       query_to_get_event_node, field_name,
                                       properties,
                                       session):
        session.execute_write(self.create_entity_event_relationship,
                              where_clause, query_to_get_event_node,
                              field_name, properties)

    def create_direct_event_flow(self, connection, jounreyID):
        q_direct_event_flow = f'''
        MATCH (n)<-[:Sender|:Receiver]- ( ev: Event WHERE ev.journey = {jounreyID})
        WITH n, ev as events ORDER BY ev.timestamp, elementId(e)
        WITH n, collect( events ) AS eventList
        UNWIND range(0,size(eventList) -2 ) AS i
        WITH n, eventList[i] as e1, eventList[i+1] as e2
        MERGE (e1)-[df:Df {{EntityType:n.EntityType}}]->(e2)
        '''
        connection.run(q_direct_event_flow)

    def create_directly_follows_tx(self, journey, session):
        session.execute_write(self.create_directly_follows, journey)

    def create_directly_follows(self, tx, journey):
        qCreateDf = f'''
        MATCH (b:Event)
        WHERE b.journey = "{journey}"
        WITH b
        ORDER BY b.timestamp
        WITH collect(b) AS nodes
        UNWIND range(0,size(nodes) -2 ) AS i
        WITH nodes[i] as e1, nodes[i+1] as e2
        MERGE (e1)-[:Df  {{EntityType: "Journey"}}]->(e2)'''

        tx.run(qCreateDf)

    def create_class(self, insert, session, is_planned=False, primary_keys=None, journey=None, log=None):
        session.execute_write(self.create_class_tx, insert, is_planned, primary_keys, journey, log)

    def create_class_tx(self, tx, insert, is_planned, primary_keys=None, journey=None, log=None):
        from Functions.StringManipulation import get_value_To_string, check_if_string_is_not_None, remove_case_append
        
        # Validate insert is not empty (excluding the Type property we add)
        if not insert or insert.strip() == "":
            full_properties = "Type:\"Touchpoint\""
        else:
            # Clean up trailing/leading commas
            insert = insert.strip().strip(',').strip()
            full_properties = insert + ", Type" + ":\"Touchpoint\""
        
        try:
            # If primary keys, journey, and log are provided, use MERGE to prevent duplicates
            # Otherwise, use CREATE (for backward compatibility)
            # Note: log is a pandas Series, so we check 'is not None' instead of truthiness
            if primary_keys is not None and journey is not None and log is not None and primary_keys.getLength() > 0:
                # Build MERGE clause using Id + EventType + journey
                # Id is auto-generated and unique per CSV row, so each row should create a unique touchpoint
                # A touchpoint is uniquely identified by: Id + EventType + journey
                merge_properties = []
                
                # CRITICAL: Add Id first (auto-generated, unique per CSV row)
                # This ensures each CSV row creates a unique touchpoint node
                if 'Id' in log and not pd.isna(log['Id']) and log['Id'] != "":
                    id_value = get_value_To_string(log['Id'])
                    if check_if_string_is_not_None(id_value):
                        merge_properties.append(f'Id: {id_value}')
                
                # Add EventType to merge properties (critical for touchpoint uniqueness)
                # Touchpoints with same Id but different EventType should be different touchpoints
                # Note: log is a pandas Series, so we check 'in log' (checks index) and handle NaN
                if 'EventType' in log and not pd.isna(log['EventType']) and log['EventType'] != "":
                    event_type_value = get_value_To_string(log['EventType'])
                    if check_if_string_is_not_None(event_type_value):
                        merge_properties.append(f'EventType: {event_type_value}')
                
                # Add journey to merge properties
                merge_properties.append(f'journey: "{journey}"')
                
                # Add Type to merge properties
                merge_properties.append('Type: "Touchpoint"')
                
                merge_clause = ", ".join(merge_properties)
                
                # Use MERGE with ON CREATE SET to set all properties when creating
                # ON MATCH is optional - we could update properties if needed
                q_create_class = f'''
                MERGE (c:Touchpoint{ ":Class" if is_planned else "" } {{{merge_clause}}})
                ON CREATE SET c = {{{full_properties}}}
                '''
                
                print(f"  [MERGE] Touchpoint (unique keys: {merge_clause[:100]}{'...' if len(merge_clause) > 100 else ''})")
            else:
                # Fallback to CREATE for backward compatibility
                q_create_class = f'''
                CREATE (c:Touchpoint{ ":Class" if is_planned else "" } {{{full_properties}}} )
                '''
                
                print(f"  [CREATE] Touchpoint: {full_properties[:100]}{'...' if len(full_properties) > 100 else ''}")
            
            tx.run(q_create_class)
        except Exception as e:
            print(f"    [ERROR] Touchpoint creation failed: {e}")
            raise

    def create_class_event_relationship(self, log, primary_keys, journeyID, session):
        session.execute_write(self.create_class_event_relationship_tx,
                              log, primary_keys, journeyID)

    def create_class_event_relationship_tx(self, tx, log, primary_keys, journeyID):
        from Functions.StringManipulation import get_value_To_string, check_if_string_is_not_None, remove_case_append
        
        # Build WHERE clause for Event using Id + EventType + journey
        # Id is auto-generated and unique per CSV row, ensuring each event matches to its unique touchpoint
        event_where_parts = []
        touchpoint_where_parts = []
        
        # CRITICAL: Add Id first (auto-generated, unique per CSV row)
        # This ensures each event matches to its corresponding unique touchpoint
        if 'Id' in log and not pd.isna(log['Id']) and log['Id'] != "":
            id_value = get_value_To_string(log['Id'])
            if check_if_string_is_not_None(id_value):
                event_where_parts.append(f'e.Id = {id_value}')
                touchpoint_where_parts.append(f'c.Id = {id_value}')
        
        # Also include primary keys if they exist (for additional matching criteria)
        for field in primary_keys.dataFields:
            if field.name in log:
                value = get_value_To_string(log[field.name])
                if check_if_string_is_not_None(value):
                    field_name = remove_case_append(field.name)
                    event_where_parts.append(f'e.{field_name} = {value}')
                    touchpoint_where_parts.append(f'c.{field_name} = {value}')
        
        # Add EventType to both WHERE clauses (events use Label, touchpoints use EventType)
        # This ensures events match to the correct touchpoint based on EventType
        if 'EventType' in log and not pd.isna(log['EventType']) and log['EventType'] != "":
            event_type_value = get_value_To_string(log['EventType'])
            if check_if_string_is_not_None(event_type_value):
                # Events store EventType as Label, touchpoints store it as EventType
                event_where_parts.append(f'e.Label = {event_type_value}')
                touchpoint_where_parts.append(f'c.EventType = {event_type_value}')
        
        # Add journey to both WHERE clauses
        event_where_parts.append(f'e.journey = "{journeyID}"')
        touchpoint_where_parts.append(f'c.journey = "{journeyID}"')
        
        if not event_where_parts:
            return
        
        event_where = " AND ".join(event_where_parts)
        touchpoint_where = " AND ".join(touchpoint_where_parts)
        
        # Use proper Neo4j syntax: MATCH ... WHERE ... instead of MATCH ... WHERE ... in the same clause
        q_create_relationship = f'''
        MATCH (e:Event)
        WHERE {event_where}
        MATCH (c:Touchpoint)
        WHERE {touchpoint_where}
        MERGE (e)-[:Observe]->(c)
        '''

        tx.run(q_create_relationship)

    def check_node_existance(self, query, session):
        result = session.execute_read(self.check_node_existance_tx, query)
        return result

    def check_node_existance_tx(self, tx, query):
        q_check_node_existance = f'''MATCH (e:Entity {{{query}}})
        return e'''
        record = tx.run(q_check_node_existance)
        if (record.single() is None):
            return False
        return True

    def update_Entity_tx(self, tx, query, identifier):
        # Skip update if query is empty to avoid "SET ," syntax error
        if not query or query.strip() == "":
            return
        
        # Remove leading/trailing commas and whitespace
        query = query.strip().strip(',').strip()
        if not query:
            return
        
        try:
            q_update_entity = f'''MATCH (e:Entity {{{identifier}}})
            SET {query}'''
            
            print(f"  [UPDATE] Entity: SET {query[:100]}{'...' if len(query) > 100 else ''}")
            tx.run(q_update_entity)
        except Exception as e:
            print(f"    [ERROR] Entity update failed: {e}")
            raise

    def create_communication_node(self, session, channel):
        session.execute_write(self.create_communication_node_tx, channel)

    def create_communication_node_tx(self, tx, channel):
        q_merge_channel = f'''MERGE (c:Channel {{Channel:"{channel}"}})'''
        tx.run(q_merge_channel)

    def associate_touchpoint_and_communication(self, channel_name,
                                          where_touchpoint, session):
        session.execute_write(self.associate_touchpoint_and_communication_tx,
                              channel_name, where_touchpoint)

    def associate_touchpoint_and_communication_tx(self, tx,
                                             channel_name, where_touchpoint):
        q_associate_channel_touchpoint = f'''MATCH (c:Channel
        {{Channel:"{channel_name}"}})
        MATCH (e:Touchpoint {{{where_touchpoint}}})
        MERGE (e)-[:Communicated]->(c)
        '''

        tx.run(q_associate_channel_touchpoint)

    def associate_experience_with_journey(self, session, journey_data,
                                          properties):
        session.execute_write(self.associate_experience_with_journey_tx,
                              journey_data, properties)

    def associate_experience_with_Journey(self, where_clause,
                                             properties, session):
        session.execute_write(self.associate_experience_with_journey_tx,
                              where_clause, properties)

    def associate_experience_with_touchpoint(self, session, where_clause,
                                             jounreyID,
                                             properties):
        session.execute_write(self.associate_experience_with_touchpoint_tx,
                              where_clause, jounreyID, properties)

    def associate_experience_with_journey_tx(self, tx,
                                             journey_data, properties):
        q_create_node_and_relationship = f'''MATCH (j:Journey {{journey: "{journey_data}"}})
        MERGE (j) -[r:Rates] ->(e:Experience {{{properties}}})'''
        tx.run(q_create_node_and_relationship)

    def associate_experience_with_touchpoint_tx(self, tx,
                                                where_clause, jounreyID, properties):
        q_create_node_and_relationship = f'''MATCH (j:Touchpoint {{{where_clause }, {jounreyID}}})
        Create (j) -[r:Rates] ->(e:Experience {{{properties}}})'''
        tx.run(q_create_node_and_relationship)

    def associate_object_with_touchpoint(self, session,
                                         where_clause, properties):
        session.execute_write(self.associate_object_with_touchpoint_tx,
                              where_clause, properties)

    def associate_object_with_touchpoint_tx(self, tx,
                                            where_clause, properties):
        q_create_object_with_touchpoint = f'''MATCH (j:Touchpoint {{{where_clause}}})
        Create (j) -[r:belongs] ->(e:Object {{{properties}}})'''
        tx.run(q_create_object_with_touchpoint)

    def create_planned_touchpoint_connection(self, session, journey):
        session.execute_write(self.tx_create_planned_touchpoint_connection, journey)

    def tx_create_planned_touchpoint_connection(self, connection, journey):
        q_direct_event_flow = f'''MATCH (n: Class)
        WHERE n.journey = "{journey}"
        WITH n ORDER BY n.id
        WITH collect(n) AS nodeList
        UNWIND range(0, size(nodeList) - 2) AS i
        WITH nodeList[i] as e1, nodeList[i+1] as e2
        MERGE (e1)<-[:Depends]-(e2)
        '''
        connection.run(q_direct_event_flow)

    def direct_follows_fix(self, session):
        session.execute_write(self.tx_direct_follows_fix,)

    def tx_direct_follows_fix(self, connection): # Remove journey based DF creation, this should show multitasking. After load delete all DF and recreate 
        query = f'''  
        MATCH (n: Entity)<-[:Corr]-(ev:Event) 
        WITH n, ev as events ORDER BY ev.TimeStamp, ev.Id
        WITH n, collect(events) AS eventList
        UNWIND range(0, size(eventList)-2) AS i
        WITH n, eventList[i] as e1, eventList[i+1] as e2
        Create (e1)-[df:Df {{EntityType:n.EntityType}}]->(e2)
        '''
        connection.run(query)
     
    def removeNullDF(self, session):
        session.execute_write(self.removeNullDF_tx)

    def removeNullDF_tx(self, connection):
        query= f''' MATCH p=()-[r:Df]->() WHERE r.EntityType IS NULL DELETE r'''
        connection.run(query)
 
    def associate_experience_with_event(self, session, where_clause,
                                        jounreyID,
                                        properties):
        session.execute_write(self.associate_experience_with_touchpoint_tx,
                              where_clause, jounreyID, properties)

    def associate_experience_with_event_tx(self, tx,
                                           where_clause, jounreyID, properties):
        q_create_node_and_relationship = f'''MATCH (j:Touchpoint {{{where_clause }, {jounreyID}}})-[:Observe]-(e:Event)
        Create (e) <-[r:Derived] -(e:Experience {{{properties}}})'''
        tx.run(q_create_node_and_relationship)

    def has_to_events(self, session):
        session.execute_write(self.has_to_events_tx)

    def has_to_events_tx(self, connection):
        query = f'''MATCH (l:Log)
        MATCH (e:Event)
        MERGE (l)-[:Has]->(e)
        '''
        connection.run(query)

    def clean_database(self, session):
        """Delete all nodes and relationships from the database"""
        session.execute_write(self.clean_database_tx)

    def clean_database_tx(self, tx):
        """Transaction to delete all nodes and relationships"""
        query = '''
        MATCH (n)
        DETACH DELETE n
        '''
        result = tx.run(query)
        summary = result.consume()
        print(f"[INFO] Cleaned database: Deleted {summary.counters.nodes_deleted} nodes and {summary.counters.relationships_deleted} relationships")
        return summary
