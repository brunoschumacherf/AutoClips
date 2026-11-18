# CortaLives

Aplicação Django para transformar vídeos longos autorizados em cortes com legendas. O fluxo básico usa faster-whisper em CPU e FFmpeg. O repositório chama-se AutoClips.

## Executar com Docker Compose

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
docker compose logs -f worker
```

Abra http://localhost:8000, crie uma conta e importe um MP4, MOV ou MKV com áudio. Use um vídeo curto na primeira execução. Abra a prévia depois do processamento, ajuste o intervalo e as legendas e baixe o MP4, SRT ou VTT. O modelo é baixado no primeiro uso e fica no volume `models`. Para usar um modelo CTranslate2 já disponível no volume, configure seu caminho em `WHISPER_MODEL`.

`make superuser` cria um administrador. `make migrate` aplica migrations. Em `/admin/`, administre os quatro planos e os workspaces. A API de leitura exige sessão autenticada, identifica recursos por UUID e tem esquema em `/api/schema/`.

## Executar a aplicação no host com PostgreSQL e Redis em contêineres

Esta opção usa menos espaço em disco em ambientes com armazenamento Docker VFS. Instale os requisitos de desenvolvimento abaixo e execute:

```bash
docker compose -f docker-compose.yml -f docker-compose.host.yml up -d --wait db redis
export DATABASE_URL=postgresql://cortalives:cortalives@127.0.0.1:15432/cortalives
export REDIS_URL=redis://127.0.0.1:16379/0 SHARED_CACHE=True
python manage.py migrate
python manage.py collectstatic --noinput
```

Com as mesmas variáveis em três terminais, execute:

```bash
uvicorn core.asgi:application --host 127.0.0.1 --port 8000
celery -A core worker -l INFO -c 2 -Q celery,downloads,transcriptions,analysis,clips,rendering,publishing
celery -A core beat -l INFO --schedule /tmp/cortalives-beat
```

## Desenvolvimento e testes

Instale Python 3.12, FFmpeg com libass, libx264 e AAC e as fontes DejaVu. Os testes usam SQLite por padrão. Os workers e o progresso WebSocket usam Redis. Use PostgreSQL para validar concorrência e em implantação.

```bash
python -m venv .venv
. .venv/bin/activate
make install
python manage.py migrate
python manage.py collectstatic --noinput
make check
make test
```

O teste de integração padrão gera vídeo sintético, injeta uma transcrição e executa ingestão, análise, renderização, edição, exportação e isolamento entre usuários. Para repetir com inferência real em CPU, use um FFmpeg com filtro `flite` e um modelo local:

```bash
CORTALIVES_TEST_MODEL=/caminho/para/faster-whisper-tiny python -m pytest -q
```

A instalação local compartilha dois processos Celery entre filas distintas. A recuperação periódica reinsere tarefas sem lease ativo. A pontuação estima relevância editorial de 0 a 100 com energia de áudio, movimento, texto, coerência e qualidade. O reenquadramento usa amostras de rostos com suavização. A exportação usa H.264/AAC, formatos vertical, quadrado e horizontal, e destaque por palavra quando há timestamps.

## Configuração externa

- **Importação por URL.** Configure `IMPORT_PROXY` em um ambiente com saída controlada. O proxy deve bloquear redes privadas, loopback, metadados e redirecionamentos para esses destinos. Bloqueie a saída direta do worker de importação e permita apenas os domínios públicos necessários para YouTube e Twitch. Autorizações e limites das plataformas continuam aplicáveis.
- **Login Google.** Defina `GOOGLE_LOGIN_CLIENT_ID` e `GOOGLE_LOGIN_CLIENT_SECRET` e registre a URL `/accounts/google/login/callback/` no cliente Google. Use credenciais distintas das de publicação quando houver permissões diferentes.
- **YouTube.** Ative a YouTube Data API v3. Crie um cliente OAuth Web e registre a URL exata de `YOUTUBE_REDIRECT_URI`, com caminho `/publications/youtube/callback/`. Configure ID, segredo e uma chave Fernet em `OAUTH_ENCRYPTION_KEY`. A conta precisa de um plano com cota social. O agendador envia vídeos privados e consulta a situação na API oficial. O teste automatizado usa mocks. Ativar em uma conta real exige credenciais, escopos, aprovação quando aplicável e validação no ambiente.
- **Armazenamento.** O padrão é um volume local. Defina `S3_BUCKET`, credenciais por identidade do serviço e opcionalmente `S3_ENDPOINT` para S3 ou MinIO. Mantenha o bucket privado. A aplicação verifica o acesso antes de servir arquivos e aceita requisições Range. Valide o provedor de armazenamento no ambiente de implantação.
- **Análise semântica.** Por padrão roda localmente com heurísticas. `SEMANTIC_PROVIDER=chat` ativa um endpoint compatível com chat completions, como Ollama ou OpenAI. Informe URL base, modelo e chave quando necessária. Essa opção envia trechos de texto ao provedor configurado e limita cada análise a 12 chamadas com fallback local.
- **TLS de build.** Em rede que inspeciona TLS, monte o bundle confiável como segredo BuildKit `package_ca`.

## Operação e limites atuais

Em implantação, configure HTTPS, `DEBUG=False`, um segredo exclusivo, domínios em `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`, SMTP e verificação de e-mail obrigatória. Restrinja PostgreSQL e Redis, limite o corpo de upload no proxy e configure backup e alertas. `VIDEO_RETENTION_DAYS` remove arquivos de vídeos em estados finais após o prazo e preserva o consumo e os metadados. A retenção automática vem desativada. Configure retenção de logs e backups, atendimento a titulares e controle sobre envio de texto a terceiros antes de operar comercialmente.

A captura ao vivo, diarização, layout gameplay/webcam, publicação TikTok e Instagram, cobrança, métricas Prometheus e gestão completa de sessões ainda não foram implementados. O frontend usa templates Django, CSS próprio e JavaScript, com WebSocket e polling de recuperação. O cancelamento invalida resultados em andamento. Um FFmpeg já em execução pode continuar até terminar ou atingir o timeout. Uma resposta de upload perdida no YouTube deixa o status indeterminado para evitar reenvio duplicado.
