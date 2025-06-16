#!/bin/bash

# This script starts the UPC_PyGame simulation by launching the server and agents.

# Set PYTHONPATH to include the project root
export PYTHONPATH=$(pwd)

# Start main.py in the background
echo "Starting game (main.py)..."
python3 main.py &
MAIN_PID=$!

# Wait briefly for the server to start
sleep 8

# List all available agents in the "agents" folder
AGENTS_DIR="./agents"
echo "Automatically detecting agents in $AGENTS_DIR..."
AGENT_FILES=$(ls $AGENTS_DIR/*.py)
echo "Detected agents:"
echo "$AGENT_FILES"

# Start all detected agents
for AGENT_PATH in $AGENT_FILES; do
    echo "Starting $(basename $AGENT_PATH)..."
    python3 $AGENT_PATH &
done

# Wait for main.py to finish
wait $MAIN_PID