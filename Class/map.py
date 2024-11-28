import numpy as np
from typing import List
from Functions.StringManipulation import get_value_To_string, check_if_string_is_not_None, remove_case_append
import pandas as pd


class field:
    name: str
    type_map: str
    identifier: bool
    foreign_key: bool
    to_type: str
    entity_type: str

    def __init__(self, name, type_map,
                 identifier, foreign_key,
                 to_type, entity_type=np.nan):
        self.name = name
        self.type_map = type_map
        self.identifier = identifier
        self.foreign_key = foreign_key
        self.to_type = to_type
        self.entity_type = entity_type


class ArrayIterator:
    def __init__(self, array):
        self.array = array
        self.index = 0

    def __iter__(self):
        result = self.array[0]
        self.index = 0
        return result

    def __next__(self):
        if self.index < len(self.array):
            result = self.array[self.index]
            self.index += 1
            return result
        else:
            raise StopIteration


class map:
    dataFields: List[field] = []

    def __init__(self, fields):
        self.dataFields = [e for e in fields]
        self.index = 0

    def __iter__(self):
        print(self.dataFields)
        return ArrayIterator(self.dataFields)

    def get_field_string(self, log):
        log_insert = ""
        first_value = False
        for index, field in enumerate(self.dataFields):
            insertValue = get_value_To_string(log[field.name])

            if check_if_string_is_not_None(insertValue):
                if first_value:
                    log_insert = log_insert + ","

                log_insert = log_insert + f'''{remove_case_append(field.name)}:{insertValue}'''
                first_value = True

        return log_insert

    def get_field_string_from_fields(self, log, fields):
        log_insert = ""
        first_value = False
        for index, field in enumerate(fields):
            insertValue = get_value_To_string(log[field.name])

            if check_if_string_is_not_None(insertValue):
                if first_value:
                    log_insert = log_insert + ","

                log_insert = log_insert + f'''{remove_case_append(field.name)}:{insertValue}'''
                first_value = True

        return log_insert

    def getLength(self):
        return len(self.dataFields)

    def get_primary_keys(self):
        field = [m for m in self.dataFields if m.identifier]
        return map(field)

    def filter_out_mapping_start_with(self, starts_with):
        result = []
        for index in range(self.getLength()):
            if self.dataFields[index].name.startswith(starts_with):
                result.append(self.dataFields[index])
        return map(result)

    def filter_out_mapping_notstart_with(self, starts_with):
        result = []
        for index in range(self.getLength()):
            if not (self.dataFields[index].name.startswith(starts_with)):
                result.append(self.dataFields[index])
        return map(result)

    def get_primary_where(self, log):
        field = self.get_primary_keys()
        return self.get_field_string_from_fields(log, field)

    def check_if_array_has_identifier(self):
        identifiers = self.get_primary_keys()

        if (identifiers.getLength() == 0):
            return True

        return False

    def get_foreign_keys(self, from_type, to_type):
        field = [m for m in self.dataFields if m.foreign_key
                 and m.to_type == to_type]
        return field

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

    def mapping_values_are_defined(self, log):
        calculated_empty_values = 0
        for index in range(self.getLength()):
            if(pd.isnull(log[self.dataFields[index].name])):
                calculated_empty_values = calculated_empty_values + 1
        return calculated_empty_values