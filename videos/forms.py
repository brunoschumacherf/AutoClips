import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from django import forms
from django.conf import settings
from django.core.validators import MaxValueValidator


def canonical_url(raw):
    target = urlsplit(raw)
    host = target.hostname
    if target.scheme != "https" or target.username or target.password or target.netloc.lower() != host:
        raise forms.ValidationError("Use um link HTTPS do YouTube ou da Twitch.")
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        live_path = re.fullmatch(r"/(?:@[A-Za-z0-9._-]{3,30}|channel/UC[A-Za-z0-9_-]{22})/live/?", target.path)
        if live_path:
            return f"https://www.youtube.com{target.path.rstrip('/')}"
        if target.path == "/watch":
            key = parse_qs(target.query).get("v", [""])[0]
        else:
            match = re.fullmatch(r"/(?:live|shorts)/([A-Za-z0-9_-]{11})/?", target.path)
            key = match[1] if match else ""
    elif host == "youtu.be":
        key = target.path[1:]
    elif host in {"twitch.tv", "www.twitch.tv"}:
        path = target.path.rstrip("/").lower()
        if re.fullmatch(r"/videos/[0-9]+", path) or (
            re.fullmatch(r"/[a-z0-9_]{2,25}", path)
            and path not in {"/videos", "/directory", "/downloads", "/settings", "/subscriptions", "/inventory"}
        ):
            return f"https://www.twitch.tv{path}"
        key = ""
    else:
        key = ""
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", key):
        return f"https://www.youtube.com/watch?v={key}"
    raise forms.ValidationError("Informe um vídeo ou live do YouTube, ou um VOD ou canal da Twitch.")


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
    capture_minutes = forms.IntegerField(
        label="Minutos de captura se estiver ao vivo", required=False, min_value=1,
        help_text="Se a transmissão estiver em andamento, a captura começará próxima do ponto ao vivo.",
    )
    count = forms.IntegerField(label="Quantidade de cortes", min_value=1, max_value=10, initial=3)
    minimum = forms.IntegerField(label="Duração mínima em segundos", min_value=3, max_value=180, initial=15)
    maximum = forms.IntegerField(label="Duração máxima em segundos", min_value=3, max_value=180, initial=60)
    aspect = forms.ChoiceField(label="Formato", choices=[
        ("9:16", "9:16 · Shorts, Reels e TikTok"), ("16:9", "16:9 · Horizontal"), ("1:1", "1:1 · Quadrado"),
    ])
    quality = forms.ChoiceField(label="Qualidade", choices=[("720", "Padrão"), ("1080", "Alta")])
    language = forms.ChoiceField(label="Idioma", choices=[("", "Automático"), ("pt", "Português"), ("en", "Inglês"), ("es", "Espanhol")], required=False)
    authorized = forms.BooleanField(label="Tenho autorização para processar este conteúdo")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["capture_minutes"]
        field.max_value = settings.LIVE_CAPTURE_MAX_MINUTES
        field.validators.append(MaxValueValidator(field.max_value))
        field.initial = min(5, field.max_value)

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
        data["capture_minutes"] = data.get("capture_minutes") or min(5, settings.LIVE_CAPTURE_MAX_MINUTES)
        if data.get("minimum", 0) > data.get("maximum", 180):
            self.add_error("maximum", "Use um valor igual ou maior que a duração mínima.")
        return data
