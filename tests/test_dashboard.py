"""Dashboard smoke tests with Streamlit's AppTest (skipped if results are not generated)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (ROOT / "results/predictions_test.parquet").exists(),
                                reason="run scripts/run_experiment.py first")
PAGES = ["Overview", "History and location", "Forecasts", "Model comparison", "Data and limitations"]


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_with_simulated_banner_and_no_exception(page):
    at = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=60).run()
    assert not at.exception
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, [e.value for e in at.exception]
    html = " ".join(m.value for m in at.markdown)
    assert "MODEL-SIMULATED DATA" in html and "not a flood warning" in html.lower()


def test_no_flood_thresholds_or_warning_language():
    at = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=60).run()
    text = " ".join(m.value for m in at.markdown).lower()
    for bad in ("danger level", "alert level", "evacuat", "flood threshold"):
        assert bad not in text
