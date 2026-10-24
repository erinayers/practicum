from __future__ import annotations

from practicum_desktop.create_lab import CreateLabScreen, QuickStartScreen
from practicum_desktop.quickstart import QuickStartDraft, QuickStartStep

DEFAULT_PACKAGES = ("git", "python3", "python3-pip", "curl")  # the terminal template's defaults

# ----- Create New Lab chooser -----------------------------------------------------------------


def test_create_screen_defaults_to_the_desktop_and_disables_windows() -> None:
    screen = CreateLabScreen()

    assert [o.template.key for o in screen.template_options] == [
        "ubuntu-desktop",
        "ubuntu",
        "windows",
    ]
    assert screen.selected_template().key == "ubuntu-desktop"
    assert "Ubuntu Desktop selected" in screen.template_hint.text()
    assert "no terminal" in screen.template_hint.text()
    assert "non-IT" in screen.template_description.text()
    windows = screen.template_options[2]
    assert windows.radio.isEnabled() is False
    assert "Coming soon" in windows.toolTip()

    screen.template_options[1].radio.setChecked(True)
    assert screen.selected_template().key == "ubuntu"
    assert "Open shell" in screen.template_hint.text()
    assert screen.quick_card.button.text() == "Quick start \u2192"
    assert screen.custom_card.button.text() == "Custom Lab \u2192"


def test_create_screen_emits_choices_and_back() -> None:
    screen = CreateLabScreen()
    fired: list = []
    screen.quick_start_requested.connect(lambda key: fired.append(("quick", key)))
    screen.custom_requested.connect(lambda: fired.append("custom"))
    screen.back_requested.connect(lambda: fired.append("back"))

    screen.quick_card.button.click()
    screen.template_options[1].radio.setChecked(True)
    screen.quick_card.button.click()
    screen.custom_card.button.click()
    screen.back_button.click()

    assert fired == [("quick", "ubuntu-desktop"), ("quick", "ubuntu"), "custom", "back"]


# ----- Quick start configuration ---------------------------------------------------------------


def test_quick_start_screen_starts_from_the_template_defaults() -> None:
    screen = QuickStartScreen()

    assert screen.name_field.text() == "Ubuntu Desktop Quick Start"
    assert screen.packages == []
    assert screen.steps == []
    assert screen.instructor_panel.isHidden()
    assert "Ubuntu Desktop" in screen.template_label.text()
    assert "already comes with a browser" in screen.included_caption.text()
    assert screen.status_pill.text_label.text() == "Draft valid \u00b7 1 machine"
    assert screen.create_button.isEnabled()
    assert screen.draft().template.key == "ubuntu-desktop"

    screen.reset("ubuntu")

    assert screen.name_field.text() == "Ubuntu Quick Start"
    assert screen.packages == list(DEFAULT_PACKAGES)
    assert "Ubuntu 22.04" in screen.included_caption.text()
    assert screen.status_pill.text_label.text() == "Draft valid \u00b7 1 machine \u00b7 4 packages"


def test_popular_software_chips_drive_the_package_list() -> None:
    screen = QuickStartScreen()
    screen.reset("ubuntu")
    assert screen.selected_options == ["git", "python3", "curl"]
    assert screen._option_chips["git"].isChecked()
    assert not screen._option_chips["tcpdump"].isChecked()
    assert "libreoffice" not in screen._option_chips  # desktop-only software

    screen._option_chips["tcpdump"].click()
    screen._option_chips["python3"].click()

    assert screen.selected_options == ["git", "curl", "tcpdump"]
    assert screen.packages == ["git", "curl", "tcpdump"]
    assert "3 packages" in screen.status_pill.text_label.text()

    screen.reset("ubuntu-desktop")
    assert screen.selected_options == []
    assert "libreoffice" in screen._option_chips and "tcpdump" not in screen._option_chips
    screen.set_option("libreoffice", True)
    assert screen.packages == ["libreoffice"]
    assert screen.draft().packages == ["libreoffice"]


