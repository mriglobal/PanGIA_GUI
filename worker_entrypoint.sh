#!/bin/bash --login
set -euo pipefail
conda activate gui
cd gui
rq worker -u redis://redis_server:6379 pangia-tasks
