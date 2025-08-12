#!/bin/bash

# File to track the last run date
LAST_RUN_FILE="/home/max/github/last_menuscrape_run"

# Log file
LOG_FILE="/home/max/github/menuscrape_log.txt"

# Get current date and time
CURRENT_DATE=$(date +%Y-%m-%d)
CURRENT_TIME=$(date +%H:%M)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Desired run time (24-hour format)
RUN_TIME="10:00"

# Check if the script has already run today
if [ -f "$LAST_RUN_FILE" ]; then
    LAST_RUN_DATE=$(cat "$LAST_RUN_FILE")
    if [ "$LAST_RUN_DATE" == "$CURRENT_DATE" ]; then
        echo "$TIMESTAMP - Script has already run today." | tee -a "$LOG_FILE"
        exit 0
    fi
fi

# Check if it's after 10:00 AM
if [[ "$CURRENT_TIME" > "$RUN_TIME" ]] || [[ "$CURRENT_TIME" == "$RUN_TIME" ]]; then
    # Run your main script
    /home/max/github/update_menuscrape.sh

    # Update the last run date
    echo "$CURRENT_DATE" > "$LAST_RUN_FILE"

    echo "$TIMESTAMP - Script ran successfully." | tee -a "$LOG_FILE"
else
    echo "$TIMESTAMP - It's before $RUN_TIME. Script will not run yet." | tee -a "$LOG_FILE"
fi

