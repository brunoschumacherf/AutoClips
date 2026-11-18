from cryptography.fernet import Fernet
from django.conf import settings
from django.db import transaction

from accounts.models import Workspace
from subscriptions.services import LimitExceeded, plan_for
from .models import SocialAccount


def cipher():
    return Fernet(settings.OAUTH_ENCRYPTION_KEY.encode())


@transaction.atomic
def connect(workspace, external_id, label, grant, *, provider="youtube"):
    workspace = Workspace.objects.select_for_update().get(pk=workspace.pk)
    accounts = SocialAccount.objects.filter(workspace=workspace)
    if not accounts.filter(provider=provider, external_id=external_id).exists() and accounts.count() >= plan_for(workspace).social_accounts:
        raise LimitExceeded("O plano não permite adicionar outra conta social.")
    return accounts.update_or_create(workspace=workspace, provider=provider, external_id=external_id, defaults={
        "label": label, "grant": cipher().encrypt(grant.encode()),
    })[0]


def stored_grant(account):
    return cipher().decrypt(bytes(account.grant)).decode()


def access_token(account):
    from .youtube import token

    secret = stored_grant(account)
    return token(grant_type="refresh_token", refresh_token=secret)["access_token"]


@transaction.atomic
def tiktok_access(account):
    import json
    import time

    from .tiktok import token

    account = SocialAccount.objects.select_for_update().get(pk=account.pk)
    grant = json.loads(stored_grant(account))
    if grant["expires_at"] > time.time() + 30:
        return grant["access_token"]
    refreshed = token(grant_type="refresh_token", refresh_token=grant["refresh_token"])
    account.grant = cipher().encrypt(serialize_tiktok_grant(refreshed).encode())
    account.save(update_fields=["grant", "updated_at"])
    return refreshed["access_token"]


def serialize_tiktok_grant(grant):
    import json
    import time

    return json.dumps({"access_token": grant["access_token"], "refresh_token": grant["refresh_token"],
                       "expires_at": time.time() + int(grant["expires_in"])})
