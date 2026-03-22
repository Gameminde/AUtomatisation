from flask_login import UserMixin


class User(UserMixin):
    """Flask-Login user object backed by the Supabase 'users' table."""

    def __init__(self, id: str, email: str, is_active: bool = True):
        self.id = id
        self.email = email
        self._is_active = is_active

    @property
    def is_active(self):
        return self._is_active
