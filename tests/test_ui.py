from streamlit.testing.v1 import AppTest


def test_app_loads_without_exception():
    app = AppTest.from_file("../app.py")
    app.run(timeout=20)
    assert not app.exception
    assert app.sidebar.radio[0].options == ["New screening", "History", "Library"]
