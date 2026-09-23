class ImportDecisionError(Exception):
    def __init__(self, row: int, cause: Exception):
        self.row = row
        self.cause = cause
        super().__init__(str(cause))


class ImportGroupingError(ValueError):
    """Selected rows cannot form the explicitly reviewed plan group."""
