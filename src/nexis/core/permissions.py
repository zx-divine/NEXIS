from nexis.core.results import Risk


class Permissions:
    def __init__(self, confirm=None, confirm_low=False):
        self.confirm = confirm or (lambda preview: False)
        self.confirm_low = confirm_low

    def authorise(self, preview):
        if preview.risk >= Risk.MEDIUM or self.confirm_low:
            return bool(self.confirm(preview))
        return True
