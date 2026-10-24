"""Create New Lab chooser and Quick start configuration screens
(windows-desktop-create-lab-screen, designer-quick-start-lab).

`CreateLabScreen` mirrors the mockup's `screen-create`: two choice cards - Quick start
(single host from an OS template) and Custom Lab (the designer). `QuickStartScreen` mirrors
`screen-quickstart`: lab name, the chosen template, "What's included" package chips and a
step editor for the instructions, with an "Instructor setup" toggle that reveals the
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
    QPlainTextEdit,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from practicum_desktop import theme
from practicum_desktop.quickstart import (
    DEFAULT_TEMPLATE,
    TEMPLATES,
    QuickStartDraft,
    QuickStartStep,
    QuickStartTemplate,
    catalog_for,
    catalog_option,
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
    discard,
    make_button,
    page_container,
    payload_of,
    powered_by_docker,
    role_label,
    style_frame,
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
        icon_label = QLabel(icon)
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
        self.button = make_button(f"{cta} \u2192", kind="primary")
        self.button.clicked.connect(self.chosen.emit)
        layout.addWidget(self.button)


class TemplateOption(QFrame):
    """.template-option: a radio row 'Ubuntu / Linux template'."""

    def __init__(self, template: QuickStartTemplate, parent=None) -> None:
        super().__init__(parent)
        self.template = template
        self.setProperty("panel", "true")
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if template.available
            else Qt.CursorShape.ForbiddenCursor
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 8, 8)
        row.setSpacing(8)
        icon = QLabel(template.icon)
        icon.setStyleSheet("font-size: 15px;")
        row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(role_label(template.title, "label"))
        caption = template.caption if template.available else f"{template.caption} \u00b7 soon"
        caption_label = role_label(caption, "hint", wrap=True)
        texts.addWidget(caption_label)
        row.addLayout(texts, 1)
        self.radio = QRadioButton()
        self.radio.setEnabled(template.available)
        row.addWidget(self.radio)
        if not template.available:
            self.setToolTip(template.unavailable_reason)
            self.radio.setToolTip(template.unavailable_reason)

    def mousePressEvent(self, event) -> None:
        if self.template.available:
            self.radio.setChecked(True)
        super().mousePressEvent(event)


class CreateLabScreen(QWidget):
    back_requested = Signal()
    quick_start_requested = Signal(str)  # template key
    custom_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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
            "\u25b6",
            "Quick start",
            "Start a basic lab with one host. Choose an operating system to generate your "
            "image template.",
            "Quick start",
        )
        templates_row = QHBoxLayout()
        templates_row.setSpacing(8)
        self.template_hint = role_label("", "hint", wrap=True)
        self.template_description = role_label("", "muted", wrap=True)
        # The radios live in separate frames, so Qt would not make them exclusive by itself.
        self._template_group = QButtonGroup(self)
        self._template_group.setExclusive(True)
        self.template_options: list[TemplateOption] = []
        for template in TEMPLATES:
            option = TemplateOption(template)
            self._template_group.addButton(option.radio)
            option.radio.toggled.connect(self._on_template_toggled)
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
        self.quick_card.body_layout.addStretch(1)
        self.quick_card.chosen.connect(self._on_quick_start_chosen)
        choices.addWidget(self.quick_card, 1)

        self.custom_card = ChoiceCard(
            "Multiple images",
            "\u25c6",
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
        self._on_template_toggled()

    def _on_quick_start_chosen(self) -> None:
        self.quick_start_requested.emit(self.selected_template().key)

    def selected_template(self) -> QuickStartTemplate:
        for option in self.template_options:
            if option.radio.isChecked():
                return option.template
        return TEMPLATES[0]

    def _on_template_toggled(self, _checked: bool = False) -> None:
        template = self.selected_template()
        self.template_hint.setText(f"{template.title} selected \u00b7 {template.hint}")
        self.template_description.setText(template.description)
        for option in self.template_options:
            option.setProperty("selected", option.radio.isChecked())
            theme.restyle(option)


class StepRow(QFrame):
    """One editable instruction step: number, title, details, remove."""

    changed = Signal()
    removed = Signal(object)

    def __init__(self, number: int, step: QuickStartStep | None = None, parent=None) -> None:
        super().__init__(parent)
        style_frame(self, f"border-bottom: 1px dashed {theme.LINE_SOFT};")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 6, 0, 8)
        row.setSpacing(8)
        self.number_label = QLabel(str(number))
        self.number_label.setFixedSize(18, 18)
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_label.setStyleSheet(
            f"background: {theme.LINE_SOFT}; color: {theme.MUTED}; border-radius: 9px;"
            " font-size: 10px;"
        )
        row.addWidget(self.number_label, 0, Qt.AlignmentFlag.AlignTop)
        fields = QVBoxLayout()
        fields.setSpacing(4)
        self.title_field = QLineEdit(step.title if step else "")
        self.title_field.setPlaceholderText("Step title, e.g. Install dependencies")
        self.title_field.textChanged.connect(self._on_title_changed)
        fields.addWidget(self.title_field)
        self.details_field = QPlainTextEdit(step.details if step else "")
        self.details_field.setPlaceholderText(
            "What the student does (Markdown; use ``` for commands)"
        )
        self.details_field.setFixedHeight(56)
        self.details_field.textChanged.connect(self.changed.emit)
        fields.addWidget(self.details_field)
        row.addLayout(fields, 1)
        remove = make_button("\u00d7", kind="ghost")
        remove.setToolTip("Remove this step")
        remove.setStyleSheet("padding: 0 6px; font-size: 15px;")
        remove.clicked.connect(self._on_remove_clicked)
        row.addWidget(remove, 0, Qt.AlignmentFlag.AlignTop)

    def _on_title_changed(self, _text: str) -> None:
        self.changed.emit()

    def _on_remove_clicked(self) -> None:
        self.removed.emit(self)

    def set_number(self, number: int) -> None:
        self.number_label.setText(str(number))

    def step(self) -> QuickStartStep:
        return QuickStartStep(
            title=self.title_field.text().strip(), details=self.details_field.toPlainText()
        )


class QuickStartScreen(QWidget):
    back_requested = Signal()
    change_template_requested = Signal()
    cancel_requested = Signal()
    create_requested = Signal(object)  # QuickStartDraft

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._template = TEMPLATES[0]
        self._selected_options: list[str] = []  # PACKAGE_CATALOG keys, in catalogue order
        self._custom_packages: list[str] = []  # free-form apt names
        self._option_chips: dict[str, ToggleChip] = {}
        self._package_chips: list[RemovableChip] = []
        self._step_rows: list[StepRow] = []
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
        self.included_panel.body_layout.addWidget(role_label("Popular software", "label"))
        self.included_panel.body_layout.addWidget(
            role_label("Tick what the lab should come with - installed at first start.", "hint")
        )
        catalog_host = FlowHost()
        self.catalog_layout = catalog_host.flow
        self._catalog_host = catalog_host
        self.included_panel.body_layout.addWidget(catalog_host)
        self.included_panel.body_layout.addStretch(1)
        self.included_panel.body_layout.addWidget(role_label("Other packages", "label"))
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
        self.install_note = role_label(
            "Installing takes a minute or two after the lab starts; the Lab nodes table and the "
            "node's shell show when the packages are ready.",
            "hint",
            wrap=True,
        )
        self.included_panel.body_layout.addWidget(self.install_note)
        columns.addWidget(self.included_panel, 1)

        self.steps_panel = Panel(padding=16)
        self.steps_panel.body_layout.addWidget(role_label("Lab instructions", "h3"))
        self.steps_panel.body_layout.addWidget(
            role_label("Steps students complete, shown in the instructions flyout.", "muted")
        )
        self.steps_scroll = QScrollArea()
        self.steps_scroll.setWidgetResizable(True)
        self.steps_scroll.setFrameShape(QFrame.Shape.NoFrame)
        steps_host = QWidget()
        self.steps_layout = QVBoxLayout(steps_host)
        self.steps_layout.setContentsMargins(0, 0, 6, 0)
        self.steps_layout.setSpacing(0)
        self.steps_layout.addStretch(1)
        self.steps_scroll.setWidget(steps_host)
        self.steps_panel.body_layout.addWidget(self.steps_scroll, 1)
        self.add_step_button = make_button("+ Add step", small=True)
        self.add_step_button.clicked.connect(self._on_add_step_clicked)
        self.steps_panel.body_layout.addWidget(self.add_step_button, 0, Qt.AlignmentFlag.AlignLeft)
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
        self.template_label.setText(
            f"{draft.template.icon} <b>{draft.template.title}</b> "
            f'<span style="color:{theme.MUTED}">{draft.template.caption} \u00b7 Single host</span>'
        )
        self.included_caption.setText(draft.template.packages_caption)
        for row in list(self._step_rows):
            self._remove_step_row(row)
        self._selected_options = list(draft.template.default_options)
        self._custom_packages = []
        self._rebuild_catalog()
        self._rebuild_chips()
        self.package_field.clear()
        self.package_error.hide()
        self.set_busy(False)
        self._update_status()

    def draft(self) -> QuickStartDraft:
        return QuickStartDraft(
            name=self.name_field.text().strip() or self._template.default_name,
            template=self._template,
            packages=self.packages,
            steps=[row.step() for row in self._step_rows if row.step().title],
            author=self.author_field.text(),
            version=self.version_field.text(),
            description=self.description_field.text(),
        )

    @property
    def packages(self) -> list[str]:
        """Apt package names: the ticked catalogue entries (expanded) plus custom names."""
        names = packages_for_options(self._selected_options)
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
        error = validate_package_name(name)
        if error is None and catalog_option(name) is not None and name in self._option_chips:
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

    def add_step(self, step: QuickStartStep | None = None) -> StepRow:
        row = StepRow(len(self._step_rows) + 1, step)
        row.changed.connect(self._update_status)
        row.removed.connect(self._remove_step_row)
        self.steps_layout.insertWidget(self.steps_layout.count() - 1, row)
        self._step_rows.append(row)
        self._update_status()
        if step is None:
            row.title_field.setFocus()
        return row

    def _remove_step_row(self, row: StepRow) -> None:
        if row in self._step_rows:
            self._step_rows.remove(row)
        self.steps_layout.removeWidget(row)
        discard(row)
        for number, remaining in enumerate(self._step_rows, start=1):
            remaining.set_number(number)
        self._update_status()

    @property
    def steps(self) -> list[QuickStartStep]:
        return [row.step() for row in self._step_rows]

    # ----- status / create ---------------------------------------------------------------

    def _on_name_changed(self, _text: str) -> None:
        self._update_status()

    def _on_add_step_clicked(self) -> None:
        self.add_step()

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
        titled = sum(1 for row in self._step_rows if row.step().title)
        if titled:
            parts.append(f"{titled} step{'s' if titled != 1 else ''}")
        self.status_pill.set_state(" \u00b7 ".join(parts), theme.GREEN)
        self.create_button.setEnabled(True)

    def _on_create_clicked(self) -> None:
        if not self.name_field.text().strip():
            self._update_status()
            return
        self.create_requested.emit(self.draft())
