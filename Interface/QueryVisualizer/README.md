# Neo4j Query Visualizer

This module provides a graphical interface for executing Neo4j Cypher queries and visualizing the results using GraphViz.

## Features

- Execute Cypher queries against your Neo4j database
- Load queries from `.cypher` files
- Visualize query results as graph diagrams
- Export visualizations in multiple formats (PNG, PDF, SVG, DOT)

## Usage

### Standalone Script

Run the standalone query visualizer:

```bash
python query_visualizer.py
```

This will:
1. Prompt you to connect to your Neo4j database
2. Open the query visualizer interface
3. Allow you to enter or load a Cypher query
4. Generate and save a GraphViz visualization

### Integration

You can also integrate the visualizer into your own code:

```python
from Interface.QueryVisualizer.QueryVisualizerUI import QueryVisualizerUI
from Connection.Neo4jConnection import Neo4jConnection
import tkinter as tk

# Create connection
connector = Neo4jConnection(uri, username, password)

# Create visualizer UI
root = tk.Tk()
visualizer = QueryVisualizerUI(root, connector)
root.mainloop()
```

## Query Requirements

For best visualization results, your Cypher queries should return:
- Nodes (e.g., `MATCH (n) RETURN n`)
- Relationships (e.g., `MATCH (a)-[r]->(b) RETURN a, r, b`)
- Paths (e.g., `MATCH path = (a)-[*]->(b) RETURN path`)
- Or use `RETURN *` to return all matched elements

## Output Formats

The visualizer supports the following output formats:
- **PNG** - Raster image (default)
- **PDF** - Vector format, good for printing
- **SVG** - Scalable vector graphics
- **DOT** - GraphViz source format (editable)

## Node Colors

Nodes are automatically colored based on their labels:
- **Event** - Light blue
- **Touchpoint** - Light green
- **Entity** - Light yellow
- **Journey** - Light coral
- **Log** - Light pink
- **Channel** - Light gray
- **Experience** - Plum
- **Object** - Wheat

## Requirements

- Python 3.x
- graphviz Python package (`pip install graphviz`)
- GraphViz system installation (for rendering images)
  - Windows: Download from https://graphviz.org/download/
  - macOS: `brew install graphviz`
  - Linux: `sudo apt-get install graphviz` or `sudo yum install graphviz`

## Troubleshooting

### GraphViz not found
If you get an error about GraphViz not being found, you need to install the GraphViz system package. The Python `graphviz` package is just a wrapper - you also need the actual GraphViz binaries installed on your system.

### No visualization generated
If your query returns scalar values (numbers, strings) instead of graph elements, the visualizer will show a message. Make sure your query returns nodes, relationships, or paths.

