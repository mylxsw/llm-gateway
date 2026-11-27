"""Integer boundaries shared by every financial entry point."""
class BillingError(Exception):
    def __init__(self, code, status=403):
        self.code, self.status = code, status
        super().__init__(code)


def integer(value, minimum=0, maximum=2**63-1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise BillingError('amount_out_of_range', 400)
    return value
