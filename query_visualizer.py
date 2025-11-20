"""
Standalone script to run Neo4j queries and visualize results with GraphViz
"""
import tkinter as tk
from Interface.Connection.ConnectionUI import ConnectionUI
from Interface.QueryVisualizer.QueryVisualizerUI import QueryVisualizerUI


def main():
    # First, get Neo4j connection
    master = tk.Tk()
    connectUI = ConnectionUI(master)
    master.mainloop()
    
    # Check if connection was established
    try:
        connector = connectUI.get_connector()
    except AttributeError:
        print("Connection was not established. Exiting.")
        return
    
    # Open query visualizer
    master = tk.Tk()
    visualizer = QueryVisualizerUI(master, connector)
    master.mainloop()
    
    # Close connection when done
    connector.close()


if __name__ == "__main__":
    main()

