from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_real_data_and_controls():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'streamlit_app.py'), default_timeout=60).run()
    assert not app.exception and not app.error
    assert app.metric[0].value == '$160.87'
    assert app.metric[4].value == '$162.91'
    app.selectbox(key='snapshot').set_value('2026-03-16').run()
    assert not app.exception
    assert app.metric[0].value == '$162.91'
    assert app.metric[5].value == '$160.87'
    app.number_input(key='minimum').set_value(30).run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    assert app.selectbox(key='snapshot').value == '2026-06-15'
