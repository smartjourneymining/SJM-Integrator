from tkinter import Label, Button, Entry
from Connection.Neo4jConnection import Neo4jConnection


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

        self.Button = Button(master, text="Connect",
                             command=lambda: self.establishConnection(master))

        self.Button.grid(row=5, column=0, columnspan=3, pady=10)

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

    def create_uri_field(self, master):
        self.UriLable = Label(master, text="Uri to Neo4j")
        self.UriLable.grid(row=1, columnspan=3, column=0)
        
        self.Uri = Entry(master)
        self.Uri.insert(0,"bolt://localhost:7687")
        
        self.Uri.grid(row=2, columnspan=3, column=0)

    def get_connector(self):
        return self.connector
