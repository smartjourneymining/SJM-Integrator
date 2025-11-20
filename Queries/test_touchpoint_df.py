#!/usr/bin/env python3
"""
Script to test and analyze touchpoint Df relationship creation.
Analyzes the results to ensure we're creating the correct number of relationships.
"""

import os
import sys
import subprocess
from pathlib import Path
from neo4j import GraphDatabase
from collections import defaultdict

# Add parent directory to path to import Neo4jConnection if needed
sys.path.insert(0, str(Path(__file__).parent.parent))

def is_running_in_wsl():
    """Check if Python is running under WSL (Windows Subsystem for Linux)"""
    try:
        # Primary check: /proc/version contains Microsoft or WSL indicators
        if os.path.exists('/proc/version'):
            with open('/proc/version', 'r') as f:
                version_info = f.read().lower()
                if 'microsoft' in version_info or 'wsl' in version_info:
                    return True
        
        # Secondary check: /etc/wsl.conf exists (WSL2 specific)
        if os.path.exists('/etc/wsl.conf'):
            return True
        
        # Tertiary check: Check for WSL-specific environment variable or files
        # This is a more conservative check - only if we're on Linux-like system
        if os.name != 'nt':  # Not Windows native
            # Check if running under WSL by looking for WSL-specific paths
            # WSL typically has /mnt/c, /mnt/d etc. mounted
            if os.path.exists('/mnt/c/Windows'):
                # Additional verification: check if /etc/resolv.conf points to Windows host
                # (Windows host IP is typically in 172.x.x.x range in WSL2)
                try:
                    if os.path.exists('/etc/resolv.conf'):
                        with open('/etc/resolv.conf', 'r') as f:
                            for line in f:
                                if line.startswith('nameserver'):
                                    ip = line.split()[1].strip()
                                    # WSL2 typically uses 172.x.x.x for Windows host
                                    if ip.startswith('172.'):
                                        return True
                except:
                    pass
    except:
        pass
    return False

