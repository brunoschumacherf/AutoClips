from cryptography.fernet import Fernet
from django.conf import settings
from django.db import transaction

from accounts.models import Workspace
from subscriptions.services import LimitExceeded, plan_for
from .models import SocialAccount


def cipher():
    return Fernet(settings.OAUTH_ENCRYPTION_KEY.encode())


@transaction.atomic
def connect(workspace, external_id, label, refresh_token):
    workspace = Workspace.objects.select_for_update().get(pk=workspace.pk)
    accounts = SocialAccount.objects.filter(workspace=workspace)
    if not accounts.filter(provider="youtube", external_id=external_id).exists() and accounts.count() >= plan_for(workspace).social_accounts:
        raise LimitExceeded("O plano não permite adicionar outra conta social.")
    return accounts.update_or_create(workspace=workspace, provider="youtube", external_id=external_id, defaults={
        "label": label, "grant": cipher().encrypt(refresh_token.encode()),
    })[0]


def access_token(account):
    from .youtube import token

    secret = cipher().decrypt(bytes(account.grant)).decode()
    return token(grant_type="refresh_token", refresh_token=secret)["access_token"]
