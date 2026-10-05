# Deploying

One small VPS running the production compose file. Caddy terminates TLS and
serves the API and the frontend from one origin, so there's no CORS preflight
in normal use.

Tested target: Hetzner CX22 (2 vCPU, 4GB, ~€4/month), Ubuntu 24.04. 4GB is
comfortable at runtime; the *build* is the tight part, which is what the swap
file below is for.

## 1. DNS first

Point an **A record** for your subdomain at the server's IPv4 address, then
check from your own machine:

```bash
dig +short study.example.com
```

It must return the server's IP **before** you start the stack. Caddy requests
a certificate on boot and Let's Encrypt validates by connecting back to that
name; if DNS isn't live the request fails, and repeated failures hit rate
limits.

## 2. Prepare the server

```bash
ssh root@YOUR_IP

adduser deploy && usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy

# Swap: 4GB of RAM is enough to run, but `next build` and the torch install
# can be OOM-killed without it
fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable

sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
```

Reconnect as `deploy`, then install Docker:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy
```

Log out and back in so the group membership applies.

## 3. Deploy

```bash
git clone https://github.com/joela03/study-helper.git
cd study-helper
cp .env.production.example .env.production
nano .env.production
```

Fill in every blank. Generate the secrets rather than inventing them:

```bash
openssl rand -hex 32      # SECRET_KEY
openssl rand -base64 24   # POSTGRES_PASSWORD
```

Then:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Expect **15–25 minutes** on 2 vCPUs. Torch and the baked embedding model
dominate; later deploys reuse those layers and are far quicker.

Watch it:

```bash
docker compose -f docker-compose.prod.yml logs -f
```

Migrations run automatically before the API accepts traffic.

## 4. Your first account

The admin seed in the ownership migration only fires when there are existing
subjects to hand over. A fresh database has none, so **no admin exists yet**.

Temporarily open registration in `.env.production`:

```
REQUIRE_INVITE=false
```

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d backend
```

Register through the site, then promote yourself:

```bash
docker compose -f docker-compose.prod.yml exec db \
  psql -U studyhelper -d studyhelper \
  -c "update users set is_admin = true where email = 'you@example.com';"
```

Set `REQUIRE_INVITE=true` again and restart the backend. From then on:

```bash
API=https://study.example.com ./scripts/invite.sh "a course mate" 1 30
```

## Updating

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Migrations are applied on backend start, so schema changes need nothing extra.

## Backups

The database lives in a Docker volume with no backup. Enable the provider's
automatic snapshots — on Hetzner that's ~20% of the server cost, around €1 a
month — and it covers the Postgres volume and the uploads together. The
embeddings are expensive to regenerate, so this is the cheapest insurance in
the whole setup.

For a database-only dump:

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U studyhelper studyhelper | gzip > backup-$(date +%F).sql.gz
```

## If it doesn't come up

**Caddy can't get a certificate** — nearly always DNS. `docker compose -f
docker-compose.prod.yml logs caddy` says so plainly. Confirm `dig` returns the
right IP and that 80/443 are open.

**Backend exits immediately** — the production guard refuses to start while
`SECRET_KEY`, `CORS_ORIGINS` or the database password are still development
defaults. The log lists exactly which.

**Frontend calls the wrong API** — `NEXT_PUBLIC_API_URL` is inlined into the
client bundle at build time, so changing `PUBLIC_ORIGIN` needs
`up -d --build`, not just a restart.

**Build killed around the torch install** — swap isn't on. Check `free -h`.
