from django.db.models import Q

from .models import Workspace


def personal_workspace(user):
    return Workspace.objects.get_or_create(owner=user)[0]


def visible_workspaces(user):
    return Workspace.objects.filter(Q(owner=user) | Q(members=user)).distinct()
