
from tkinter import Button, Canvas, Checkbutton, Frame, IntVar, Label, Scrollbar, filedialog
from tkinter.ttk import Combobox
from Class.map import field
from AutoMapper.autoMapper import check_field_belongs
from Class.log import log
from Class.event import touchpoint
from Class.objects import objects
# sort out scrolling
import json


class Mapper:
    def __init__(self, master, mappingFor, fields):
        self.entryBox = []
        self.attributes = []
        self.attribute_owner = []
        self.attribute_identifier = []
        self.attribute_foreign_identifier = []
        self.attribute_foreign_owner = []
        self.attribute_actor_field = []

        self.master = master
        master.title("XSS field mapping" )
        master.columnconfigure(0, weight=1)
        master.columnconfigure(1, weight=1)
        master.rowconfigure(0, weight=1)
        self.label = Label(master, text="Fields")
        self.label.pack()
        self.frame = Frame(master, height=1500)
        self.frame.pack(side="top", fill="x")
        self.createTable(self.frame, fields)

        self.import_setings = Button(self.master,
                                     text="Import settings",
                                     command=lambda:
                                     self.import_setings_from_file(master))

        self.Finish = Button(self.master,
                             text="Finish",
                             command=lambda:
                             self.convert_inputs_to_object(master))
        self.Finish.pack()
        self.import_setings.pack()
        master.geometry("{}x{}".format(1000, 800))
        master.minsize(1000,800)

    def import_setings_from_file(self, master):
        self.fileToRead = filedialog.askopenfilename(initialdir="/",
                                                     title="Select file",
                                                     filetypes=[("Json", '*.json'),
                                                                ("All files", "*.*")])

        if self.fileToRead != "":
            with open(self.fileToRead, "r") as outfile:
                file_content = outfile.read()
            json_parse = json.loads(file_content)
            self.converted = {}
            actor = [field(**e) for e in json_parse["Actor"]]
            event = [field(**e) for e in json_parse["Event"]]
            logs = [field(**e) for e in json_parse["Log"]]
            rating = [field(**e) for e in json_parse["Rating"]]
            objFields = [field(**e) for e in json_parse["Object"]]

            self.actor = touchpoint(actor)
            self.event = touchpoint(event)
            self.logs = log(logs)
            self.rating = touchpoint(rating)
            self.objects = objects(objFields)
        master.destroy()

    def create_labels(self, select_frame):
        Label(select_frame, text="Field name").grid(row=0,
                                                    column=0,
                                                    sticky='nsew',
                                                    padx=20)

        Label(select_frame, text="Property of").grid(row=0,
                                                     column=1,
                                                     sticky='nsew',
                                                     padx=20)

        Label(select_frame, text="Identifier").grid(row=0,
                                                    column=2,
                                                    sticky='we',
                                                    padx=20)

        Label(select_frame, text="Foreign key").grid(row=0,
                                                     column=3,
                                                     sticky='we',
                                                     padx=20)

        Label(select_frame, text="Key relates to").grid(row=0,
                                                        column=4,
                                                        sticky='we',
                                                        padx=20)

        Label(select_frame, text="Relates to type of actor").grid(row=0,
                                                                  column=5,
                                                                  sticky='we',
                                                                  padx=20)

    def create_dropdown(self, select_frame, text, column, rowVisualization, setValue=""):
        values = ["",
                  "Actor",
                  "Event",
                  "Log",
                  "Rating",
                  "Object"]

        dropDown = Combobox(select_frame,  state="readonly", values=values)
        print("ID: "+str(values.index(setValue)))

        dropDown.set(text)
        dropDown.current(values.index(setValue))
        dropDown.grid(row=rowVisualization, column=column, padx=20)
        dropDown.grid_remove()
        return dropDown

    def create_checkbutton(self, select_frame, text, column, row, checked):
        c_v1 = IntVar()
        c_v1.set(1 if checked else 0)
        ChkBttn = Checkbutton(select_frame,
                              text=text,
                              variable=c_v1,
                              onvalue=1,
                              offvalue=0)

        ChkBttn.grid(row=row, column=column, padx=20)
        return ChkBttn, c_v1

    def create_sorting_fame(self, select_frame, fields):
        row = 1
        for line in fields:
            field_type, identifier, foreign_key = check_field_belongs(line)
            text = Label(select_frame, text=line)
            text.grid(row=row, column=0, padx=20)
            self.attributes.append(text)

            dropDown = self.create_dropdown(select_frame,
                                            "Field belongs",
                                            1,
                                            row,
                                            field_type)
            dropDown.grid()
            self.attribute_owner.append(dropDown)

            bttn, c_v1 = self.create_checkbutton(select_frame,
                                                 "Identifier",
                                                 2,
                                                 row,
                                                 identifier)
            self.attribute_identifier.append(c_v1)

            dropDown2 = self.create_dropdown(select_frame,
                                             "Field belongs",
                                             4,
                                             row)
            self.attribute_foreign_owner.append(dropDown2)

            bttn2, c_v2 = self.create_checkbutton(select_frame,
                                                  "Foreign key",
                                                  3,
                                                  row,
                                                  foreign_key)

            bttn2.configure(command=lambda id=row:
                            self.enableForeigKeyDropDown(id-1))

            self.attribute_foreign_identifier.append(c_v2)

            actorTypefield = Combobox(select_frame,
                                      state="readonly",
                                      values=["Sender",
                                              "Receiver",
                                              "Both"])

            actorTypefield.set("Field belongs")
            actorTypefield.grid(row=row, column=5, padx=20)
            actorTypefield.grid_remove()
            self.attribute_actor_field.append(actorTypefield)

            dropDown2.bind('<<ComboboxSelected>>',
                           lambda event, entry=dropDown,
                           entry2=dropDown2, actor=actorTypefield:
                           self.enable_receiver_sender_dropdown(entry,
                                                                entry2,
                                                                actor))

            dropDown.bind('<<ComboboxSelected>>',
                          lambda event, entry=dropDown,
                          entry2=dropDown2, actor=actorTypefield:
                          self.enable_receiver_sender_dropdown(entry,
                                                               entry2,
                                                               actor))

            row = row + 1

    def createTable(self, master, fields):
        row = 1
        frame = Frame(master, height=1500)
        frame.pack(side="top", fill="x")
        frame.columnconfigure(0, weight="1")
        frame.rowconfigure(0, weight="1")
        frame.rowconfigure(1, minsize="700")

        self.canvas = Canvas(frame)
        select_frame = Frame(master)
        self.canvas.grid(row=1, columnspan=6, rowspan=10, sticky='nswe')
        self.canvas.create_window((0, 0), window=select_frame,  anchor='nw')

        select_frame.config()
        self.create_labels(select_frame)
        self.create_sorting_fame(select_frame, fields)

        sbb = Scrollbar(frame,  orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sbb.set)
        select_frame.bind("<Configure>", self.onFrameConfigure)
        sbb.grid(row=1, column=6, rowspan=row, sticky="nsew")

    def onFrameConfigure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def enable_receiver_sender_dropdown(self, row, entry2, actor):
        if (not actor.winfo_ismapped()) and (row.get() == "Actor"
                                             or entry2.get() == "Actor"):
            actor.grid()
        elif actor.winfo_ismapped() and not (row.get() == "Actor"
                                             or entry2.get() == "Actor"):
            actor.grid_remove()

    def enableForeigKeyDropDown(self, row):
        if not self.attribute_foreign_owner[row].winfo_ismapped():
            self.attribute_foreign_owner[row].grid()
        else:
            self.attribute_foreign_owner[row].grid_remove()

    def convert_inputs_to_object(self, master):
        self.converted = {}
        self.converted["Actor"] = []
        self.converted["Event"] = []
        self.converted["Log"] = []
        self.converted["Rating"] = []
        self.converted["Object"] = []

        for i in range(0, len(self.attributes)):
            place = self.attribute_owner[i].get()
            if place != "":
                mapping = field(self.attributes[i].cget("text"),
                                self.attribute_owner[i].get(),
                                self.attribute_identifier[i].get(),
                                self.attribute_foreign_identifier[i].get(),
                                self.attribute_foreign_owner[i].get(),
                                self.attribute_actor_field[i].get())
                if self.converted[i].name == "log":
                    self.converted[place] = log(mapping)
                else:
                    self.converted[place] = touchpoint(mapping)

        structure = {
            'Actor': [elem.__dict__ for elem in self.converted["Actor"]],
            'Event': [elem.__dict__ for elem in self.converted["Event"]],
            'Log': [elem.__dict__ for elem in self.converted["Log"]],
            'Rating': [elem.__dict__ for elem in self.converted["Rating"]],
            'Object': [elem.__dict__ for elem in self.converted["Object"]]
        }
        with open("settings.json", "w") as outfile:
            json.dump(structure, outfile)
        master.destroy()
