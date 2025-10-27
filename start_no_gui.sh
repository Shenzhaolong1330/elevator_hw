#!/bin/bash

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 not found. Please install Python3 3.8+ first."
    exit 1
fi

# Set environment variables
VENV_DIR="venv"
REQUIREMENTS_FILE="requirements.txt"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    
    # Activate virtual environment and install dependencies
    echo "Installing dependencies..."
    source "$VENV_DIR/bin/activate"
    pip install -r "$REQUIREMENTS_FILE"
    pip install elevator-py
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies."
        exit 1
    fi
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Set client type
export ELEVATOR_CLIENT_TYPE=algorithm

# Start algorithm program only
echo "Starting Elevator Scheduling Algorithm..."
python3 algorithm_only.py

if [ $? -ne 0 ]; then
    echo ""
    echo "Error: Algorithm failed to start."
    exit 1
fi
