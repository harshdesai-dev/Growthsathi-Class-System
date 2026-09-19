from django.contrib.auth.tokens import PasswordResetTokenGenerator


class AccountTokenGenerator(PasswordResetTokenGenerator):
    def __init__(self, purpose):
        super().__init__()
        self.key_salt = f"growthsathi.account.{purpose}"

    def _make_hash_value(self, user, timestamp):
        return super()._make_hash_value(user, timestamp) + user.status + str(user.institute_id)


activation_tokens = AccountTokenGenerator("activation")
reset_tokens = AccountTokenGenerator("password-reset")
