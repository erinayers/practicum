from __future__ import annotations

from practicum_desktop.create_lab import CreateLabScreen, QuickStartScreen, template_availability
from practicum_desktop.docker_status import DockerStatus
from practicum_desktop.quickstart import QuickStartDraft, QuickStartStep, template_by_key

DEFAULT_PACKAGES = ("git", "python3", "python3-pip", "curl")  # the terminal template's defaults

LINUX_DOCKER = DockerStatus(available=True, detail="ok", os_type="linux", server_version="27.3")
WINDOWS_DOCKER = DockerStatus(
    available=True, detail="ok", os_type="windows", server_version="27.3", host_build=22631
)
NO_DOCKER = DockerStatus(available=False, detail="Docker is not running.")

# ----- Create New Lab chooser -----------------------------------------------------------------


def test_create_screen_defaults_to_the_desktop_and_holds_windows_until_checked() -> None:
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
    assert "Checking whether Docker Desktop serves Windows containers" in windows.toolTip()
    assert screen.readiness_panel.isHidden()  # nobody asked about Windows yet

    screen.template_options[1].radio.setChecked(True)
    assert screen.selected_template().key == "ubuntu"
    assert "Open shell" in screen.template_hint.text()
    assert screen.quick_card.button.text() == "Quick start"
    assert not screen.quick_card.button.icon().isNull()  # the design "forward" icon
    assert screen.custom_card.button.text() == "Custom Lab"
    assert screen.quick_card.button.isEnabled()


def test_template_availability_follows_the_docker_engine_mode() -> None:
    desktop, terminal, windows = (
        template_by_key(k) for k in ("ubuntu-desktop", "ubuntu", "windows")
    )

    assert template_availability(desktop, None) == (True, "")
    assert template_availability(desktop, LINUX_DOCKER) == (True, "")
    assert template_availability(desktop, NO_DOCKER) == (True, "")  # Docker is only needed at Start
    assert template_availability(windows, LINUX_DOCKER)[0] is False
    assert "Switch to Windows containers" in template_availability(windows, LINUX_DOCKER)[1]
    assert template_availability(windows, NO_DOCKER)[0] is False
    assert "Start Docker Desktop" in template_availability(windows, NO_DOCKER)[1]
    assert template_availability(windows, WINDOWS_DOCKER) == (True, "")
    assert template_availability(terminal, WINDOWS_DOCKER)[0] is False
    assert "Switch to Linux containers" in template_availability(terminal, WINDOWS_DOCKER)[1]


def test_linux_engine_keeps_ubuntu_templates_and_explains_windows_with_links_and_retry() -> None:
    screen = CreateLabScreen()
    retries: list[str] = []
    screen.readiness_retry_requested.connect(lambda: retries.append("retry"))

    screen.set_docker_status(LINUX_DOCKER)

    assert screen.template_options[0].radio.isEnabled()
    assert screen.template_options[1].radio.isEnabled()
    windows = screen.template_options[2]
    assert windows.radio.isEnabled() is False
    assert "unavailable" in windows.caption_label.text()
    assert "Switch to Windows containers" in windows.toolTip()
    assert screen.readiness_panel.isHidden()  # Ubuntu users are not bothered with it

    # Clicking the unavailable row asks "why?": the panel opens with the blocker, the next
    # action, the two requirement links and Retry.
    windows.inspected.emit("windows")
    assert screen.readiness_panel.isHidden() is False
    panel = screen.readiness_panel
    assert "Windows template unavailable" in panel.state_label.text()
    assert "serving Linux containers" in panel.state_label.text()
    assert "Switch to Windows containers" in panel.action_label.text()
    assert "never switches the mode" in panel.action_label.text()
    assert "docs.docker.com/desktop/setup/install/windows-install" in panel.links_label.text()
    assert "version-compatibility" in panel.links_label.text()
    assert panel.state_icon.property("icon") == "warning"
    assert panel.retry_button.isEnabled()

    panel.retry_button.click()
    assert retries == ["retry"]
    assert panel.retry_button.isEnabled() is False  # until the owner reports back
    assert "checking" in panel.state_label.text().lower()

    screen.set_docker_status(LINUX_DOCKER)  # the owner's answer: still Linux
    assert panel.retry_button.isEnabled()
    assert screen.selected_template().key == "ubuntu-desktop"
    assert screen.quick_card.button.isEnabled()


