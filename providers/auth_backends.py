from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)

        if not username or password is None:
            return None

        UserModel = get_user_model()
        user = UserModel._default_manager.filter(
            **{f"{UserModel.USERNAME_FIELD}__iexact": username}
        ).first()
        if user is None:
            user = UserModel._default_manager.filter(
                **{f"{UserModel.EMAIL_FIELD}__iexact": username}
            ).first()

        if user is None:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
