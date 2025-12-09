#!/bin/bash
# Sync instrumental output to NAS via SSH
# Runs continuously, syncing new files every 30 seconds
# Deletes local files after successful sync to save VPS storage

NAS_HOST="devshell.nsystems.live"
NAS_PORT="54321"
NAS_USER="msn0624c"
NAS_PATH="/volume1/docker/data/media/Instrumentals"
LOCAL_PATH="/data/output"
SSH_KEY="/root/.ssh/id_ed25519"
SYNC_DB="/tmp/synced_files.txt"
DELETE_AFTER_SYNC="true"  # Set to "false" to keep local copies

echo "Starting NAS sync service..."
echo "Local: $LOCAL_PATH -> Remote: $NAS_USER@$NAS_HOST:$NAS_PATH"
echo "Delete after sync: $DELETE_AFTER_SYNC"

# Ensure SSH key has correct permissions
chmod 600 $SSH_KEY 2>/dev/null

# Create sync database if it doesn't exist
touch "$SYNC_DB"

sync_files() {
    # Find all audio files in output directory
    find "$LOCAL_PATH" -type f \( -name "*.mp3" -o -name "*.flac" -o -name "*.wav" -o -name "*.m4a" \) 2>/dev/null | while IFS= read -r file; do
        # Skip if file doesn't exist (might have been deleted)
        [ -f "$file" ] || continue
        
        # Get relative path from LOCAL_PATH
        rel_path="${file#$LOCAL_PATH/}"
        rel_dir=$(dirname "$rel_path")
        remote_dir="$NAS_PATH/$rel_dir"
        
        # Escape special characters for scp remote path (parentheses, spaces, etc.)
        # scp requires escaping for the remote shell
        escaped_remote_dir=$(printf '%s' "$remote_dir" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\$/\\$/g; s/`/\\`/g')
        
        echo "Syncing: $rel_path"
        
        # Create remote directory - double quotes handle spaces and special chars
        ssh -p "$NAS_PORT" -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes \
            "$NAS_USER@$NAS_HOST" "mkdir -p \"$escaped_remote_dir\"" 2>/dev/null
        
        # Copy file using scp with legacy protocol
        # Put the entire remote path in double quotes to handle special characters
        scp -O -P "$NAS_PORT" -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes \
            "$file" "$NAS_USER@$NAS_HOST:\"$escaped_remote_dir/\"" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo "  -> Copied successfully"
            
            # Delete local file after successful sync if enabled
            if [ "$DELETE_AFTER_SYNC" = "true" ]; then
                rm -f "$file"
                echo "  -> Deleted local file"
                
                # Clean up empty parent directories
                parent_dir=$(dirname "$file")
                while [ "$parent_dir" != "$LOCAL_PATH" ] && [ -d "$parent_dir" ]; do
                    if [ -z "$(ls -A "$parent_dir" 2>/dev/null)" ]; then
                        rmdir "$parent_dir" 2>/dev/null
                        echo "  -> Removed empty dir: $parent_dir"
                        parent_dir=$(dirname "$parent_dir")
                    else
                        break
                    fi
                done
            fi
        else
            echo "  -> Failed to copy (will retry next cycle)"
        fi
    done
}

while true; do
    echo "[$(date)] Syncing files to NAS..."
    
    sync_files
    
    echo "[$(date)] Sync cycle completed"
    
    # Wait 30 seconds before next sync
    sleep 30
done
