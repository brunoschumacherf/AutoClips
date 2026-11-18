import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from django import forms
from django.conf import settings


def canonical_url(raw):
    target = urlsplit(raw)
    host = target.hostname
    if target.scheme != "https" or target.username or target.password or target.netloc.lower() != host:
        raise forms.ValidationError("Use um link HTTPS do YouTube ou da Twitch.")
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        key = parse_qs(target.query).get("v", [""])[0] if target.path == "/watch" else ""
    elif host == "youtu.be":
        key = target.path[1:]
    elif host in {"twitch.tv", "www.twitch.tv"} and re.fullmatch(r"/videos/[0-9]+", target.path):
        return f"https://www.twitch.tv{target.path}"
    else:
        key = ""
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", key):
        return f"https://www.youtube.com/watch?v={key}"
    raise forms.ValidationError("Informe um vídeo do YouTube ou um VOD da Twitch.")


def validate_upload(file):
    if file.size > settings.MAX_UPLOAD_BYTES or Path(file.name).suffix.lower() not in {".mp4", ".mov", ".mkv"}:
        raise forms.ValidationError("Envie MP4, MOV ou MKV dentro do limite de tamanho.")
    header = file.read(12)
    file.seek(0)
    if header[4:8] != b"ftyp" and not header.startswith(b"\x1a\x45\xdf\xa3"):
        raise forms.ValidationError("O conteúdo do arquivo não corresponde a um vídeo suportado.")
    return file


class IntakeForm(forms.Form):
    title = forms.CharField(label="Título", max_length=180)
    file = forms.FileField(label="Arquivo de vídeo", required=False, validators=[validate_upload])
    url = forms.URLField(label="Link do YouTube ou da Twitch", required=False, assume_scheme="https")
    count = forms.IntegerField(label="Quantidade de cortes", min_value=1, max_value=10, initial=3)
    minimum = forms.IntegerField(label="Duração mínima em segundos", min_value=3, max_value=180, initial=15)
    maximum = forms.IntegerField(label="Duração máxima em segundos", min_value=3, max_value=180, initial=60)
    aspect = forms.ChoiceField(label="Formato", choices=[
        ("9:16", "9:16 · Shorts, Reels e TikTok"), ("16:9", "16:9 · Horizontal"), ("1:1", "1:1 · Quadrado"),
    ])
    quality = forms.ChoiceField(label="Qualidade", choices=[("720", "Padrão"), ("1080", "Alta")])
    language = forms.ChoiceField(label="Idioma", choices=[("", "Automático"), ("pt", "Português"), ("en", "Inglês"), ("es", "Espanhol")], required=False)
    authorized = forms.BooleanField(label="Tenho autorização para processar este conteúdo")

    def clean_url(self):
        url = self.cleaned_data["url"]
        if not url:
            return ""
        if not settings.IMPORT_PROXY:
            raise forms.ValidationError("A importação por link requer um proxy de saída configurado.")
        try:
            return canonical_url(url)
        except ValueError as error:
            raise forms.ValidationError("Link inválido.") from error

    def clean(self):
        data = super().clean()
        if not self.errors and bool(data["file"]) == bool(data["url"]):
            raise forms.ValidationError("Informe um arquivo ou um link.")
        if data.get("minimum", 0) > data.get("maximum", 180):
            self.add_error("maximum", "Use um valor igual ou maior que a duração mínima.")
        return data
