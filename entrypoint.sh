#!/bin/bash --login
set -euo pipefail
conda activate gui
cd gui
exec gunicorn -b 0.0.0.0:5000 -t 6000 pangia_gui:app
