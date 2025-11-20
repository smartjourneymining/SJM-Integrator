from tkinter import ttk, scrolledtext, Button, Label, Frame, messagebox, filedialog, Canvas
from Connection.Neo4jConnection import Neo4jConnection
from PIL import Image, ImageTk
import os
import tempfile
import subprocess
import platform


class QueryVisualizerUI:
    def __init__(self, master, connector: Neo4jConnection):
        self.master = master
        self.connector = connector
        self.current_image = None
        self.current_photo = None
        self.current_records = None  # Store query results for saving
        
        # Zoom and pan state
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False
        self.image_item = None
        
        master.title("Neo4j Query Visualizer")
        
        # Create paned window for resizable split
        paned = ttk.PanedWindow(master, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Left panel - Query input
        left_frame = Frame(paned)
        paned.add(left_frame, weight=1)
        
        # Query input section
        query_label = Label(left_frame, text="Cypher Query:")
        query_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        self.query_text = scrolledtext.ScrolledText(left_frame, height=15, width=50)
        self.query_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Load query from file button
        load_frame = Frame(left_frame)
        load_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        load_button = Button(load_frame, text="Load Query from File", command=self.load_query_from_file)
        load_button.pack(side="left", padx=(0, 10))
        
        # Execute and visualize button
        execute_button = Button(load_frame, text="Execute & Visualize", command=self.execute_and_visualize)
        execute_button.pack(side="left")
        
        # Save button (initially disabled)
        self.save_button = Button(load_frame, text="Save Visualization", command=self.save_visualization, state="disabled")
        self.save_button.pack(side="left", padx=(10, 0))
        
        # Status label
        self.status_label = Label(left_frame, text="Ready", fg="green")
        self.status_label.pack(anchor="w", padx=10, pady=(5, 10))
        
        # Right panel - Visualization display
        right_frame = Frame(paned)
        paned.add(right_frame, weight=2)
        
        # Visualization label and controls
        viz_header = Frame(right_frame)
        viz_header.pack(fill="x", padx=10, pady=(10, 5))
        
        viz_label = Label(viz_header, text="Visualization:")
        viz_label.pack(side="left")
        
        # Zoom controls
        zoom_frame = Frame(viz_header)
        zoom_frame.pack(side="right")
        
        Label(zoom_frame, text="Zoom:").pack(side="left", padx=(0, 5))
        Button(zoom_frame, text="+", command=self.zoom_in, width=3).pack(side="left", padx=2)
        Button(zoom_frame, text="-", command=self.zoom_out, width=3).pack(side="left", padx=2)
        Button(zoom_frame, text="Reset", command=self.zoom_reset, width=6).pack(side="left", padx=2)
        Button(zoom_frame, text="Fit", command=self.zoom_fit, width=6).pack(side="left", padx=2)
        
        # Create canvas with scrollbars for the visualization
        canvas_frame = Frame(right_frame)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Canvas for displaying the image
        self.canvas = Canvas(canvas_frame, bg="white", highlightthickness=1, highlightbackground="gray")
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        
        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid layout for canvas and scrollbars
        self.canvas.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        
        # Bind mouse events for zoom and pan
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)  # Windows/Mac
        self.canvas.bind("<Button-4>", self._on_mousewheel)  # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_mousewheel)  # Linux scroll down
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        
        # Make canvas focusable for keyboard events
        self.canvas.focus_set()
        self.canvas.bind("<Control-MouseWheel>", self._on_zoom_wheel)  # Ctrl+Wheel for zoom
        self.canvas.bind("<Control-Button-4>", self._on_zoom_wheel)  # Linux
        self.canvas.bind("<Control-Button-5>", self._on_zoom_wheel)  # Linux
        
        master.minsize(1200, 600)

    def load_query_from_file(self):
        """Load a Cypher query from a file"""
        file_path = filedialog.askopenfilename(
            title="Select Cypher Query File",
            filetypes=[("Cypher files", "*.cypher"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    query = f.read()
                    self.query_text.delete(1.0, "end")
                    self.query_text.insert(1.0, query)
                    self.status_label.config(text=f"Loaded query from {os.path.basename(file_path)}", fg="green")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {str(e)}")
                self.status_label.config(text="Error loading file", fg="red")

    def execute_and_visualize(self):
        """Execute the query and create a GraphViz visualization"""
        query = self.query_text.get(1.0, "end-1c").strip()
        
        if not query:
            messagebox.showwarning("Warning", "Please enter a Cypher query")
            return
        
        try:
            self.status_label.config(text="Executing query...", fg="blue")
            self.master.update()
            
            # Execute query
            with self.connector.driver.session() as session:
                records = self.connector.execute_query(session, query)
            
            if not records:
                messagebox.showinfo("Info", "Query executed successfully but returned no results")
                self.status_label.config(text="Query executed - no results", fg="orange")
                self.clear_visualization()
                return
            
            self.status_label.config(text="Creating visualization...", fg="blue")
            self.master.update()
            
            # Create visualization in temporary file
            # Use SVG format for vector graphics - no blur at any zoom level!
            from Functions.GraphVizVisualizer import create_graphviz_visualization
            
            with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as tmp_file:
                temp_path = tmp_file.name
            
            try:
                create_graphviz_visualization(records, temp_path)
                
                # Store records for potential saving later
                self.current_records = records
                
                # Display the visualization in the canvas (loads image into memory)
                self.display_visualization(temp_path)
                
                # Clean up temp file after image is loaded into memory
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except:
                    pass
                
                self.status_label.config(text="Visualization created successfully", fg="green")
                self.save_button.config(state="normal")
                
            except Exception as viz_error:
                # Clean up temp file on error
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except:
                    pass
                raise viz_error
                
        except Exception as e:
            error_msg = str(e)
            messagebox.showerror("Error", f"Failed to execute query or create visualization:\n{error_msg}")
            self.status_label.config(text="Error occurred", fg="red")
            self.clear_visualization()
            print(f"Error: {error_msg}")
    
    def display_visualization(self, image_path):
        """Display the visualization image in the canvas"""
        try:
            # Check if it's SVG - convert to high-res PNG for display
            if image_path.lower().endswith('.svg'):
                try:
                    # Try using cairosvg for SVG to PNG conversion
                    import cairosvg
                    from io import BytesIO
                    
                    # Convert SVG to high-resolution PNG (300 DPI for crisp rendering)
                    png_data = cairosvg.svg2png(
                        url=image_path, 
                        dpi=300,
                        output_width=6000  # Very high resolution to prevent blur
                    )
                    
                    # Create PIL Image from PNG data
                    img = Image.open(BytesIO(png_data))
                except ImportError:
                    # Fallback: use PIL with svglib if cairosvg not available
                    try:
                        from svglib.svglib import svg2rlg
                        from reportlab.graphics import renderPM
                        from io import BytesIO
                        
                        drawing = svg2rlg(image_path)
                        png_data = renderPM.drawToString(drawing, fmt='PNG', dpi=300)
                        img = Image.open(BytesIO(png_data))
                    except ImportError:
                        # Last resort: regenerate as high-res PNG
                        messagebox.showwarning(
                            "SVG Support", 
                            "SVG rendering requires cairosvg or svglib.\n"
                            "Falling back to PNG format.\n\n"
                            "For best quality, install: pip install cairosvg"
                        )
                        from Functions.GraphVizVisualizer import create_graphviz_visualization
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                            png_path = tmp_file.name
                        create_graphviz_visualization(self.current_records, png_path)
                        img = Image.open(png_path)
                        try:
                            os.unlink(png_path)
                        except:
                            pass
            else:
                # Load regular image formats
                img = Image.open(image_path)
            
            # Store original image
            self.current_image = img.copy()
            
            # Reset zoom and pan
            self.zoom_level = 1.0
            self.pan_x = 0
            self.pan_y = 0
            
            # Update display
            self._update_display()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to display visualization: {str(e)}")
            self.clear_visualization()
    
    def _update_display(self):
        """Update the canvas display with current zoom and pan"""
        if not self.current_image:
            return
        
        try:
            # Calculate display size based on zoom
            img_width, img_height = self.current_image.size
            display_width = int(img_width * self.zoom_level)
            display_height = int(img_height * self.zoom_level)
            
            # Resize image for display using high-quality resampling
            # Use LANCZOS for downscaling, NEAREST for upscaling to preserve sharpness
            if self.zoom_level > 1.0:
                # When zooming in, use LANCZOS for better quality
                display_img = self.current_image.resize((display_width, display_height), Image.Resampling.LANCZOS)
            elif self.zoom_level < 1.0:
                # When zooming out, also use LANCZOS
                display_img = self.current_image.resize((display_width, display_height), Image.Resampling.LANCZOS)
            else:
                display_img = self.current_image
            
            # Convert to PhotoImage
            self.current_photo = ImageTk.PhotoImage(display_img)
            
            # Clear canvas and add image at pan position
            self.canvas.delete("all")
            self.image_item = self.canvas.create_image(
                self.pan_x, self.pan_y, 
                anchor="nw", 
                image=self.current_photo
            )
            
            # Update scroll region to allow scrolling
            bbox = self.canvas.bbox("all")
            if bbox:
                self.canvas.config(scrollregion=bbox)
            
        except Exception as e:
            print(f"Error updating display: {e}")
    
    def clear_visualization(self):
        """Clear the visualization from the canvas"""
        self.canvas.delete("all")
        self.current_image = None
        self.current_photo = None
        self.current_records = None
        self.image_item = None
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.is_dragging = False
        self.save_button.config(state="disabled")
    
    def save_visualization(self):
        """Save the current visualization to a file"""
        if not self.current_records:
            messagebox.showwarning("Warning", "No visualization to save")
            return
        
        output_path = filedialog.asksaveasfilename(
            title="Save Visualization",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("PDF files", "*.pdf"), ("SVG files", "*.svg"), ("DOT files", "*.dot")]
        )
        
        if output_path:
            try:
                from Functions.GraphVizVisualizer import create_graphviz_visualization
                
                # Recreate the visualization with the original query results
                create_graphviz_visualization(self.current_records, output_path)
                self.status_label.config(text=f"Visualization saved to {os.path.basename(output_path)}", fg="green")
                
                # Ask if user wants to open the file
                if messagebox.askyesno("Success", "Visualization saved successfully!\n\nWould you like to open it?"):
                    self.open_file(output_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save visualization: {str(e)}")
    
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling on canvas (pan)"""
        # Windows and Mac
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")
    
    def _on_zoom_wheel(self, event):
        """Handle Ctrl+MouseWheel for zooming"""
        if not self.current_image:
            return
        
        # Get mouse position relative to canvas
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # Determine zoom direction
        if platform.system() == "Windows":
            delta = event.delta
        else:
            delta = 120 if event.num == 4 else -120
        
        # Zoom factor
        zoom_factor = 1.1 if delta > 0 else 0.9
        new_zoom = self.zoom_level * zoom_factor
        
        # Limit zoom range
        if 0.1 <= new_zoom <= 5.0:
            # Calculate zoom center relative to image
            old_img_x = (canvas_x - self.pan_x) / self.zoom_level
            old_img_y = (canvas_y - self.pan_y) / self.zoom_level
            
            self.zoom_level = new_zoom
            
            # Adjust pan to keep zoom center in place
            new_img_x = old_img_x * self.zoom_level
            new_img_y = old_img_y * self.zoom_level
            self.pan_x = canvas_x - new_img_x
            self.pan_y = canvas_y - new_img_y
            
            self._update_display()
    
    def _on_canvas_click(self, event):
        """Handle mouse click for starting drag"""
        if self.current_image:
            self.is_dragging = True
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            self.canvas.config(cursor="hand2")
    
    def _on_canvas_drag(self, event):
        """Handle mouse drag for panning"""
        if self.is_dragging and self.current_image:
            # Calculate delta
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y
            
            # Update pan position
            self.pan_x += dx
            self.pan_y += dy
            
            # Update drag start position
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            
            self._update_display()
    
    def _on_canvas_release(self, event):
        """Handle mouse release"""
        self.is_dragging = False
        self.canvas.config(cursor="")
    
    def _on_canvas_motion(self, event):
        """Handle mouse motion (for cursor changes)"""
        if self.current_image:
            self.canvas.config(cursor="hand2" if self.is_dragging else "")
    
    def zoom_in(self):
        """Zoom in on the visualization"""
        if self.current_image:
            self.zoom_level = min(self.zoom_level * 1.2, 5.0)
            self._update_display()
    
    def zoom_out(self):
        """Zoom out on the visualization"""
        if self.current_image:
            self.zoom_level = max(self.zoom_level / 1.2, 0.1)
            self._update_display()
    
    def zoom_reset(self):
        """Reset zoom to 100%"""
        if self.current_image:
            self.zoom_level = 1.0
            self.pan_x = 0
            self.pan_y = 0
            self._update_display()
    
    def zoom_fit(self):
        """Fit the image to canvas"""
        if not self.current_image:
            return
        
        self.canvas.update()
        canvas_width = max(self.canvas.winfo_width(), 100)
        canvas_height = max(self.canvas.winfo_height(), 100)
        
        img_width, img_height = self.current_image.size
        
        # Calculate scale to fit
        scale_w = canvas_width / img_width
        scale_h = canvas_height / img_height
        self.zoom_level = min(scale_w, scale_h) * 0.95  # 95% to add some padding
        
        # Center the image
        display_width = int(img_width * self.zoom_level)
        display_height = int(img_height * self.zoom_level)
        self.pan_x = (canvas_width - display_width) / 2
        self.pan_y = (canvas_height - display_height) / 2
        
        self._update_display()

    def open_file(self, file_path):
        """Open a file using the system's default application"""
        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(file_path)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", file_path])
            else:  # Linux
                subprocess.run(["xdg-open", file_path])
        except Exception as e:
            messagebox.showwarning("Warning", f"Could not open file automatically: {str(e)}\n\nFile saved at: {file_path}")

