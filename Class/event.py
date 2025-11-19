from Functions.StringManipulation import get_value_To_string, check_if_string_is_not_None, remove_case_append
from Class.map import map, ArrayIterator


class touchpoint(map):
    def __init__(self, fields):
        super().__init__(fields)

    def __iter__(self):
        return ArrayIterator(self.dataFields)
