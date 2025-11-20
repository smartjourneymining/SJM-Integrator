"""
Module for converting Neo4j query results to GraphViz visualizations
Uses DOT format to create process flow visualizations with ellipses and clear left-to-right flow
"""
from graphviz import Digraph
import re
import os


def sanitize_label(text, max_length=40):
    """Sanitize text for use in GraphViz labels (process flow)"""
    if text is None:
        return "None"
    
    text = str(text).strip()
    
    # Remove common prefixes that add clutter
    if text.startswith('case:'):
        text = text[5:]
    
    # Replace newlines with spaces for better readability
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    # Escape special characters for GraphViz
    text = text.replace('"', '\\"').replace('\\', '\\\\')
    
    # Clean up multiple spaces
    import re
    text = re.sub(r'\s+', ' ', text)
    
    # Truncate if too long, but try to break at word boundaries
    if len(text) > max_length:
        # Try to break at a space near the max length
        truncated = text[:max_length]
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.7:  # If space is reasonably close to end
            text = truncated[:last_space] + "..."
        else:
            text = truncated + "..."
    
    return text


def get_node_id(node):
    """Generate a unique, sanitized ID for a node (GraphViz compatible)"""
    # GraphViz node IDs must be alphanumeric or underscore, no hyphens or special chars
    # Try to get element_id (Neo4j 5.x) or id (Neo4j 4.x)
    raw_id = None
    if hasattr(node, 'element_id'):
        raw_id = node.element_id
    elif hasattr(node, 'id'):
        raw_id = str(node.id)
    
    if raw_id:
        # Sanitize the ID - replace hyphens and special chars with underscores
        # GraphViz doesn't like hyphens in node IDs
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', str(raw_id))
        # Ensure it starts with a letter or underscore
        if sanitized and sanitized[0].isdigit():
            sanitized = 'n' + sanitized
        return sanitized if sanitized else f"node_{abs(hash(raw_id))}"
    else:
        # Fallback: use labels and properties
        labels = list(node.labels) if hasattr(node, 'labels') else []
        props = dict(node) if hasattr(node, '__iter__') else {}
        fallback_id = f"{'_'.join(labels)}_{abs(hash(str(props)))}"
        # Sanitize fallback ID too
        return re.sub(r'[^a-zA-Z0-9_]', '_', fallback_id)


def get_node_label(node):
    """Generate a readable label for a process flow node"""
    labels = list(node.labels) if hasattr(node, 'labels') else []
    props = dict(node) if hasattr(node, '__iter__') else {}
    
    # Priority order for displaying text in nodes
    # Prefer the most descriptive property first
    display_text = None
    
    # Try to find the most meaningful text to display
    for key in ['Label', 'EventType', 'name', 'Channel', 'EntityType', 'journey']:
        if key in props and props[key] is not None:
            value = str(props[key])
            if value and value.strip() and value.lower() != 'nan':
                display_text = sanitize_label(value, 40)  # Longer text for ellipses
                break
    
    # If no good property found, use the label type
    if not display_text:
        if labels:
            display_text = labels[0]  # Use first label
        else:
            display_text = "Node"
    
    # Add type as secondary info if different from main text
    if labels and labels[0] != display_text:
        return f"{display_text}\\n({labels[0]})"
    
    return display_text


def get_relationship_label(rel):
    """Generate a label for a relationship (simplified for process flow)"""
    rel_type = rel.type if hasattr(rel, 'type') else ''
    
    # Get relationship properties
    props = dict(rel) if hasattr(rel, '__iter__') else {}
    
    # For process flow, show relationship type if meaningful
    # Skip common/obvious relationship types to reduce clutter
    skip_types = ['Df', 'Observe', 'Contains']  # These are flow relationships, don't need labels
    
    if rel_type and rel_type not in skip_types:
        # Only show relationship type if it's meaningful
        return rel_type
    
    # Return empty string for flow relationships (they're implied by the arrow)
    return ''


def get_node_color(node):
    """Get a color for a node based on its labels (process flow colors)"""
    labels = list(node.labels) if hasattr(node, 'labels') else []
    
    # Process flow color scheme - lighter, more readable colors
    color_map = {
        'Event': '#E3F2FD',  # Light blue
        'Touchpoint': '#C8E6C9',  # Light green
        'Entity': '#FFF9C4',  # Light yellow
        'Journey': '#FFCCBC',  # Light coral
        'Log': '#F8BBD0',  # Light pink
        'Channel': '#E0E0E0',  # Light gray
        'Experience': '#E1BEE7',  # Light purple
        'Object': '#D7CCC8',  # Light brown
        'Class': '#BBDEFB'  # Very light blue
    }
    
    for label in labels:
        if label in color_map:
            return color_map[label]
    
    return '#FFFFFF'  # White background


