#!/bin/bash
# Sync local JobSentry code to the Proxmox LXC
# Usage: ./deploy/sync-to-lxc.sh [LXC_IP]

LXC_IP="${1:?Usage: $0 <LXC_IP>}"
LXC_USER="jobsentry"
REMOTE_DIR="/home/${LXC_USER}/JobSentry"

echo "Syncing to ${LXC_USER}@${LXC_IP}:${REMOTE_DIR}..."

rsync -avz --delete \
    --exclude='.venv/' \
    --exclude='.env' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.git/' \
    --exclude='data/' \
    --exclude='*.db' \
    --exclude='*.egg-info/' \
    -e ssh \
    "$(dirname "$0")/../" \
    "root@${LXC_IP}:${REMOTE_DIR}/"

echo "Fixing ownership..."
ssh "root@${LXC_IP}" "chown -R ${LXC_USER}:${LXC_USER} ${REMOTE_DIR}"

echo "Reinstalling package..."
ssh "root@${LXC_IP}" "su - ${LXC_USER} -c 'cd ${REMOTE_DIR} && .venv/bin/pip install -e . -q'"

echo "Done! Verify with:"
echo "  ssh root@${LXC_IP} \"su - ${LXC_USER} -c 'cd ${REMOTE_DIR} && .venv/bin/jobsentry version'\""
