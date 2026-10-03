from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class EmailOrUsernameBackend(ModelBackend):
    """Lets users log in with either their username or their email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        user = (
            User.objects.filter(username__iexact=username).first()
            or User.objects.filter(email__iexact=username).first()
        )
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
