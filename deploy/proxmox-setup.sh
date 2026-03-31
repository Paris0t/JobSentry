#!/bin/bash
# JobSentry — Proxmox LXC deployment script
# Run this INSIDE the LXC container as root after creating it.
#
# LXC Requirements:
#   - Debian 12 (Bookworm) or Ubuntu 22.04+
#   - 1 CPU core, 512MB RAM minimum (1GB recommended)
#   - 4GB disk minimum
#   - Network access (NAT or bridged)
#
# Create the LXC on Proxmox:
#   pct create 200 local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst \
#     --hostname jobsentry \
#     --memory 1024 \
#     --cores 1 \
#     --rootfs local-lvm:4 \
#     --net0 name=eth0,bridge=vmbr0,ip=dhcp \
#     --unprivileged 1 \
#     --features nesting=1 \
#     --start 1
#
# Then: pct enter 200
# Then run this script: bash /tmp/proxmox-setup.sh

set -e

REPO_URL="${JOBSENTRY_REPO_URL:-https://github.com/Paris0t/JobSentry.git}"
APP_USER="jobsentry"
APP_DIR="/home/${APP_USER}/JobSentry"

echo "=== JobSentry Proxmox Setup ==="

# 1. Install system dependencies
echo "[1/6] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-venv python3-pip \
    git curl wget \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libatspi2.0-0 \
    libx11-6 libxcomposite1 libxdamage1 libxext6 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libxshmfence1 libxkbcommon0 fonts-liberation \
    > /dev/null 2>&1

# 2. Create app user
echo "[2/6] Creating ${APP_USER} user..."
if ! id -u ${APP_USER} >/dev/null 2>&1; then
    useradd -m -s /bin/bash ${APP_USER}
fi

# 3. Clone and install
echo "[3/6] Cloning repository..."
su - ${APP_USER} -c "
    cd ~
    if [ ! -d JobSentry ]; then
        git clone ${REPO_URL}
    else
        cd JobSentry && git pull
    fi
    cd ~/JobSentry
    python3 -m venv .venv
    .venv/bin/pip install -e . -q
"

# 4. Install Playwright browser
echo "[4/6] Installing Playwright Chromium..."
su - ${APP_USER} -c "
    cd ~/JobSentry
    .venv/bin/playwright install chromium
"

# 5. Set up data directories
echo "[5/6] Setting up data directories..."
su - ${APP_USER} -c "
    mkdir -p ~/.local/share/jobsentry/{cookies,screenshots,logs}
"

# 6. Create systemd timer (alternative to cron)
echo "[6/6] Creating systemd timer..."
cat > /etc/systemd/system/jobsentry.service << 'UNIT'
[Unit]
Description=JobSentry automated job search
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=jobsentry
WorkingDirectory=/home/jobsentry/JobSentry
Environment=HOME=/home/jobsentry
ExecStart=/home/jobsentry/JobSentry/.venv/bin/bash -c '\
    source .venv/bin/activate && \
    jobsentry jobs search -b clearancejobs -p 3 && \
    jobsentry jobs search -b indeed -p 2 && \
    jobsentry jobs fetch && \
    jobsentry jobs match && \
    jobsentry notify summary'
StandardOutput=append:/home/jobsentry/.local/share/jobsentry/logs/service.log
StandardError=append:/home/jobsentry/.local/share/jobsentry/logs/service.log
UNIT

cat > /etc/systemd/system/jobsentry.timer << 'TIMER'
[Unit]
Description=Run JobSentry twice daily

[Timer]
OnCalendar=*-*-* 08:00:00
OnCalendar=*-*-* 18:00:00
Persistent=true

[Install]
WantedBy=timers.target
TIMER

systemctl daemon-reload
systemctl enable jobsentry.timer

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Copy your .env from laptop:"
echo "     scp .env ${APP_USER}@<LXC_IP>:${APP_DIR}/.env"
echo ""
echo "  2. Copy your profile and cookies:"
echo "     scp ~/.local/share/jobsentry/profile.json ${APP_USER}@<LXC_IP>:~/.local/share/jobsentry/"
echo "     scp -r ~/.local/share/jobsentry/cookies/ ${APP_USER}@<LXC_IP>:~/.local/share/jobsentry/"
echo ""
echo "  3. Lock down .env permissions:"
echo "     ssh ${APP_USER}@<LXC_IP> 'chmod 600 ${APP_DIR}/.env'"
echo ""
echo "  4. Start the timer:"
echo "     systemctl start jobsentry.timer"
echo ""
echo "  5. Test manually:"
echo "     su - ${APP_USER} -c 'cd ${APP_DIR} && .venv/bin/jobsentry jobs search -b clearancejobs'"
echo ""
echo "  6. Check timer status:"
echo "     systemctl status jobsentry.timer"
echo "     journalctl -u jobsentry.service -f"