def test_windows_engine_enables_the_windows_template_and_disables_the_ubuntu_ones() -> None:
    screen = CreateLabScreen()
    chosen: list[str] = []
    screen.quick_start_requested.connect(chosen.append)

    screen.set_docker_status(WINDOWS_DOCKER)

    desktop, terminal, windows = screen.template_options
    assert windows.radio.isEnabled() and windows.radio.isChecked()  # fell back to the usable one
    assert desktop.radio.isEnabled() is False and terminal.radio.isEnabled() is False
    assert "Switch to Linux containers" in desktop.toolTip()
    assert screen.selected_template().key == "windows"
    assert "Windows selected" in screen.template_hint.text()
    assert "Open PowerShell" in screen.template_hint.text()
    assert screen.readiness_panel.isHidden() is False  # explains why Ubuntu is off
    assert "Windows containers: ready" in screen.readiness_panel.state_label.text()
    assert "host build 22631" in screen.readiness_panel.state_label.text()
    assert screen.readiness_panel.state_icon.property("icon") == "success"
    assert screen.quick_card.button.isEnabled()

    screen.quick_card.button.click()
    assert chosen == ["windows"]

    # Switching Docker back to Linux containers (Retry) takes the Windows template away again
    # and falls back to the default Ubuntu template.
    screen.set_docker_status(LINUX_DOCKER)
    assert windows.radio.isEnabled() is False and windows.radio.isChecked() is False
    assert screen.selected_template().key == "ubuntu-desktop"
    assert desktop.radio.isEnabled()


def test_no_docker_explains_and_keeps_the_windows_cta_disabled() -> None:
    screen = CreateLabScreen()
    chosen: list[str] = []
    screen.quick_start_requested.connect(chosen.append)

    screen.set_docker_status(NO_DOCKER)
    windows = screen.template_options[2]
    windows.inspected.emit("windows")

    assert windows.radio.isEnabled() is False
    assert "Docker is not reachable" in screen.readiness_panel.state_label.text()
    assert "Start Docker Desktop" in screen.readiness_panel.action_label.text()
    assert screen.readiness_panel.state_icon.property("icon") == "error"
    # Linux templates still work (creation needs no Docker; the gate checks at Start).
    assert screen.template_options[0].radio.isEnabled()
    assert screen.quick_card.button.isEnabled()


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


def test_windows_quick_start_offers_tool_chips_and_chocolatey_ids() -> None:
    screen = QuickStartScreen()
    screen.reset("windows")
    screen.set_windows_host_build(22631)

    assert screen.name_field.text() == "Windows Quick Start"
    assert "Windows" in screen.template_label.text()
    assert screen.template_icon.property("icon") == "terminal"
    assert "Chocolatey" in screen.included_caption.text()
    assert screen.catalog_title.text() == "Popular tools"
    assert screen.other_packages_title.text() == "Other Chocolatey packages"
    assert "Chocolatey package id" in screen.package_field.placeholderText()
    assert "several minutes" in screen.install_note.text()
    assert screen.selected_options == ["git"]
    assert screen.packages == ["git"]
    assert "7zip" in screen._option_chips and "tcpdump" not in screen._option_chips
    assert "libreoffice" not in screen._option_chips

    screen.set_option("nodejs", True)
    screen.set_option("pwsh", True)
    assert screen.packages == ["git", "nodejs-lts", "powershell-core"]  # Chocolatey ids

    assert screen.add_package("g++") is False  # apt syntax, not a Chocolatey id
    assert "Chocolatey package id" in screen.package_error.text()
    assert screen.add_package("git") is True  # catalogue key → ticks the chip, no duplicate
    assert screen.packages.count("git") == 1
    assert screen.add_package("nodejs-lts") is False  # already there through its chip
    assert "already in the list" in screen.package_error.text()
    assert screen.add_package("Notepad.Plus") is True
    assert screen._package_chips[0].value == "notepad.plus"

    draft = screen.draft()
    assert draft.template.key == "windows"
    assert draft.packages == ["git", "nodejs-lts", "powershell-core", "notepad.plus"]
    assert draft.windows_host_build == 22631
    assert "4 packages" in screen.status_pill.text_label.text()

    screen.reset("ubuntu")  # back to apt wording and apt validation
    assert screen.catalog_title.text() == "Popular software"
    assert screen.add_package("g++") is True
    assert screen.draft().windows_host_build is None


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