def test_other_packages_can_be_added_removed_and_are_validated() -> None:
    screen = QuickStartScreen()
    screen.reset("ubuntu")

    screen.package_field.setText("Htop")
    screen.add_package_button.click()
    assert screen.packages == ["git", "python3", "python3-pip", "curl", "htop"]  # lower-cased
    assert screen.package_field.text() == ""

    assert screen.add_package("rm -rf") is False
    assert "not a valid package name" in screen.package_error.text()
    assert screen.add_package("htop") is False
    assert "already in the list" in screen.package_error.text()
    assert screen.add_package("tcpdump") is True  # a catalogue name ticks its chip instead
    assert screen._option_chips["tcpdump"].isChecked()
    assert screen._package_chips[0].value == "htop"

    screen.remove_package("htop")
    assert "htop" not in screen.packages
    assert "5 packages" in screen.status_pill.text_label.text()


def test_steps_editor_numbers_renumbers_and_builds_the_draft() -> None:
    screen = QuickStartScreen()

    first = screen.add_step()
    first.title_field.setText("Install dependencies")
    first.details_field.setPlainText("pip install -r requirements.txt")
    second = screen.add_step(QuickStartStep("Start the API", "flask run"))
    third = screen.add_step()
    assert [row.number_label.text() for row in screen._step_rows] == ["1", "2", "3"]
    assert "2 steps" in screen.status_pill.text_label.text()  # the untitled one is not counted

    screen._remove_step_row(first)

    assert [row.number_label.text() for row in screen._step_rows] == ["1", "2"]
    assert screen._step_rows[0] is second
    draft = screen.draft()
    assert draft.steps == [QuickStartStep("Start the API", "flask run")]
    assert third in screen._step_rows


def test_instructor_toggle_reveals_metadata_that_lands_in_the_draft() -> None:
    screen = QuickStartScreen()
    screen.reset("ubuntu")

    screen.instructor_toggle.setChecked(True)
    assert screen.instructor_panel.isHidden() is False
    screen.author_field.setText("Dr. Ada")
    screen.version_field.setText("2.0")
    screen.description_field.setText("Look at packets.")
    screen.name_field.setText("Explore network traffic")

    draft = screen.draft()

    assert draft == QuickStartDraft(
        name="Explore network traffic",
        template=screen._template,
        packages=["git", "python3", "python3-pip", "curl"],
        steps=[],
        author="Dr. Ada",
        version="2.0",
        description="Look at packets.",
    )


def test_empty_name_blocks_create_and_explains() -> None:
    screen = QuickStartScreen()
    created: list = []
    screen.create_requested.connect(created.append)

    screen.name_field.setText("   ")

    assert screen.create_button.isEnabled() is False
    assert "name is required" in screen.status_pill.text_label.text()
    screen._on_create_clicked()
    assert created == []

    screen.name_field.setText("My lab")
    screen.create_button.click()

    assert len(created) == 1
    assert created[0].name == "My lab"


def test_busy_and_error_states_drive_the_bottom_bar() -> None:
    screen = QuickStartScreen()

    screen.set_busy(True, "Creating lab\u2026")
    assert not screen.create_button.isEnabled()
    assert not screen.cancel_button.isEnabled()
    assert screen.status_pill.text_label.text() == "Creating lab\u2026"

    screen.show_error("name: Field required")
    assert screen.create_button.isEnabled()
    assert screen.status_pill.text_label.text() == "name: Field required"

    screen.reset("ubuntu")
    assert screen.status_pill.text_label.text().startswith("Draft valid")


def test_reset_returns_to_defaults_for_the_chosen_template() -> None:
    screen = QuickStartScreen()
    screen.reset("ubuntu")
    screen.add_step(QuickStartStep("x"))
    screen.set_option("git", False)
    screen.add_package("htop")
    screen.name_field.setText("changed")
    screen.instructor_toggle.setChecked(True)

    screen.reset("ubuntu")

    assert screen.steps == []
    assert screen.packages == list(DEFAULT_PACKAGES)
    assert screen.name_field.text() == "Ubuntu Quick Start"
    assert screen.instructor_toggle.isChecked() is False


def test_navigation_signals() -> None:
    screen = QuickStartScreen()
    fired: list[str] = []
    screen.back_requested.connect(lambda: fired.append("back"))
    screen.cancel_requested.connect(lambda: fired.append("cancel"))

    screen.back_button.click()
    screen.cancel_button.click()

    assert fired == ["back", "cancel"]
