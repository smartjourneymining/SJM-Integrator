from tkinter import Label, Button, Entry, Checkbutton, BooleanVar
from Connection.Neo4jConnection import Neo4jConnection
import os
import subprocess


class ConnectionUI:
    def __init__(self, master):
        self.entryBox = []
        self.master = master
        master.title("Connection to Neo4j server")
        self.label = Label(master, text="Enter credentials to connect to Neo4j server")
        self.label.grid(row=0, columnspan=3)

        self.create_uri_field(master)
        self.create_entry_field(master=master, textForDisplay="Username",
                                row=3, column=0, text="neo4j")

        self.create_entry_field(master=master, textForDisplay="Password",
                                row=3, column=2, symbols="*", text="")

        # Add checkbox for cleaning database (after username/password fields)
        self.clean_database_var = BooleanVar()
        self.clean_database_var.set(False)  # Default to False (don't clean)
        self.clean_database_checkbox = Checkbutton(
            master, 
            text="Clean database before processing",
            variable=self.clean_database_var
        )
        self.clean_database_checkbox.grid(row=5, column=0, columnspan=3, pady=5, sticky="w")

        self.Button = Button(master, text="Connect",
                             command=lambda: self.establishConnection(master))

        self.Button.grid(row=6, column=0, columnspan=3, pady=10)

        master.minsize(100,100)

    def establishConnection(self, master):
        if (self.validate_url()):
            self.connector = Neo4jConnection(self.Uri.get(),
                                             self.entryBox[0].get(),
                                             self.entryBox[1].get())

            if (self.connector.check_connection() is True):
                if (self.connector.check_authentification() is False):
                    print("Authentication credentials are invalid")
                else:
                    master.destroy()
            else:
                print("Connection cannot be established")

    def validate_url(self):
        return self.Uri.get().startswith(("neo4j",
                                          "neo4j+s",
                                          "bolt",
                                          "bolt+s",
                                          "neo4j+ssc",
                                          "bolt+ssc"))

    def create_entry_field(self, textForDisplay, master, row, column, symbols="", text= ""):
        label = Label(master, text=textForDisplay)
        label.grid(row=row, column=column)

        entryBox = Entry(master, show=symbols)
        entryBox.insert(0, text)
        entryBox.grid(row=row+1, column=column)

        self.entryBox.append(entryBox)

    def is_running_in_wsl(self):
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

    def get_windows_host_ip(self):
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

    def create_uri_field(self, master):
        self.UriLable = Label(master, text="Uri to Neo4j")
        self.UriLable.grid(row=1, columnspan=3, column=0)
        
        self.Uri = Entry(master)
        
        # Only apply Windows IP workaround if running in WSL
        default_uri = "bolt://localhost:7687"  # Default for native Windows/Linux
        if self.is_running_in_wsl():
            windows_ip = self.get_windows_host_ip()
            if windows_ip:
                default_uri = f"bolt://{windows_ip}:7687"
                print(f"Detected WSL environment. Using Windows host IP: {windows_ip}")
            else:
                print("Warning: Running in WSL but could not determine Windows host IP. Using localhost.")
        
        self.Uri.insert(0, default_uri)
        
        self.Uri.grid(row=2, columnspan=3, column=0)

    def get_connector(self):
        return self.connector
    
    def should_clean_database(self):
        """Return True if the user wants to clean the database before processing"""
        return self.clean_database_var.get()
