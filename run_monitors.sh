#!/bin/bash

# Review Monitor Runner Script
# This script sets up the environment and runs the main monitor

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to script directory
cd "$SCRIPT_DIR"

source venv/bin/activate
# Set up Python path if needed
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Log file for cron output
LOG_FILE="$SCRIPT_DIR/cron_monitor.log"

# Print header to log
echo "=================================" >> "$LOG_FILE"
echo "Review Monitor Started: $(date)" >> "$LOG_FILE"
echo "Directory: $SCRIPT_DIR" >> "$LOG_FILE"
echo "=================================" >> "$LOG_FILE"

# Run the main monitor script
python3 "$SCRIPT_DIR/main_monitor.py" >> "$LOG_FILE" 2>&1

# Capture exit code
EXIT_CODE=$?

# Print footer to log
echo "=================================" >> "$LOG_FILE"
echo "Review Monitor Finished: $(date)" >> "$LOG_FILE"
echo "Exit Code: $EXIT_CODE" >> "$LOG_FILE"
echo "=================================" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Exit with the same code as the Python script
exit $EXIT_CODE