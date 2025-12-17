#!/bin/bash
# Sync instrumental output to NAS via SSH
# Supports multiple modes: continuous, scheduled, manual-only
# Deletes local files after successful sync if DELETE_AFTER_SYNC=true

NAS_HOST="${NAS_HOST:-devshell.nsystems.live}"
NAS_PORT="${NAS_PORT:-54321}"
NAS_USER="${NAS_USER:-msn0624c}"
NAS_PATH="${NAS_PATH:-/volume1/docker/data/media/Instrumentals}"
LOCAL_PATH="${LOCAL_PATH:-/data/output}"
SSH_KEY="${SSH_KEY:-/root/.ssh/id_ed25519}"
SYNC_LOG="${SYNC_LOG:-/data/logs/nas_sync.jsonl}"
DELETE_AFTER_SYNC="${DELETE_AFTER_SYNC:-false}"  # Default to false - keep files
SYNC_MODE="${SYNC_MODE:-manual}"  # Options: continuous, scheduled, manual
SYNC_INTERVAL="${SYNC_INTERVAL:-30}"  # Seconds between syncs (for continuous mode)
TRIGGER_FILE="${SYNC_TRIGGER_FILE:-/data/output/.sync_trigger}"  # Touch this file to trigger manual sync

echo "============================================"
echo "NAS Sync Service Starting"
echo "============================================"
echo "Mode: $SYNC_MODE"
echo "Local: $LOCAL_PATH"
echo "Remote: $NAS_USER@$NAS_HOST:$NAS_PATH"
echo "Delete after sync: $DELETE_AFTER_SYNC"
echo "Sync interval: ${SYNC_INTERVAL}s (continuous mode)"
echo "============================================"

# Ensure SSH key has correct permissions
chmod 600 $SSH_KEY 2>/dev/null

# Ensure log directory exists
mkdir -p "$(dirname "$SYNC_LOG")" 2>/dev/null

log_sync() {
    local status="$1"
    local files_synced="$2"
    local bytes_synced="$3"
    local duration="$4"
    local error="$5"
    
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local log_entry="{\"timestamp\":\"$timestamp\",\"status\":\"$status\",\"files_synced\":$files_synced,\"bytes_synced\":$bytes_synced,\"duration_sec\":$duration"
    
    if [ -n "$error" ]; then
        log_entry="$log_entry,\"error\":\"$error\""
    fi
    log_entry="$log_entry}"
    
    echo "$log_entry" >> "$SYNC_LOG"
}

sync_files() {
    local start_time=$(date +%s)
    local files_synced=0
    local bytes_synced=0
    local has_error=false
    local error_msg=""
    
    echo "[$(date)] Starting sync..."
    
    # Find all audio files in output directory
    local files=$(find "$LOCAL_PATH" -type f \( -name "*.mp3" -o -name "*.flac" -o -name "*.wav" -o -name "*.m4a" \) 2>/dev/null)
    
    if [ -z "$files" ]; then
        echo "[$(date)] No files to sync"
        return 0
    fi
    
    echo "$files" | while IFS= read -r file; do
        # Skip if file doesn't exist (might have been deleted)
        [ -f "$file" ] || continue
        
        # Get file size
        local file_size=$(stat -c%s "$file" 2>/dev/null || echo 0)
        
        # Get relative path from LOCAL_PATH
        rel_path="${file#$LOCAL_PATH/}"
        rel_dir=$(dirname "$rel_path")
        remote_dir="$NAS_PATH/$rel_dir"
        
        # Escape special characters for scp remote path
        escaped_remote_dir=$(printf '%s' "$remote_dir" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\$/\\$/g; s/`/\\`/g')
        
        echo "  Syncing: $rel_path ($(numfmt --to=iec-i --suffix=B $file_size 2>/dev/null || echo "${file_size}B"))"
        
        # Create remote directory
        ssh -p "$NAS_PORT" -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes \
            "$NAS_USER@$NAS_HOST" "mkdir -p \"$escaped_remote_dir\"" 2>/dev/null
        
        # Copy file using scp
        scp -O -P "$NAS_PORT" -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes \
            "$file" "$NAS_USER@$NAS_HOST:\"$escaped_remote_dir/\"" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo "    ✓ Copied successfully"
            files_synced=$((files_synced + 1))
            bytes_synced=$((bytes_synced + file_size))
            
            # Delete local file after successful sync if enabled
            if [ "$DELETE_AFTER_SYNC" = "true" ]; then
                rm -f "$file"
                echo "    ✓ Deleted local file"
                
                # Clean up empty parent directories
                parent_dir=$(dirname "$file")
                while [ "$parent_dir" != "$LOCAL_PATH" ] && [ -d "$parent_dir" ]; do
                    if [ -z "$(ls -A "$parent_dir" 2>/dev/null)" ]; then
                        rmdir "$parent_dir" 2>/dev/null
                        parent_dir=$(dirname "$parent_dir")
                    else
                        break
                    fi
                done
            fi
        else
            echo "    ✗ Failed to copy"
            has_error=true
            error_msg="Failed to copy some files"
        fi
    done
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo "[$(date)] Sync completed: $files_synced files, $(numfmt --to=iec-i --suffix=B $bytes_synced 2>/dev/null || echo "${bytes_synced}B") in ${duration}s"
    
    # Log the sync result
    if [ "$has_error" = true ]; then
        log_sync "failed" "$files_synced" "$bytes_synced" "$duration" "$error_msg"
    else
        log_sync "success" "$files_synced" "$bytes_synced" "$duration" ""
    fi
    
    return 0
}

# Handle graceful shutdown
trap 'echo "Shutting down NAS sync service..."; exit 0' SIGTERM SIGINT

case "$SYNC_MODE" in
    continuous)
        echo "Running in CONTINUOUS mode - syncing every ${SYNC_INTERVAL}s"
        while true; do
            sync_files
            # Also check for manual trigger
            if [ -f "$TRIGGER_FILE" ]; then
                rm -f "$TRIGGER_FILE"
                echo "[$(date)] Manual trigger detected, syncing immediately..."
                sync_files
            fi
            sleep "$SYNC_INTERVAL"
        done
        ;;
    
    scheduled)
        echo "Running in SCHEDULED mode - waiting for cron or manual trigger"
        # In scheduled mode, just wait for triggers
        while true; do
            if [ -f "$TRIGGER_FILE" ]; then
                rm -f "$TRIGGER_FILE"
                echo "[$(date)] Manual trigger detected"
                sync_files
            fi
            sleep 5  # Check for trigger every 5 seconds
        done
        ;;
    
    manual)
        echo "Running in MANUAL mode - waiting for triggers only"
        echo "Touch $TRIGGER_FILE or call /api/nas/trigger-sync to sync"
        while true; do
            if [ -f "$TRIGGER_FILE" ]; then
                rm -f "$TRIGGER_FILE"
                echo "[$(date)] Manual trigger detected"
                sync_files
            fi
            sleep 5  # Check for trigger every 5 seconds
        done
        ;;
    
    once)
        # Run once and exit (useful for cron jobs)
        echo "Running in ONCE mode - single sync then exit"
        sync_files
        exit 0
        ;;
    
    *)
        echo "Unknown SYNC_MODE: $SYNC_MODE"
        echo "Valid modes: continuous, scheduled, manual, once"
        exit 1
        ;;
esac