def get_windows_host_ip():
    """Get Windows host IP address when running in WSL using ip route"""
    try:
        # Use ip route to get the default gateway (Windows host IP in WSL)
        result = subprocess.run(
            ['ip', 'route', 'show'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        
        # Parse output to find default route
        for line in result.stdout.split('\n'):
            if 'default' in line.lower():
                parts = line.split()
                # The gateway IP is typically the 3rd field (index 2)
                # Format: default via <IP> dev <interface> ...
                try:
                    # Look for 'via' keyword followed by IP
                    if 'via' in parts:
                        via_index = parts.index('via')
                        if via_index + 1 < len(parts):
                            ip = parts[via_index + 1].strip()
                            # Validate it's a valid IP (basic check)
                            if ip and '.' in ip:
                                return ip
                except (ValueError, IndexError):
                    continue
        
        # Fallback: try parsing as default via <IP> or just get 3rd field
        for line in result.stdout.split('\n'):
            if 'default' in line.lower():
                parts = line.split()
                if len(parts) >= 3:
                    ip = parts[2].strip()
                    if ip and '.' in ip and not ip.startswith('dev'):
                        return ip
                        
    except subprocess.TimeoutExpired:
        print("Warning: Timeout while determining Windows host IP")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Could not determine Windows host IP via ip route: {e}")
    except Exception as e:
        print(f"Warning: Could not determine Windows host IP: {e}")
    return None

def get_connection():
    """Get Neo4j connection from environment variables or prompt user."""
    # Get URI from environment or determine default
    uri = os.getenv('NEO4J_URI')
    if not uri:
        # Only apply Windows IP workaround if running in WSL
        uri = "bolt://localhost:7687"  # Default for native Windows/Linux
        if is_running_in_wsl():
            windows_ip = get_windows_host_ip()
            if windows_ip:
                uri = f"bolt://{windows_ip}:7687"
                print(f"Detected WSL environment. Using Windows host IP: {windows_ip}")
            else:
                print("Warning: Running in WSL but could not determine Windows host IP. Using localhost.")
    
    username = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', '12345678')
    
    if not password:
        print("Please set NEO4J_PASSWORD environment variable or enter it when prompted")
        password = input("Neo4j password: ")
    
    driver = GraphDatabase.driver(uri, auth=(username, password))
    return driver

def read_query_file(filepath):
    """Read a Cypher query file and remove comments."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove single-line comments (// ...)
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        # Remove comments but keep the line if it has code
        if '//' in line:
            comment_idx = line.find('//')
            code_part = line[:comment_idx].strip()
            if code_part:
                cleaned_lines.append(code_part)
        else:
            cleaned_lines.append(line)
    
    query = '\n'.join(cleaned_lines)
    
    # Remove trailing semicolons (Neo4j doesn't need them for single statements)
    # and split into multiple statements if semicolons are used as separators
    query = query.strip().rstrip(';')
    
    return query

def run_query(session, query, description):
    """Run a query and return results."""
    print(f"\n{'='*80}")
    print(f"Running: {description}")
    print(f"{'='*80}")
    try:
        result = session.run(query)
        records = list(result)
        print(f"✓ Query executed successfully. Returned {len(records)} records.")
        return records
    except Exception as e:
        print(f"✗ Error executing query: {e}")
        return []

def analyze_touchpoints(session, journey_id='ID14'):
    """Analyze touchpoints and their relationships."""
    print("\n" + "="*80)
    print("ANALYSIS: Touchpoints and Events")
    print("="*80)
    
    # Count touchpoints
    query = f"""
    MATCH (uj:Journey WHERE uj.journey = '{journey_id}')
    MATCH (uj)-[:Contains]-(tp:Touchpoint)
    RETURN COUNT(DISTINCT tp) AS touchpointCount
    """
    result = run_query(session, query, "Count touchpoints")
    touchpoint_count = result[0]['touchpointCount'] if result else 0
    print(f"Total touchpoints: {touchpoint_count}")
    
    # Check how many events observe each touchpoint
    query = f"""
    MATCH (uj:Journey WHERE uj.journey = '{journey_id}')
    MATCH (uj)-[:Contains]-(tp:Touchpoint)
    OPTIONAL MATCH (e:Event)-[:Observe]->(tp)
    RETURN tp.Id AS touchpointId, tp.EventType AS eventType, COUNT(e) AS eventCount
    ORDER BY eventCount DESC
    """
    result = run_query(session, query, "Events per touchpoint")
    
    touchpoints_with_multiple_events = [r for r in result if r['eventCount'] > 1]
    if touchpoints_with_multiple_events:
        print(f"\n⚠ WARNING: {len(touchpoints_with_multiple_events)} touchpoints have multiple events:")
        for r in touchpoints_with_multiple_events[:10]:  # Show first 10
            print(f"  Touchpoint {r['touchpointId']} ({r['eventType']}): {r['eventCount']} events")
    else:
        print("✓ All touchpoints have exactly one event (or zero)")
    
    # Count event Df relationships
    query = f"""
    MATCH (e1:Event)-[df:Df {{EntityType: 'Journey'}}]->(e2:Event)
    WHERE e1.journey = '{journey_id}' AND e2.journey = '{journey_id}'
    RETURN COUNT(df) AS dfCount
    """
    result = run_query(session, query, "Count event Df relationships")
    event_df_count = result[0]['dfCount'] if result else 0
    print(f"Total event Df relationships: {event_df_count}")
    
    return touchpoint_count, event_df_count

def analyze_touchpoint_df_relationships(session, journey_id='ID14'):
    """Analyze touchpoint Df relationships."""
    print("\n" + "="*80)
    print("ANALYSIS: Touchpoint Df Relationships")
    print("="*80)
    
    # Count unique touchpoint pairs with Df (use directed pattern to avoid double-counting)
    query = f"""
    MATCH (uj:Journey WHERE uj.journey = '{journey_id}')
    MATCH (uj)-[:Contains]-(tp1:Touchpoint)-[df:Df]->(tp2:Touchpoint)
    WHERE (uj)-[:Contains]-(tp2)
    RETURN COUNT(DISTINCT [tp1.Id, tp2.Id]) AS uniquePairs, COUNT(df) AS totalRelationships
    """
    result = run_query(session, query, "Count touchpoint Df relationships")
    if result:
        unique_pairs = result[0]['uniquePairs']
        total_relationships = result[0]['totalRelationships']
        print(f"Unique touchpoint pairs with Df: {unique_pairs}")
        print(f"Total Df relationships: {total_relationships}")
        
        if total_relationships > unique_pairs:
            print(f"⚠ WARNING: More relationships than unique pairs! Possible duplicates.")
        elif total_relationships == unique_pairs:
            print("✓ Number of relationships matches unique pairs (good!)")
    
    # Check for bidirectional relationships
    # Find pairs where both tp1->tp2 and tp2->tp1 exist
    query = f"""
    MATCH (uj:Journey WHERE uj.journey = '{journey_id}')
    MATCH (uj)-[:Contains]-(tp1:Touchpoint)-[df1:Df]->(tp2:Touchpoint)
    WHERE (uj)-[:Contains]-(tp2)
    WITH tp1, tp2
    MATCH (tp2)-[df2:Df]->(tp1)
    RETURN COUNT(*) AS bidirectionalCount
    """
    result = run_query(session, query, "Check for bidirectional relationships")
    if result:
        bidirectional_count = result[0]['bidirectionalCount']
        if bidirectional_count > 0:
            print(f"⚠ WARNING: {bidirectional_count} bidirectional relationships found")
        else:
            print("✓ No bidirectional relationships (good!)")
    
    # Show distribution of incoming/outgoing relationships
    query = f"""
    MATCH (uj:Journey WHERE uj.journey = '{journey_id}')
    MATCH (uj)-[:Contains]-(tp:Touchpoint)
    OPTIONAL MATCH (tp)-[dfOut:Df]->(:Touchpoint)
    OPTIONAL MATCH (:Touchpoint)-[dfIn:Df]->(tp)
    RETURN tp.Id AS touchpointId, 
           COUNT(DISTINCT dfOut) AS outgoingCount,
           COUNT(DISTINCT dfIn) AS incomingCount
    ORDER BY (COUNT(DISTINCT dfOut) + COUNT(DISTINCT dfIn)) DESC
    LIMIT 10
    """
    result = run_query(session, query, "Top touchpoints by relationship count")
    if result:
        print("\nTop 10 touchpoints by total relationships:")
        for r in result:
            total = r['outgoingCount'] + r['incomingCount']
            if total > 0:
                print(f"  {r['touchpointId']}: {r['outgoingCount']} outgoing, {r['incomingCount']} incoming")

def main():
    """Main function to run the analysis."""
    journey_id = os.getenv('JOURNEY_ID', 'ID14')
    
    print("="*80)
    print("Touchpoint Df Relationship Analysis")
    print("="*80)
    print(f"Journey ID: {journey_id}")
    print(f"Set JOURNEY_ID environment variable to change this")
    
    driver = get_connection()
    
    try:
        with driver.session() as session:
            # Analyze current state
            touchpoint_count, event_df_count = analyze_touchpoints(session, journey_id)
            
            # Check existing touchpoint Df relationships
            analyze_touchpoint_df_relationships(session, journey_id)
            
            # First, delete existing relationships
            delete_file = Path(__file__).parent / 'delete_touchpoint_df.cypher'
            if delete_file.exists():
                print("\n" + "="*80)
                print("EXECUTING: Delete Existing Touchpoint Df Relationships")
                print("="*80)
                
                query = read_query_file(delete_file)
                # Replace journey ID in query
                query = query.replace("'ID14'", f"'{journey_id}'")
                
                result = run_query(session, query, "Delete touchpoint Df relationships")
                if result:
                    deleted_count = result[0].get('deletedRelationships', 0)
                    print(f"Deleted {deleted_count} relationships")
            
            # Then, create new relationships
            create_file = Path(__file__).parent / 'create_touchpoint_df.cypher'
            if create_file.exists():
                print("\n" + "="*80)
                print("EXECUTING: Create Touchpoint Df Relationships")
                print("="*80)
                
                query = read_query_file(create_file)
                # Replace journey ID in query
                query = query.replace("'ID14'", f"'{journey_id}'")
                
                # First, check how many unique touchpoint pairs would be created
                diagnostic_query = f"""
                MATCH (uj:Journey WHERE uj.journey = '{journey_id}')
                MATCH (e1:Event)-[df:Df {{EntityType: 'Journey'}}]->(e2:Event)
                WHERE e1.journey = uj.journey AND e2.journey = uj.journey
                MATCH (e1)-[:Observe]->(tp1:Touchpoint)
                MATCH (e2)-[:Observe]->(tp2:Touchpoint)
                WHERE (uj)-[:Contains]-(tp1)
                  AND (uj)-[:Contains]-(tp2)
                  AND tp1 <> tp2
                WITH DISTINCT tp1, tp2
                RETURN COUNT(*) AS uniquePairs
                """
                diag_result = run_query(session, diagnostic_query, "Diagnostic: Count unique touchpoint pairs")
                if diag_result:
                    unique_pairs = diag_result[0].get('uniquePairs', 0)
                    print(f"Would create {unique_pairs} unique touchpoint pair relationships")
                
                result = run_query(session, query, "Create touchpoint Df relationships")
                print(f"Created/updated {len(result)} relationships")
                
                # Analyze after creation
                print("\n" + "="*80)
                print("ANALYSIS: After Creating Relationships")
                print("="*80)
                analyze_touchpoint_df_relationships(session, journey_id)
                
                # Expected vs actual
                print("\n" + "="*80)
                print("SUMMARY")
                print("="*80)
                print(f"Touchpoints: {touchpoint_count}")
                print(f"Event Df relationships: {event_df_count}")
                
                # Get actual count (use directed pattern to avoid double-counting)
                query = f"""
                MATCH (uj:Journey WHERE uj.journey = '{journey_id}')
                MATCH (uj)-[:Contains]-(tp1:Touchpoint)-[df:Df]->(tp2:Touchpoint)
                WHERE (uj)-[:Contains]-(tp2)
                RETURN COUNT(DISTINCT [tp1.Id, tp2.Id]) AS uniquePairs
                """
                result = run_query(session, query, "Final count")
                if result:
                    actual_count = result[0]['uniquePairs']
                    print(f"Actual touchpoint Df relationships: {actual_count}")
                    
                    # Compare against event Df count (should match)
                    if actual_count == event_df_count:
                        print(f"✓ Touchpoint Df relationships match event Df relationships (expected: {event_df_count})")
                    elif actual_count > event_df_count * 1.5:
                        print(f"⚠ WARNING: Touchpoint Df relationships ({actual_count}) significantly exceed event Df relationships ({event_df_count})")
                    elif actual_count < event_df_count * 0.5:
                        print(f"⚠ WARNING: Touchpoint Df relationships ({actual_count}) are much fewer than event Df relationships ({event_df_count})")
                    else:
                        print(f"ℹ Touchpoint Df relationships ({actual_count}) differ from event Df relationships ({event_df_count})")
            
    finally:
        driver.close()

if __name__ == '__main__':
    main()

