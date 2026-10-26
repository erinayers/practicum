"""Create New Lab chooser and Quick start configuration screens
(windows-desktop-create-lab-screen, designer-quick-start-lab, designer-windows-quick-start,
windows-desktop-windows-container-readiness).

`CreateLabScreen` mirrors the mockup's `screen-create`: two choice cards - Quick start
(single host from an OS template) and Custom Lab (the designer). Which templates can be
chosen follows the Docker engine mode the owner pushes in with `set_docker_status()`: the
Ubuntu templates while Docker Desktop serves Linux containers, the Windows template while it
serves Windows containers. The Windows readiness panel under the templates explains the
detected blocker (no Docker / Linux engine), links to Docker's and Microsoft's current
requirements and offers Retry; Practicum never switches the engine itself.

`QuickStartScreen` mirrors `screen-quickstart`: lab name, the chosen template, "What's
included" package chips (apt packages, or Chocolatey tool ids for Windows) and a step editor
for the instructions, with an "Instructor setup" toggle that reveals the
author/version/description fields. The screen only assembles a `QuickStartDraft`; the
owner turns it into a lab through `quickstart.create_quick_start_lab` and then routes the
new lab through the pre-start gate like any other Start (D-4).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from practicum_desktop import icons, theme
from practicum_desktop.docker_status import (
    DOCKER_WINDOWS_INSTALL_URL,
    WINDOWS_CONTAINER_COMPATIBILITY_URL,
    DockerStatus,
    WindowsContainerReadiness,
    windows_container_readiness,
)
from practicum_desktop.manual_editor import ManualStepsEditor, StepRow
from practicum_desktop.quickstart import (
    DEFAULT_TEMPLATE,
    TEMPLATES,
    QuickStartDraft,
    QuickStartStep,
    QuickStartTemplate,
    catalog_for,
    packages_for_options,
    template_by_key,
    validate_package_name,
)
from practicum_desktop.widgets import (
    BackLink,
    Chip,
    FlowHost,
    Panel,
    RemovableChip,
    StatusPill,
    ToggleChip,
    TopologyLink,
    TopologyNetwork,
    TopologyNode,
    TopologyView,
    bind,
    bottom_bar,
    copyable_label,
    make_button,
    page_container,
    payload_of,
    powered_by_docker,
    role_label,
)

MINI_TOPOLOGY = (
    [TopologyNode("host-a"), TopologyNode("router"), TopologyNode("host-b")],
    [TopologyNetwork("lan"), TopologyNetwork("dmz")],
    [
        TopologyLink("host-a", "lan"),
        TopologyLink("router", "lan"),
        TopologyLink("router", "dmz"),
        TopologyLink("host-b", "dmz"),
    ],
)


class ChoiceCard(QFrame):
    """.choice-card: tag in the corner, icon, title, description, custom body, CTA."""

    chosen = Signal()

    def __init__(
        self, tag: str, icon: str, title: str, description: str, cta: str, parent=None
    ) -> None:
        super().__init__(parent)
        self.setProperty("panel", "true")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 22)
        layout.setSpacing(8)

        top = QHBoxLayout()
        if icon in icons.ICONS and icons.icon_available(icon):
            icon_label = icons.icon_label(icon, 22, title)
        else:
            icon_label = QLabel(icon)
            icon_label.setAccessibleName(title)
        icon_label.setFixedSize(38, 38)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(
            f"background: {theme.LINE_SOFT}; border-radius: 10px; font-size: 18px;"
        )
        top.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        top.addStretch(1)
        top.addWidget(Chip(tag, muted=True), 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)

        layout.addWidget(role_label(title, "h2"))
        layout.addWidget(role_label(description, "muted", wrap=True))
        self.body_layout = QVBoxLayout()
        self.body_layout.setSpacing(8)
        layout.addLayout(self.body_layout, 1)
        if icons.icon_available("forward"):
            self.button = make_button(cta, kind="primary", icon="forward", icon_trailing=True)
        else:
            self.button = make_button(f"{cta} \u2192", kind="primary")
        self.button.clicked.connect(self.chosen.emit)
        layout.addWidget(self.button)


class TemplateOption(QFrame):
    """.template-option: a radio row 'Ubuntu / Terminal only'. Availability is set at runtime
    from the Docker engine mode (`set_available`); an unavailable row keeps its tooltip and
    still reacts to a click by emitting `inspected`, so the user can ask why."""

    inspected = Signal(str)  # template key - clicked (even when unavailable)

    def __init__(self, template: QuickStartTemplate, parent=None) -> None:
        super().__init__(parent)
        self.template = template
        self.available = True
        self.unavailable_reason = ""
        self.setProperty("panel", "true")
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 8, 8)
        row.setSpacing(8)
        if icons.icon_available(template.icon_name):
            icon = icons.icon_label(template.icon_name, 16, template.title)
        else:
            icon = QLabel(template.icon)
            icon.setStyleSheet("font-size: 15px;")
        row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(role_label(template.title, "label"))
        self.caption_label = role_label(template.caption, "hint", wrap=True)
        texts.addWidget(self.caption_label)
        row.addLayout(texts, 1)
        self.radio = QRadioButton()
        self.radio.setAccessibleName(f"{template.title} template")
        row.addWidget(self.radio)
        self.set_available(True, "")

    def set_available(self, available: bool, reason: str = "") -> None:
        self.available = available
        self.unavailable_reason = reason
        self.radio.setEnabled(available)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if available else Qt.CursorShape.ForbiddenCursor
        )
        suffix = "" if available else " \u00b7 unavailable"
        self.caption_label.setText(f"{self.template.caption}{suffix}")
        self.setToolTip(reason)
        self.radio.setToolTip(reason)

    def mousePressEvent(self, event) -> None:
        if self.available:
            self.radio.setChecked(True)
        self.inspected.emit(self.template.key)
        super().mousePressEvent(event)


def template_availability(
    template: QuickStartTemplate, docker: DockerStatus | None
) -> tuple[bool, str]:
    """(available, reason) for `template` given the last Docker probe. Unknown Docker state
    (None) leaves the Linux templates usable - Docker is only needed at Start - while the
    Windows template waits for a positive readiness check."""
    if template.os == "windows":
        if docker is None:
            return False, "Checking whether Docker Desktop serves Windows containers\u2026"
        readiness = windows_container_readiness(docker)
        if readiness.ready:
            return True, ""
        return False, f"{readiness.detail} {readiness.next_action}"
    if docker is not None and docker.available and docker.os_type == "windows":
        return False, (
            "Docker Desktop is serving Windows containers, so this Linux template cannot "
            "start. Right-click the Docker whale icon and choose 'Switch to Linux "
            "containers...', then select Retry."
        )
    return True, ""


class WindowsReadinessPanel(QFrame):
    """The Windows-container readiness verdict under the templates: state line with the
    design icon, the next action in plain words, links to the current Docker Desktop and
    Microsoft requirements, and Retry (windows-desktop-windows-container-readiness)."""

    retry_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panel", "soft")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.state_icon = icons.icon_label("warning", 16, "Windows containers")
        head.addWidget(self.state_icon, 0, Qt.AlignmentFlag.AlignTop)
        self.state_label = role_label("", "label", wrap=True)
        head.addWidget(self.state_label, 1)
        self.retry_button = make_button("Retry", small=True)
        self.retry_button.setToolTip(
            "Check again whether Docker Desktop is reachable and which containers it serves"
        )
        self.retry_button.clicked.connect(self.retry_requested.emit)
        head.addWidget(self.retry_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(head)
        self.action_label = copyable_label("", role="muted")
        layout.addWidget(self.action_label)
        self.links_label = QLabel(
            f'<a href="{DOCKER_WINDOWS_INSTALL_URL}">Docker Desktop Windows requirements '
            "and how to switch container mode</a> \u00b7 "
            f'<a href="{WINDOWS_CONTAINER_COMPATIBILITY_URL}">Windows host / container '
            "image compatibility</a>"
        )
        self.links_label.setProperty("role", "hint")
        self.links_label.setOpenExternalLinks(True)
        self.links_label.setWordWrap(True)
        self.links_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(self.links_label)
        self.readiness: WindowsContainerReadiness | None = None
        self.set_checking()

    def set_checking(self) -> None:
        self.readiness = None
        icons.set_label_icon(self.state_icon, "warning", 16)
        self.state_label.setText("Windows containers: checking Docker Desktop\u2026")
        self.action_label.setText("")
        self.action_label.hide()
        self.links_label.hide()
        self.retry_button.setEnabled(False)

    def set_readiness(self, readiness: WindowsContainerReadiness) -> None:
        self.readiness = readiness
        self.retry_button.setEnabled(True)
        icon_name = {"ready": "success", "linux_engine": "warning"}.get(readiness.state, "error")
        icons.set_label_icon(self.state_icon, icon_name, 16)
        if readiness.ready:
            self.state_label.setText(f"Windows containers: ready. {readiness.detail}")
            self.action_label.setText(
                "The Windows template can be used. The Ubuntu templates and other Linux labs "
                "stay unavailable until Docker Desktop is switched back to Linux containers."
            )
        else:
            self.state_label.setText(f"Windows template unavailable: {readiness.detail}")
            self.action_label.setText(readiness.next_action)
        self.action_label.show()
        self.links_label.show()


class CreateLabScreen(QWidget):
    back_requested = Signal()
    quick_start_requested = Signal(str)  # template key
    custom_requested = Signal()
    readiness_retry_requested = Signal()  # re-probe Docker (owner runs it off-thread)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._docker: DockerStatus | None = None
        self._inspected_key: str | None = None
        self.setObjectName("screen")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        page, layout = page_container()
        outer.addWidget(page, 1)

        self.back_button = BackLink("Back to my labs")
        self.back_button.clicked.connect(self.back_requested.emit)
        layout.addWidget(self.back_button)

        title = role_label("Create New Lab", "h1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        subtitle = role_label(
            "Choose a simple single-host template or build a custom networking environment.",
            "subtitle",
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(10)

        choices = QHBoxLayout()
        choices.setSpacing(20)

        self.quick_card = ChoiceCard(
            "Single host",
            "play",
            "Quick start",
            "Start a basic lab with one host. Choose an operating system to generate your "
            "image template.",
            "Quick start",
        )
        templates_row = QHBoxLayout()
        templates_row.setSpacing(8)
        self.template_hint = role_label("", "hint", wrap=True)
        self.template_description = role_label("", "muted", wrap=True)
        self.readiness_panel = WindowsReadinessPanel()
        self.readiness_panel.retry_requested.connect(self._on_readiness_retry)
        self.readiness_panel.hide()
        # The radios live in separate frames, so Qt would not make them exclusive by itself.
        self._template_group = QButtonGroup(self)
        self._template_group.setExclusive(True)
        self.template_options: list[TemplateOption] = []
        for template in TEMPLATES:
            option = TemplateOption(template)
            self._template_group.addButton(option.radio)
            option.radio.toggled.connect(self._on_template_toggled)
            option.inspected.connect(self._on_template_inspected)
            templates_row.addWidget(option, 1)
            self.template_options.append(option)
        default_index = next(
            (
                i
                for i, option in enumerate(self.template_options)
                if option.template is DEFAULT_TEMPLATE
            ),
            0,
        )
        self.template_options[default_index].radio.setChecked(True)
        self.quick_card.body_layout.addLayout(templates_row)
        self.quick_card.body_layout.addWidget(self.template_description)
        self.quick_card.body_layout.addWidget(self.template_hint)
        self.quick_card.body_layout.addWidget(self.readiness_panel)
        self.quick_card.body_layout.addStretch(1)
        self.quick_card.chosen.connect(self._on_quick_start_chosen)
        choices.addWidget(self.quick_card, 1)

        self.custom_card = ChoiceCard(
            "Multiple images",
            "tools",
            "Custom Lab",
            "Build an advanced networking lab with multiple Docker images and connections "
            "between hosts.",
            "Custom Lab",
        )
        mini = TopologyView(compact=True)
        mini.set_topology(*MINI_TOPOLOGY)
        mini.setMinimumHeight(120)
        mini.setMaximumHeight(150)
        mini.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.custom_card.body_layout.addWidget(mini, 1)
        self.custom_card.body_layout.addStretch(1)
        self.custom_card.body_layout.addWidget(
            role_label("Configure images and networking in a dedicated designer.", "hint")
        )
        self.custom_card.chosen.connect(self.custom_requested.emit)
        choices.addWidget(self.custom_card, 1)
        layout.addLayout(choices, 1)
        outer.addWidget(powered_by_docker())
        self._apply_availability()
        self._on_template_toggled()

    # ----- engine mode / readiness ----------------------------------------------------------

    @property
    def docker_status(self) -> DockerStatus | None:
        return self._docker

    def windows_readiness(self) -> WindowsContainerReadiness | None:
        return windows_container_readiness(self._docker) if self._docker is not None else None

    def set_docker_status(self, docker: DockerStatus | None) -> None:
        """Applies a fresh Docker probe: enables the templates the engine mode can run,
        updates the readiness panel. None = a check is in progress."""
        self._docker = docker
        self._apply_availability()
        if docker is None:
            self.readiness_panel.set_checking()
        else:
            self.readiness_panel.set_readiness(windows_container_readiness(docker))
        self._update_readiness_panel_visibility()
        self._on_template_toggled()

    def set_checking(self) -> None:
        self.readiness_panel.set_checking()
        self.readiness_panel.retry_button.setEnabled(False)

    def _apply_availability(self) -> None:
        for option in self.template_options:
            available, reason = template_availability(option.template, self._docker)
            option.set_available(available, reason)
        current = next((o for o in self.template_options if o.radio.isChecked()), None)
        if current is None or not current.available:
            # The selection became unavailable (engine switched): move to the first usable
            # template - the exclusive group unchecks the old one.
            fallback = next((o for o in self.template_options if o.available), None)
            if fallback is not None:
                fallback.radio.setChecked(True)

    def template_option(self, key: str) -> TemplateOption:
        return next(o for o in self.template_options if o.template.key == key)

    def _on_template_inspected(self, key: str) -> None:
        self._inspected_key = key
        self._update_readiness_panel_visibility()

    def _on_readiness_retry(self) -> None:
        self.set_checking()
        self.readiness_retry_requested.emit()

    def _update_readiness_panel_visibility(self) -> None:
        """The panel is shown when the Windows template is what the user is looking at
        (selected or clicked while unavailable) and whenever Docker is in Windows mode (then
        it explains why the Ubuntu templates are off)."""
        windows_selected = self.selected_template().os == "windows"
        docker = self._docker
        windows_engine = docker is not None and docker.available and docker.os_type == "windows"
        inspected = self._inspected_key == "windows"
        self.readiness_panel.setVisible(windows_selected or windows_engine or inspected)

    # ----- choice ---------------------------------------------------------------------------

    def _on_quick_start_chosen(self) -> None:
        option = self.template_option(self.selected_template().key)
        if not option.available:
            self._inspected_key = option.template.key
            self._update_readiness_panel_visibility()
            return
        self.quick_start_requested.emit(option.template.key)

    def selected_template(self) -> QuickStartTemplate:
        for option in self.template_options:
            if option.radio.isChecked():
                return option.template
        return TEMPLATES[0]

    def _on_template_toggled(self, _checked: bool = False) -> None:
        template = self.selected_template()
        option = self.template_option(template.key)
        if option.available:
            self.template_hint.setText(f"{template.title} selected \u00b7 {template.hint}")
        else:
            self.template_hint.setText(
                f"{template.title} selected \u00b7 unavailable: {option.unavailable_reason}"
            )
        self.template_description.setText(template.description)
        self.quick_card.button.setEnabled(option.available)
        self.quick_card.button.setToolTip("" if option.available else option.unavailable_reason)
        for opt in self.template_options:
            opt.setProperty("selected", opt.radio.isChecked())
            theme.restyle(opt)
        self._update_readiness_panel_visibility()


class QuickStartScreen(QWidget):
    back_requested = Signal()
    change_template_requested = Signal()
    cancel_requested = Signal()
    create_requested = Signal(object)  # QuickStartDraft

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._template = TEMPLATES[0]
        self._selected_options: list[str] = []  # PACKAGE_CATALOG keys, in catalogue order
        self._custom_packages: list[str] = []  # free-form apt names / Chocolatey ids
        self._windows_host_build: int | None = None
        self._option_chips: dict[str, ToggleChip] = {}
        self._package_chips: list[RemovableChip] = []
        self._build_ui()
        self.reset(TEMPLATES[0].key)

    # ----- UI --------------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setObjectName("screen")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        page, layout = page_container((44, 20, 44, 14))
        outer.addWidget(page, 1)

        self.back_button = BackLink("Back to lab selection")
        self.back_button.clicked.connect(self.back_requested.emit)
        layout.addWidget(self.back_button)

        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(role_label("Configure your Quick start lab", "h1"))
        titles.addWidget(
            role_label(
                "Choose what comes with the image and write the notes your students will follow.",
                "subtitle",
            )
        )
        top.addLayout(titles, 1)
        self.instructor_toggle = QCheckBox("Instructor setup")
        self.instructor_toggle.setProperty("toggle", True)
        self.instructor_toggle.setToolTip(
            "Show the author, version and description fields an instructor fills in before "
            "sharing this lab"
        )
        self.instructor_toggle.toggled.connect(self._on_instructor_toggled)
        top.addWidget(self.instructor_toggle, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)

        name_block = QVBoxLayout()
        name_block.setSpacing(4)
        name_block.addWidget(role_label("Lab name", "label"))
        self.name_field = QLineEdit()
        self.name_field.setMaximumWidth(360)
        self.name_field.setMaxLength(120)
        self.name_field.textChanged.connect(self._on_name_changed)
        name_block.addWidget(self.name_field)
        layout.addLayout(name_block)

        self.instructor_panel = QFrame()
        self.instructor_panel.setProperty("panel", "soft")
        instructor_grid = QGridLayout(self.instructor_panel)
        instructor_grid.setContentsMargins(12, 10, 12, 10)
        instructor_grid.setHorizontalSpacing(12)
        instructor_grid.setVerticalSpacing(4)
        instructor_grid.addWidget(role_label("Author", "label"), 0, 0)
        self.author_field = QLineEdit()
        self.author_field.setPlaceholderText("Who prepared this lab")
        self.author_field.setMaxLength(120)
        instructor_grid.addWidget(self.author_field, 1, 0)
        instructor_grid.addWidget(role_label("Version", "label"), 0, 1)
        self.version_field = QLineEdit()
        self.version_field.setPlaceholderText("e.g. 1.0.0")
        self.version_field.setMaxLength(40)
        instructor_grid.addWidget(self.version_field, 1, 1)
        instructor_grid.addWidget(role_label("Description", "label"), 0, 2)
        self.description_field = QLineEdit()
        self.description_field.setPlaceholderText("One line students see before starting")
        self.description_field.setMaxLength(2000)
        instructor_grid.addWidget(self.description_field, 1, 2)
        instructor_grid.setColumnStretch(2, 2)
        self.instructor_panel.hide()
        layout.addWidget(self.instructor_panel)

        template_bar = QFrame()
        template_bar.setProperty("panel", "soft")
        template_row = QHBoxLayout(template_bar)
        template_row.setContentsMargins(14, 8, 14, 8)
        template_row.setSpacing(8)
        self.template_icon = icons.icon_label("terminal", 16, "Template")
        template_row.addWidget(self.template_icon)
        self.template_label = QLabel("")
        template_row.addWidget(self.template_label)
        template_row.addStretch(1)
        change = make_button("Change template", kind="link")
        change.clicked.connect(self.change_template_requested.emit)
        template_row.addWidget(change)
        layout.addWidget(template_bar)

        columns = QHBoxLayout()
        columns.setSpacing(20)

        self.included_panel = Panel(padding=16)
        self.included_panel.body_layout.addWidget(role_label("What's included", "h3"))
        self.included_caption = role_label("", "muted", wrap=True)
        self.included_panel.body_layout.addWidget(self.included_caption)
        base_host = FlowHost()
        self.base_layout = base_host.flow
        self._base_host = base_host
        self.included_panel.body_layout.addWidget(base_host)
        self.catalog_title = role_label("Popular software", "label")
        self.included_panel.body_layout.addWidget(self.catalog_title)
        self.catalog_hint = role_label(
            "Tick what the lab should come with - installed at first start.", "hint", wrap=True
        )
        self.included_panel.body_layout.addWidget(self.catalog_hint)
        catalog_host = FlowHost()
        self.catalog_layout = catalog_host.flow
        self._catalog_host = catalog_host
        self.included_panel.body_layout.addWidget(catalog_host)
        self.included_panel.body_layout.addStretch(1)
        self.other_packages_title = role_label("Other packages", "label")
        self.included_panel.body_layout.addWidget(self.other_packages_title)
        chips_host = FlowHost()
        self.chips_layout = chips_host.flow
        self._chips_host = chips_host
        self.included_panel.body_layout.addWidget(chips_host)
        self.package_error = copyable_label("", role="error")
        self.package_error.hide()
        self.included_panel.body_layout.addWidget(self.package_error)
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.package_field = QLineEdit()
        self.package_field.setPlaceholderText("Any Ubuntu package name, e.g. htop")
        self.package_field.returnPressed.connect(self._on_add_package)
        add_row.addWidget(self.package_field, 1)
        self.add_package_button = make_button("Add", small=True)
        self.add_package_button.clicked.connect(self._on_add_package)
        add_row.addWidget(self.add_package_button)
        self.included_panel.body_layout.addLayout(add_row)
        self.install_note = role_label("", "hint", wrap=True)
        self.included_panel.body_layout.addWidget(self.install_note)
        columns.addWidget(self.included_panel, 1)

        self.steps_panel = Panel(padding=16)
        self.steps_panel.body_layout.addWidget(role_label("Lab instructions", "h3"))
        self.steps_panel.body_layout.addWidget(
            role_label("Steps students complete, shown in the instructions flyout.", "muted")
        )
        self.manual_editor = ManualStepsEditor()
        self.manual_editor.changed.connect(self._update_status)
        self.steps_panel.body_layout.addWidget(self.manual_editor, 1)
        self.add_step_button = self.manual_editor.add_button
        columns.addWidget(self.steps_panel, 1)
        layout.addLayout(columns, 1)

        bar, bar_row = bottom_bar()
        self.status_pill = StatusPill("")
        bar_row.addWidget(self.status_pill, 1)
        self.cancel_button = make_button("Cancel")
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        bar_row.addWidget(self.cancel_button)
        self.create_button = make_button("Create Lab", kind="primary")
        self.create_button.clicked.connect(self._on_create_clicked)
        bar_row.addWidget(self.create_button)
        outer.addWidget(bar)

    # ----- state -----------------------------------------------------------------------

    def reset(self, template_key: str) -> None:
        """Fresh draft for `template_key` (defaults: name, packages, no steps)."""
        draft = QuickStartDraft(template=template_by_key(template_key))
        self._template = draft.template
        self.name_field.setText(draft.name or draft.template.default_name)
        self.author_field.clear()
        self.version_field.clear()
        self.description_field.clear()
        self.instructor_toggle.setChecked(False)
        glyph = ""
        if icons.icon_available(draft.template.icon_name):
            icons.set_label_icon(self.template_icon, draft.template.icon_name, 16)
            self.template_icon.setToolTip(f"{draft.template.title} template")
            self.template_icon.show()
        else:
            self.template_icon.hide()
            glyph = f"{draft.template.icon} "
        self.template_label.setText(
            f"{glyph}<b>{draft.template.title}</b> "
            f'<span style="color:{theme.MUTED}">{draft.template.caption} \u00b7 Single host</span>'
        )
        self.manual_editor.clear()
        self.included_caption.setText(draft.template.packages_caption)
        self.catalog_title.setText(draft.template.catalog_title)
        self.catalog_hint.setText(draft.template.catalog_hint)
        self.other_packages_title.setText(draft.template.other_packages_title)
        self.package_field.setPlaceholderText(draft.template.package_placeholder)
        self.install_note.setText(draft.template.install_note)
        self._windows_host_build = None
        self._selected_options = list(draft.template.default_options)
        self._custom_packages = []
        self._rebuild_catalog()
        self._rebuild_chips()
        self.package_field.clear()
        self.package_error.hide()
        self.set_busy(False)
        self._update_status()

    def set_windows_host_build(self, build: int | None) -> None:
        """The Docker host's Windows build (from the readiness check) - picks the pinned
        Server Core tag for a Windows draft."""
        self._windows_host_build = build

    def draft(self) -> QuickStartDraft:
        return QuickStartDraft(
            name=self.name_field.text().strip() or self._template.default_name,
            template=self._template,
            packages=self.packages,
            steps=[step for step in self.manual_editor.steps() if step.title],
            author=self.author_field.text(),
            version=self.version_field.text(),
            description=self.description_field.text(),
            windows_host_build=self._windows_host_build,
        )

    @property
    def template(self) -> QuickStartTemplate:
        return self._template

    @property
    def packages(self) -> list[str]:
        """Package names (apt) or ids (Chocolatey): the ticked catalogue entries (expanded)
        plus custom names."""
        names = packages_for_options(self._selected_options, self._template.kind)
        for name in self._custom_packages:
            if name not in names:
                names.append(name)
        return names

    @property
    def selected_options(self) -> list[str]:
        return list(self._selected_options)

    def set_busy(self, busy: bool, text: str = "") -> None:
        self.create_button.setEnabled(not busy)
        self.cancel_button.setEnabled(not busy)
        if busy:
            self.status_pill.set_state(text or "Creating lab\u2026", theme.AMBER)
        else:
            self._update_status()

    def show_error(self, text: str) -> None:
        self.set_busy(False)
        self.status_pill.set_state(text, theme.DANGER)

    # ----- packages --------------------------------------------------------------------

    def _rebuild_catalog(self) -> None:
        """One toggle chip per popular package of this template kind."""
        self.base_layout.clear()
        self.base_layout.addWidget(Chip(self._template.base_label, muted=True))
        self.catalog_layout.clear()
        self._option_chips = {}
        for option in catalog_for(self._template.kind):
            chip = ToggleChip(option.key, option.description)
            chip.setChecked(option.key in self._selected_options)
            bind(chip, self._on_option_toggled, option.key)
            self.catalog_layout.addWidget(chip)
            self._option_chips[option.key] = chip
        self._catalog_host.refit()
        self._base_host.refit()

    def _on_option_toggled(self) -> None:
        key = payload_of(self.sender())
        chip = self._option_chips.get(key)
        if chip is None:
            return
        self.set_option(key, chip.isChecked())

    def set_option(self, key: str, selected: bool) -> None:
        if selected and key not in self._selected_options:
            self._selected_options.append(key)
            order = [o.key for o in catalog_for(self._template.kind)]
            self._selected_options.sort(key=lambda k: order.index(k) if k in order else len(order))
        elif not selected and key in self._selected_options:
            self._selected_options.remove(key)
        chip = self._option_chips.get(key)
        if chip is not None and chip.isChecked() != selected:
            chip.setChecked(selected)
        self._update_status()

    def _rebuild_chips(self) -> None:
        self.chips_layout.clear()
        self._package_chips = []
        for package in self._custom_packages:
            chip = RemovableChip(package)
            chip.removed.connect(self.remove_package)
            self.chips_layout.addWidget(chip)
            self._package_chips.append(chip)
        self._chips_host.refit()
        self._update_status()

    def add_package(self, name: str) -> bool:
        """Adds a free-form apt package; a catalogue key ticks its chip instead."""
        name = name.strip().lower()
        error = validate_package_name(name, self._template.kind)
        if error is None and name in self._option_chips:
            self.set_option(name, True)
            self.package_error.hide()
            return True
        if error is None and name in self.packages:
            error = f"'{name}' is already in the list."
        if error is not None:
            self.package_error.setText(error)
            self.package_error.show()
            return False
        self.package_error.hide()
        self._custom_packages.append(name)
        self._rebuild_chips()
        return True

    def remove_package(self, name: str) -> None:
        self._custom_packages = [p for p in self._custom_packages if p != name]
        self._rebuild_chips()

    def _on_add_package(self) -> None:
        if self.add_package(self.package_field.text()):
            self.package_field.clear()

    # ----- steps -----------------------------------------------------------------------

    @property
    def _step_rows(self) -> list[StepRow]:
        return self.manual_editor.rows

    def add_step(self, step: QuickStartStep | None = None) -> StepRow:
        return self.manual_editor.add_step(step)

    def _remove_step_row(self, row: StepRow) -> None:
        self.manual_editor.remove_row(row)

    @property
    def steps(self) -> list[QuickStartStep]:
        return self.manual_editor.steps()

    # ----- status / create ---------------------------------------------------------------

    def _on_name_changed(self, _text: str) -> None:
        self._update_status()

    def _on_instructor_toggled(self, checked: bool) -> None:
        self.instructor_panel.setVisible(checked)

    def _update_status(self) -> None:
        name = self.name_field.text().strip()
        if not name:
            self.status_pill.set_state("A lab name is required.", theme.AMBER)
            self.create_button.setEnabled(False)
            return
        parts = ["Draft valid", "1 machine"]
        count = len(self.packages)
        if count:
            parts.append(f"{count} package{'s' if count != 1 else ''}")
        titled = self.manual_editor.titled_count()
        if titled:
            parts.append(f"{titled} step{'s' if titled != 1 else ''}")
        self.status_pill.set_state(" \u00b7 ".join(parts), theme.GREEN)
        self.create_button.setEnabled(True)

    def _on_create_clicked(self) -> None:
        if not self.name_field.text().strip():
            self._update_status()
            return
        self.create_requested.emit(self.draft())
