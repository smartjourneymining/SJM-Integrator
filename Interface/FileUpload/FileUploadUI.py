from tkinter import Button, Label, filedialog


class FileUploadUI:
    def __init__(self, master):
        self.createMainWindow(master)
        master.minsize(100,100)

    def createDialog(self, master):
        self.fileToRead = filedialog.askopenfilename(initialdir="/",
                                                     title="Select file",
                                                     filetypes=(("XES files", "*.XES"),
                                                                ("Comma-Separated Vlues", "*.CSV"),
                                                                ("all files", "*.*")))
        if self.fileToRead != "":
            master.destroy()

    def closeWindow(self, window):
        window.destroy()

    def createMainWindow(self, master):
        master.title("Integrator log upload")
        self.label = Label(master, text="Please select XES file")
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
        return self.fileToRead.split("/")[-1]
