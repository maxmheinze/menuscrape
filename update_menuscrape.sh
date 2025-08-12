#!/bin/bash

# Log file
LOG_FILE="/home/max/github/menuscrape_log.txt"

# Initialize Conda
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
source /home/max/anaconda3/etc/profile.d/conda.sh 2>&1 || {
    echo "$TIMESTAMP - Failed to initialize Conda" | tee -a "$LOG_FILE"
    exit 1
}
echo "$TIMESTAMP - Conda initialized" | tee -a "$LOG_FILE"

# Activate your Conda environment
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
conda activate base 2>&1 || {
    echo "$TIMESTAMP - Failed to activate Conda environment" | tee -a "$LOG_FILE"
    exit 1
}
echo "$TIMESTAMP - Conda environment 'base' activated" | tee -a "$LOG_FILE"

# Navigate to your repository directory
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
cd /home/max/github/menuscrape 2>&1 || {
    echo "$TIMESTAMP - Failed to change directory to /home/max/github/menuscrape" | tee -a "$LOG_FILE"
    exit 1
}
echo "$TIMESTAMP - Changed directory to /home/max/github/menuscrape" | tee -a "$LOG_FILE"

# Run your Python script
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
python menuscrape.py 2>&1 || {
    echo "$TIMESTAMP - Python script failed" | tee -a "$LOG_FILE"
    exit 1
}
echo "$TIMESTAMP - Python script executed successfully" | tee -a "$LOG_FILE"

# Add the generated files
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
git add -A 2>&1 || {
    echo "$TIMESTAMP - Git add failed" | tee -a "$LOG_FILE"
    exit 1
}
echo "$TIMESTAMP - Git add completed" | tee -a "$LOG_FILE"

# Commit the changes with a timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
git commit -m "Automated update: $TIMESTAMP" 2>&1 || {
    echo "$TIMESTAMP - Git commit failed" | tee -a "$LOG_FILE"
    exit 1
}
echo "$TIMESTAMP - Git commit successful" | tee -a "$LOG_FILE"

# Push the changes to the remote repository
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
git push origin main 2>&1 || {
    echo "$TIMESTAMP - Git push failed" | tee -a "$LOG_FILE"
    exit 1
}
echo "$TIMESTAMP - Changes pushed to origin main" | tee -a "$LOG_FILE"

# Copy the "menu.md" file to the second repository
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
cp /home/max/github/menuscrape/menu.md /home/max/github/maxmheinze.github.io/ 2>&1 || {
    echo "$TIMESTAMP - File copy failed" | tee -a "$LOG_FILE"
    exit 1
}
echo "$TIMESTAMP - menu.md copied to second repository" | tee -a "$LOG_FILE"

# Navigate to the second repository directory
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
cd /home/max/github/maxmheinze.github.io 2>&1 || {
    echo "$TIMESTAMP - Failed to change directory to /home/max/github/maxmheinze.github.io" | tee -a "$LOG_FILE"
    exit 1
}
echo "$TIMESTAMP - Changed directory to /home/max/github/maxmheinze.github.io" | tee -a "$LOG_FILE"

# Add the copied file
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
git add -A 2>&1 || {
    echo "$TIMESTAMP - Git add failed in second repo" | tee -a "$LOG_FILE"
    exit 1
}
echo "$TIMESTAMP - Git add in second repo completed" | tee -a "$LOG_FILE"

# Commit the changes with a timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
git commit -m "Automated update: $TIMESTAMP" 2>&1 || {
    echo "$TIMESTAMP - Git commit failed in second repo" | tee -a "$LOG_FILE"
    exit 1
}
echo "$TIMESTAMP - Git commit in second repo successful" | tee -a "$LOG_FILE"

# Push the changes to the remote repository
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
git push origin main 2>&1 || {
    echo "$TIMESTAMP - Git push failed in second repo" | tee -a "$LOG_FILE"
    exit 1
}
echo "$TIMESTAMP - Changes pushed to origin main in second repo" | tee -a "$LOG_FILE"

