#!/usr/bin/env python3
"""Measure actual Streamlit AppTest cold and cached rendering in this environment."""
import json
import platform
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import streamlit as st
from streamlit.testing.v1 import AppTest
from src.config import ROOT
st.cache_data.clear()
at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30)
start=time.perf_counter();at.run();cold=time.perf_counter()-start
assert not at.exception
updates=[]
for date in ['2026-03-16','2026-06-15']:
    start=time.perf_counter();at.selectbox(key='snapshot').set_value(date).run();updates.append(time.perf_counter()-start)
    assert not at.exception
result=dict(scope='Streamlit AppTest execution; excludes browser painting, installation, server startup and module imports',platform=platform.platform(),python=sys.version,cold_seconds=cold,cached_detail_update_seconds=updates,cold_target_seconds=10,cached_target_seconds=2,cold_target_met=cold<=10,cached_target_met=max(updates)<=2)
(ROOT/'reports/ui_performance.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
