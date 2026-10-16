from Class.map import map, ArrayIterator
from Functions.StringManipulation import get_value_To_string, check_if_string_is_not_None, remove_case_append


class objects(map):
    def __init__(self, fields):
        super().__init__(fields)

    def __iter__(self):
        return ArrayIterator(self.dataFields)

    def get_field_string(self, log, index=0):
        log_insert = ""
        first_value = False
        internal = False
        for ind, field in enumerate(self.dataFields):
            if(len(log[field.name]) >1):
                insertValue = get_value_To_string(log[field.name]["children"][index][1])
                internal = True
                if check_if_string_is_not_None(insertValue):
                    if first_value:
                        log_insert = log_insert + ","

                    log_insert = log_insert + f'''{remove_case_append(field.name)}:{insertValue}'''
                    first_value = True
            else:
                insertValue = super().get_value_To_string(log[field.name])

                if check_if_string_is_not_None(insertValue):
                    if first_value:
                        log_insert = log_insert + ","

                    log_insert = log_insert + f'''{remove_case_append(field.name)}:{insertValue}'''
                    first_value = True
        return log_insert, (index + 1 if internal else None)
