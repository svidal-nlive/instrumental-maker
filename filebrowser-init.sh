#!/bin/bash
# Filebrowser initialization script
# This script initializes filebrowser with a default user

DB_PATH="/database/filebrowser.db"

# Wait for filebrowser to start
sleep 2

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo "Initializing filebrowser with default credentials..."
    
    # Use filebrowser CLI to set up admin user
    # filebrowser users add admin password
    filebrowser --database "$DB_PATH" users add admin password
    
    if [ $? -eq 0 ]; then
        echo "Filebrowser initialized successfully!"
        echo "Username: admin"
        echo "Password: password"
    else
        echo "Failed to initialize filebrowser user"
    fi
fi

# Keep the container running
exec "$@"
