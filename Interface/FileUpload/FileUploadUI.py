from tkinter import Button, Label, filedialog
import os


class FileUploadUI:
    def __init__(self, master):
        self.fileToRead = ""  # Initialize to empty string in case user exits without selecting
        self.createMainWindow(master)
        master.minsize(100,100)

    def createDialog(self, master):
        self.fileToRead = filedialog.askopenfilename(initialdir=os.getcwd(),
                                                     title="Select file",
                                                     filetypes=(("XES files", ["*.xes", "*.XES"]),
                                                                ("CSV files", ["*.csv", "*.CSV"]),
                                                                ("all files", "*.*")))
        if self.fileToRead != "":
            master.destroy()

    def closeWindow(self, window):
        window.destroy()

    def createMainWindow(self, master):
        master.title("Integrator log upload")
        self.label = Label(master, text="Please select XES or CSV file")
        self.label.grid(row=0, columnspan=3)
        self.button_file_explorer = Button(master, text="Browse files",
                                           command=lambda: self.createDialog(master))
        self.button_file_explorer.grid(sticky='nesw', row=1,
                                       columnspan=12, column=0, pady=10)
        self.button_exit = Button(master, text="Exit",
                                  command=lambda: self.closeWindow(master))
        self.button_exit.grid(sticky='nesw', row=2, columnspan=12, column=0)

    def getFileLocation(self):
        return self.fileToRead

    def getFileName(self):
        return os.path.basename(self.fileToRead)
    
    def isCsvFile(self):
        """Check if the selected file is a CSV file"""
        if self.fileToRead == "":
            return False
        return self.fileToRead.lower().endswith('.csv')
    
    def isXesFile(self):
        """Check if the selected file is an XES file"""
        if self.fileToRead == "":
            return False
        return self.fileToRead.lower().endswith('.xes')
