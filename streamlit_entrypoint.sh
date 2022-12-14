#!/bin/bash --login

pip install --upgrade pip
pip install streamlit
pip install matplotlib
pip install bokeh

# Re-enable strict mode:
set -euo pipefail
cd gui

# exec the final command:
exec streamlit run streamlit_vis.py pangia_gui:app