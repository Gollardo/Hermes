class ImportDecisionError(Exception):
    def __init__(self, row: int, cause: Exception):
        self.row = row
        self.cause = cause
        super().__init__(str(cause))