def create_graphviz_visualization(records, output_path):
    """
    Create a GraphViz visualization from Neo4j query results using DOT format
    
    This function uses GraphViz DOT (Graph Description Language) to create
    the visualization. The DOT format is a plain text graph description language.
    
    Args:
        records: List of Neo4j record objects from query execution
        output_path: Path where the visualization should be saved
    """
    # Create a directed graph using DOT format
    # Digraph uses DOT (Graph Description Language) internally
    # The graph can be rendered to PNG, PDF, SVG, or saved as DOT source
    dot = Digraph(comment='Neo4j Query Result')
    
    # Process flow visualization settings - ensure left-to-right layout
    # Use 'dot' engine which properly respects rankdir='LR' and creates hierarchical layouts
    dot.engine = 'dot'
    
    # CRITICAL: Left to right flow - set rankdir at top level AND in graph attributes
    # This ensures the layout is definitely left-to-right
    dot.attr(rankdir='LR')  # Top-level attribute for left-to-right
    
    # Graph-level attributes for layout and rendering
    dot.attr('graph', 
             rankdir='LR',  # Also set in graph attributes (redundant but ensures it works)
             ranksep='3.0',  # More space between ranks (horizontal levels) for clarity
             nodesep='2.5',  # More space between nodes in same rank
             size='60,40',  # Larger canvas for high-res rendering
             concentrate='false',  # Don't merge edges - keep all visible
             splines='spline',  # Use splines instead of ortho to avoid port warnings
             pad='1.5',  # Padding around graph
             bgcolor='white')  # White background
    dot.attr('node', 
             shape='ellipse',  # Ellipse shape for process nodes
             style='filled,rounded',
             fontsize='14',  # Larger font for readability
             fontname='Arial',
             width='1.5',
             height='0.8',
             fixedsize='false')  # Allow nodes to size based on content
    dot.attr('edge', 
             fontsize='11',
             fontname='Arial',
             arrowsize='1.0',  # Slightly larger arrows
             penwidth='2.0')  # Thicker edges for better visibility
    
    # Track nodes and relationships we've already added
    added_nodes = set()
    added_edges = set()
    
    # Process each record
    for record in records:
        # Extract nodes and relationships from the record
        for key, value in record.items():
            if value is None:
                continue
            
            # Check if it's a node
            if hasattr(value, 'labels') or (hasattr(value, '__class__') and 'Node' in str(value.__class__)):
                node_id = get_node_id(value)
                if node_id not in added_nodes:
                    label = get_node_label(value)
                    color = get_node_color(value)
                    dot.node(node_id, label=label, fillcolor=color)
                    added_nodes.add(node_id)
            
            # Check if it's a relationship
            elif hasattr(value, 'type') or (hasattr(value, '__class__') and 'Relationship' in str(value.__class__)):
                # Get start and end nodes
                start_node = value.start_node if hasattr(value, 'start_node') else None
                end_node = value.end_node if hasattr(value, 'end_node') else None
                
                if start_node and end_node:
                    start_id = get_node_id(start_node)
                    end_id = get_node_id(end_node)
                    
                    # Add nodes if not already added
                    if start_id not in added_nodes:
                        start_label = get_node_label(start_node)
                        start_color = get_node_color(start_node)
                        dot.node(start_id, label=start_label, fillcolor=start_color)
                        added_nodes.add(start_id)
                    
                    if end_id not in added_nodes:
                        end_label = get_node_label(end_node)
                        end_color = get_node_color(end_node)
                        dot.node(end_id, label=end_label, fillcolor=end_color)
                        added_nodes.add(end_id)
                    
                    # Add edge
                    rel_label = get_relationship_label(value)
                    edge_key = (start_id, end_id, rel_label)
                    if edge_key not in added_edges:
                        # Only add label if it's not empty
                        if rel_label and rel_label.strip():
                            dot.edge(start_id, end_id, label=rel_label)
                        else:
                            dot.edge(start_id, end_id)
                        added_edges.add(edge_key)
            
            # Check if it's a path (Neo4j Path object)
            elif hasattr(value, 'nodes') and hasattr(value, 'relationships'):
                # It's a Neo4j Path object
                nodes = list(value.nodes)
                relationships = list(value.relationships)
                
                # Add all nodes
                for node in nodes:
                    node_id = get_node_id(node)
                    if node_id not in added_nodes:
                        label = get_node_label(node)
                        color = get_node_color(node)
                        dot.node(node_id, label=label, fillcolor=color)
                        added_nodes.add(node_id)
                
                # Add all relationships
                for i, rel in enumerate(relationships):
                    if i < len(nodes) - 1:
                        start_id = get_node_id(nodes[i])
                        end_id = get_node_id(nodes[i + 1])
                        rel_label = get_relationship_label(rel)
                        edge_key = (start_id, end_id, rel_label)
                        if edge_key not in added_edges:
                            if rel_label and rel_label.strip():
                                dot.edge(start_id, end_id, label=rel_label)
                            else:
                                dot.edge(start_id, end_id)
                            added_edges.add(edge_key)
            
            # Check if it's a list (could contain nodes, relationships, or paths)
            elif isinstance(value, list):
                for item in value:
                    # Check if it's a path
                    if hasattr(item, 'nodes') and hasattr(item, 'relationships'):
                        nodes = list(item.nodes)
                        relationships = list(item.relationships)
                        
                        for node in nodes:
                            node_id = get_node_id(node)
                            if node_id not in added_nodes:
                                label = get_node_label(node)
                                color = get_node_color(node)
                                dot.node(node_id, label=label, fillcolor=color)
                                added_nodes.add(node_id)
                        
                        for i, rel in enumerate(relationships):
                            if i < len(nodes) - 1:
                                start_id = get_node_id(nodes[i])
                                end_id = get_node_id(nodes[i + 1])
                                edge_key = (start_id, end_id, get_relationship_label(rel))
                                if edge_key not in added_edges:
                                    rel_label = get_relationship_label(rel)
                                    dot.edge(start_id, end_id, label=rel_label)
                                    added_edges.add(edge_key)
                    # Check if it's a node
                    elif hasattr(item, 'labels') or (hasattr(item, '__class__') and 'Node' in str(item.__class__)):
                        node_id = get_node_id(item)
                        if node_id not in added_nodes:
                            label = get_node_label(item)
                            color = get_node_color(item)
                            dot.node(node_id, label=label, fillcolor=color)
                            added_nodes.add(node_id)
                    # Check if it's a relationship
                    elif hasattr(item, 'type') or (hasattr(item, '__class__') and 'Relationship' in str(item.__class__)):
                        start_node = item.start_node if hasattr(item, 'start_node') else None
                        end_node = item.end_node if hasattr(item, 'end_node') else None
                        
                        if start_node and end_node:
                            start_id = get_node_id(start_node)
                            end_id = get_node_id(end_node)
                            
                            if start_id not in added_nodes:
                                start_label = get_node_label(start_node)
                                start_color = get_node_color(start_node)
                                dot.node(start_id, label=start_label, fillcolor=start_color)
                                added_nodes.add(start_id)
                            
                            if end_id not in added_nodes:
                                end_label = get_node_label(end_node)
                                end_color = get_node_color(end_node)
                                dot.node(end_id, label=end_label, fillcolor=end_color)
                                added_nodes.add(end_id)
                            
                            rel_label = get_relationship_label(item)
                            edge_key = (start_id, end_id, rel_label)
                            if edge_key not in added_edges:
                                if rel_label and rel_label.strip():
                                    dot.edge(start_id, end_id, label=rel_label)
                                else:
                                    dot.edge(start_id, end_id)
                                added_edges.add(edge_key)
    
    # If no nodes were found, create a simple message node
    if not added_nodes:
        dot.node("no_data", label="No graph data found\\nQuery returned scalar values or empty results", 
                fillcolor="lightgray", shape="note")
        print("Warning: No graph nodes or relationships found in query results.")
        print("Make sure your query returns nodes, relationships, or paths using RETURN * or specific variables.")
    
    # Determine output format from file extension
    file_ext = os.path.splitext(output_path)[1].lower()
    
    if file_ext == '.dot':
        # Save as DOT file
        dot.save(output_path)
    else:
        # Render to image format
        try:
            # GraphViz format (png, pdf, svg, etc.)
            format_type = file_ext[1:] if file_ext else 'png'
            base_path = output_path.replace(file_ext, '')
            
            # Render the graph with high resolution
            # For PNG, the large size attribute (60,40) ensures high resolution
            # This prevents blur when zooming in the UI
            dot.render(base_path, format=format_type, cleanup=True)
            
            # If the rendered file has a different name, rename it
            rendered_path = output_path.replace(file_ext, '') + file_ext
            if rendered_path != output_path and os.path.exists(rendered_path):
                import shutil
                shutil.move(rendered_path, output_path)
        except Exception as e:
            # If rendering fails, save as DOT file
            print(f"Warning: Could not render to {format_type}. Saving as DOT file instead.")
            dot.save(output_path.replace(file_ext, '.dot'))

