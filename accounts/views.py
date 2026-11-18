from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import UserProfile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["display_name"]
        labels = {"display_name": "Nome de exibição"}


@login_required
def settings_page(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("settings")
    return render(request, "form.html", {"form": form, "title": "Configurações", "button": "Salvar perfil", "profile": True})
