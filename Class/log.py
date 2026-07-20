from Functions.StringManipulation import get_value_To_string, check_if_string_is_not_None, remove_case_append
from Class.map import map, ArrayIterator


class log(map):
    def __init__(self, fields):
        super().__init__(fields)

    def __iter__(self):
        return ArrayIterator(self.dataFields)

    def get_range_field_string(self, log):
        log_insert = ""
        first_value = False
        for index in range(self.getLength()):
            insertValue = get_value_To_string(log[self.dataFields[index].name])

            if check_if_string_is_not_None(insertValue):
                if first_value:
                    log_insert = log_insert + ","

                log_insert = log_insert + f'''{remove_case_append(self.dataFields[index].name)}:{insertValue}'''
                first_value = True

        return log_insert
