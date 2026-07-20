class Xes:
    def __init__(self):
        self.Header = ""
        self.extension =""
        self.Global = []
        self.Trace = []


class Trace:
    def __init__(self):
        self.attributes = []
        self.event =[]


class Global:
    def __init__(self):
        self.scope = ""
        self.attributes = []

class Event:
    def __init__(self):
        self.attributes = []

class Attribute: 
    def __init__(self):
        self.type = ""
        self.value = ""
        self.key = ""
    def __init__(self,type,value,key):
        self.type = type
        self.value = value
        self.key = key