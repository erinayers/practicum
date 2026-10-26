from __future__ import annotations

from practicum_desktop.api_client import NodeProgressInfo
from practicum_desktop.progress_panel import (
    StartProgressPanel,
    node_percent,
    step_text,
    summarize_progress,
)


def test_node_percent_by_step() -> None:
    assert node_percent(NodeProgressInfo("a", "img", "waiting")) == 0
    assert node_percent(NodeProgressInfo("a", "img", "checking_image")) == 10
    assert node_percent(NodeProgressInfo("a", "img", "pulling_image", percent=0)) == 10
    assert node_percent(NodeProgressInfo("a", "img", "pulling_image", percent=50)) == 40
    assert node_percent(NodeProgressInfo("a", "img", "pulling_image", percent=100)) == 70
    assert node_percent(NodeProgressInfo("a", "img", "creating_container")) == 80
    assert node_percent(NodeProgressInfo("a", "img", "ready")) == 100


def test_step_text_wording() -> None:
    creating = NodeProgressInfo("a", "ubuntu", "creating_container")
    assert step_text(creating) == "Starting container…"
    assert (
        step_text(
            NodeProgressInfo("a", "ubuntu", "pulling_image", percent=42, detail="3 of 7 layers")
        )
        == "Downloading ubuntu · 42% · 3 of 7 layers"
    )
    assert step_text(NodeProgressInfo("a", "ubuntu", "failed", detail="no such image")) == (
        "Failed: no such image"
    )
    assert step_text(NodeProgressInfo("a", "ubuntu", "ready")) == "Ready"


def test_summarize_progress_names_the_active_node() -> None:
    assert summarize_progress([]) == ("Starting containers…", 0)
    progress = [
        NodeProgressInfo("a", "alpine", "ready"),
        NodeProgressInfo("b", "ubuntu", "pulling_image", percent=50, detail="2 of 4 layers"),
        NodeProgressInfo("c", "nginx", "waiting"),
    ]
    text, overall = summarize_progress(progress)
    assert text == "Downloading ubuntu · 50% · 2 of 4 layers (b)"
    assert overall == round((100 + 40 + 0) / 3)

    failed = [
        NodeProgressInfo("a", "alpine", "ready"),
        NodeProgressInfo("b", "x", "failed", detail="boom"),
    ]
    assert summarize_progress(failed)[0] == "Failed: boom (b)"
    assert summarize_progress([NodeProgressInfo("a", "alpine", "ready")]) == (
        "All containers are running.",
        100,
    )


def test_panel_renders_one_row_per_node_with_bars_for_pulls() -> None:
    panel = StartProgressPanel()
    panel.set_progress(
        [
            NodeProgressInfo("a", "alpine", "ready"),
            NodeProgressInfo("b", "ubuntu", "pulling_image", percent=30, detail="1 of 3 layers"),
        ]
    )

    assert "Downloading ubuntu" in panel.summary_label.text()
    assert panel.overall_bar.value() == round((100 + 28) / 2)
    texts = [w.text() for w in panel._row_widgets if hasattr(w, "text")]
    assert "a" in texts and "Ready" in texts
    marks = [w.property("icon") for w in panel._row_widgets if w.property("icon")]
    assert marks == ["success"]  # the design check next to the ready node
    assert "b" in texts and any("1 of 3 layers" in t for t in texts)
    bars = [w for w in panel._row_widgets if w.metaObject().className() == "QProgressBar"]
    assert len(bars) == 1 and bars[0].value() == 30

    panel.set_progress([])
    assert panel._row_widgets == []
    assert panel.summary_label.text() == "Starting containers…"
