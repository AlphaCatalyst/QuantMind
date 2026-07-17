class FreshValidationError(Exception):
    error_code = "FRESH_VALIDATION_ERROR"


class FreshValidationNotMature(FreshValidationError):
    error_code = "FRESH_VALIDATION_NOT_MATURE"
