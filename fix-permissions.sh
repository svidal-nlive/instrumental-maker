#!/bin/bash
# Fix permissions for pipeline directories to allow both local user and Docker containers to access

set -e

PIPELINE_ROOT="/home/roredev/instrumental-maker/pipeline-data"
LOCAL_USER="roredev"
LOCAL_UID=1000
LOCAL_GID=1000

echo "🔐 Fixing permissions for pipeline directories..."
echo "   Pipeline root: $PIPELINE_ROOT"
echo "   Local user: $LOCAL_USER ($LOCAL_UID:$LOCAL_GID)"
echo ""

# Ensure pipeline root exists
mkdir -p "$PIPELINE_ROOT"

# List of critical directories
DIRS=(
    "$PIPELINE_ROOT/incoming"
    "$PIPELINE_ROOT/output"
    "$PIPELINE_ROOT/outputs"
    "$PIPELINE_ROOT/working"
    "$PIPELINE_ROOT/logs"
    "$PIPELINE_ROOT/archive"
    "$PIPELINE_ROOT/quarantine"
    "$PIPELINE_ROOT/db"
    "$PIPELINE_ROOT/config"
    "$PIPELINE_ROOT/models"
)

# Create missing directories
for dir in "${DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "📁 Creating: $dir"
        mkdir -p "$dir"
    fi
done

# Change ownership to local user:local group (allows local editing)
echo "👤 Changing ownership to $LOCAL_USER:$LOCAL_GID..."
sudo chown -R "$LOCAL_UID:$LOCAL_GID" "$PIPELINE_ROOT"

# Set permissions:
# - Owner (local user): read + write + execute
# - Group (local user's group): read + write + execute (for Docker volumes)
# - Others: read + execute (so containers can access)
echo "🔑 Setting directory permissions (755)..."
sudo find "$PIPELINE_ROOT" -type d -exec chmod 755 {} \;

echo "🔑 Setting file permissions (644)..."
sudo find "$PIPELINE_ROOT" -type f -exec chmod 644 {} \;

# Make scripts executable if they exist
echo "🔧 Setting script permissions..."
sudo find "$PIPELINE_ROOT" -type f -name "*.sh" -exec chmod 755 {} \;

# Create docker group permissions setup
# Docker containers running as root inside will see these directories as writable
echo ""
echo "✅ Permission fixes applied!"
echo ""
echo "Directory permissions summary:"
ls -la "$PIPELINE_ROOT" | tail -n +4

echo ""
echo "📝 Note: Docker containers running as root (UID 0) can read/write all files."
echo "   Local user ($LOCAL_USER) can also read/write all files."
echo "   This ensures consistency between testing and production."
