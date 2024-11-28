import Levenshtein


def is_identifier(attribute):
    common_identifier_parts = ["PK", "ID", "NK"]
    contains = False
    for field in common_identifier_parts:
        contains = attribute.startswith(field)
        if not contains:
            contains = attribute.endswith(field)
        if contains:
            return contains


def is_foreignkey(attribute):
    common_identifier_parts = ["FK"]
    contains = False
    for field in common_identifier_parts:
        contains = attribute.startswith(field)
        if not contains:
            contains = attribute.endswith(field)
        if contains:
            return contains

def calculate_to_whom_belongs(field, array):
    minimal_difference = 99999
    for element in array:
        difference = Levenshtein.distance(field, element)
        if difference < minimal_difference:
            minimal_difference = difference
    return minimal_difference


def check_field_belongs(field):
    log_identifier_parts = ["case:log", "case:journey", "case:enduser"]
    event_identifier_parts = ["Initiator", "Receiver",
                              "Channel", "DetlaDate", "Duration",
                              "dateOriginated", "dateReceiver",
                              "dateConsumed", "timestamp",
                              "dateCompleted", "Id"]

    actor_identifier_parts = ["Label", "Text", "Comment"]
    identifier = False
    foreign_key = False

    identifier = is_identifier(field)
    foreign_key = is_foreignkey(field)

    similarity_to_actor = calculate_to_whom_belongs(field,
                                                    actor_identifier_parts)

    similarity_to_log = calculate_to_whom_belongs(field,
                                                  log_identifier_parts)

    similarity_to_event = calculate_to_whom_belongs(field,
                                                    event_identifier_parts)
    print(identifier, foreign_key)
    if (similarity_to_actor <= similarity_to_event and similarity_to_actor <= similarity_to_log):
        return "Entity", identifier, foreign_key
    elif (similarity_to_log <= similarity_to_event and similarity_to_log <= similarity_to_actor):
        return "Log", identifier, foreign_key
    else:
        return "Event", identifier, foreign_key
