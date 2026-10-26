@echo off
pushd "%~dp0"
uv run --locked streamlit run app.py
popd
