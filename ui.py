import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QAction
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMenu, QPushButton, QScrollArea, QSizePolicy,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)

import db

# ── palette ──────────────────────────────────────────────────────────────────
C_BG         = "#16161e"
C_HEADER_BG  = "#1e1e2e"
C_ACTIVE_BG  = "#1a3050"
C_ACTIVE_BD  = "#3a7bd5"
C_HOVER_BG   = "#242435"
C_TEXT       = "#cdd6f4"
C_MUTED      = "#585b70"
C_ACCENT     = "#89b4fa"
C_DELETE     = "#f38ba8"
C_ADD        = "#a6e3a1"

ROW_H = 38


# ── helpers ──────────────────────────────────────────────────────────────────

def _fmt_seconds(s: float) -> str:
    s = max(0, int(s))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}"


def _make_icon(color: str, size: int = 22) -> QIcon:
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    m = 2
    p.drawEllipse(m, m, size - 2 * m, size - 2 * m)
    p.end()
    return QIcon(px)


# ── TopicRow ─────────────────────────────────────────────────────────────────

class TopicRow(QFrame):
    activated        = Signal(str)      # user clicked to select
    rename_committed = Signal(str, str) # (old_name, new_name)
    delete_requested = Signal(str)      # topic name

    def __init__(self, name: str, is_idle: bool, seconds: float = 0,
                 active: bool = False):
        super().__init__()
        self.topic_name = name
        self.is_idle    = is_idle
        self._active    = active
        self._edit_mode = False
        self._hover     = False

        self.setFixedHeight(ROW_H)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 8, 0)
        lay.setSpacing(6)

        self._label = QLabel(name)
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self._input = QLineEdit(name)
        self._input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._input.setStyleSheet(
            f"background: transparent; border: none; "
            f"color: {C_TEXT}; font-size: 13px; padding: 0;"
        )
        self._input.hide()
        self._input.editingFinished.connect(self._commit)

        self._time_lbl = QLabel(_fmt_seconds(seconds))
        self._time_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._time_lbl.setMinimumWidth(46)

        self._del_btn = QPushButton("×")
        self._del_btn.setFixedSize(20, 20)
        self._del_btn.hide()
        self._del_btn.setStyleSheet(
            f"QPushButton {{ background: {C_DELETE}; color: #1e1e2e; "
            f"border-radius: 10px; font-size: 14px; font-weight: bold; border: none; }}"
            f"QPushButton:hover {{ background: #ff9fb3; }}"
        )
        self._del_btn.clicked.connect(lambda: self.delete_requested.emit(self.topic_name))

        lay.addWidget(self._label)
        lay.addWidget(self._input)
        lay.addWidget(self._time_lbl)
        lay.addWidget(self._del_btn)

        self._refresh_style()

    # ── public API ──

    def set_seconds(self, s: float):
        self._time_lbl.setText(_fmt_seconds(s))

    def set_active(self, active: bool):
        self._active = active
        self._refresh_style()

    def set_edit_mode(self, edit: bool):
        self._edit_mode = edit
        if edit:
            self._label.hide()
            self._input.show()
            self._input.setText(self.topic_name)
            if not self.is_idle:
                self._del_btn.show()
            self.setCursor(Qt.ArrowCursor)
        else:
            self._input.hide()
            self._label.show()
            self._del_btn.hide()
            self.setCursor(Qt.PointingHandCursor)
        self._refresh_style()

    # ── internal ──

    def _commit(self):
        new = self._input.text().strip()
        if new and new != self.topic_name:
            self.rename_committed.emit(self.topic_name, new)
            self.topic_name = new
            self._label.setText(new)

    def _refresh_style(self):
        if self._active:
            bg, bd = C_ACTIVE_BG, C_ACTIVE_BD
            text_css = f"color: #ffffff; font-size: 13px; font-weight: bold;"
            time_css = f"color: {C_ACCENT}; font-size: 12px;"
        elif self._hover and not self._edit_mode:
            bg, bd = C_HOVER_BG, "#333355"
            text_css = f"color: {C_TEXT}; font-size: 13px;"
            time_css = f"color: {C_MUTED}; font-size: 12px;"
        else:
            bg, bd = "transparent", "transparent"
            text_css = f"color: {C_TEXT}; font-size: 13px;"
            time_css = f"color: {C_MUTED}; font-size: 12px;"

        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 1px solid {bd}; border-radius: 4px; }}"
        )
        self._label.setStyleSheet(text_css)
        self._time_lbl.setStyleSheet(time_css)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._edit_mode:
            self.activated.emit(self.topic_name)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self._hover = True
        self._refresh_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._refresh_style()
        super().leaveEvent(event)


# ── AddTopicRow ───────────────────────────────────────────────────────────────

class AddTopicRow(QFrame):
    topic_added = Signal(str)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(ROW_H)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 8, 0)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Add topic…")
        self._input.setStyleSheet(
            f"background: transparent; border: none; "
            f"color: {C_ADD}; font-size: 13px; padding: 0;"
        )
        self._input.returnPressed.connect(self._commit)
        lay.addWidget(self._input)

        self.setStyleSheet(
            f"QFrame {{ background: transparent; "
            f"border: 1px dashed {C_MUTED}; border-radius: 4px; }}"
        )

    def clear(self):
        self._input.clear()

    def _commit(self):
        name = self._input.text().strip()
        if name:
            self.topic_added.emit(name)
            self._input.clear()


# ── MainWindow ────────────────────────────────────────────────────────────────

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._edit_mode    = False
        self._active       = db.get_idle_name()
        self._active_since = time.time()
        self._base_totals: dict[str, float] = {}
        self._rows: list[TopicRow] = []

        self._build_ui()
        self._build_tray()
        self._load_topics()

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(1000)

        self._hb_timer = QTimer(self)
        self._hb_timer.timeout.connect(db.update_heartbeat)
        self._hb_timer.start(30_000)
        db.update_heartbeat()

    # ── UI construction ──

    def _build_ui(self):
        self.setWindowTitle("Stopwatch")
        self.setMinimumWidth(240)
        self.resize(260, 320)
        self.setStyleSheet(f"QWidget {{ background: {C_BG}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # header
        header = QFrame()
        header.setFixedHeight(36)
        header.setStyleSheet(
            f"QFrame {{ background: {C_HEADER_BG}; border-bottom: 1px solid #2a2a3e; }}"
        )
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(10, 0, 6, 0)

        title = QLabel("Stopwatch")
        title.setStyleSheet(
            f"color: {C_TEXT}; font-size: 13px; font-weight: bold; "
            f"background: transparent; border: none;"
        )

        self._edit_btn = QPushButton("✏")
        self._edit_btn.setFixedSize(26, 26)
        self._edit_btn.setCheckable(True)
        self._edit_btn.setToolTip("Edit topics")
        self._edit_btn.clicked.connect(self._toggle_edit)
        self._style_header_btn(self._edit_btn)

        menu_btn = QPushButton("⋮")
        menu_btn.setFixedSize(26, 26)
        menu_btn.setToolTip("Menu")
        self._style_header_btn(menu_btn)
        menu_btn.clicked.connect(self._show_menu)

        h_lay.addWidget(title)
        h_lay.addStretch()
        h_lay.addWidget(self._edit_btn)
        h_lay.addWidget(menu_btn)
        root.addWidget(header)

        # scrollable topic list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet(f"background: {C_BG};")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(6, 6, 6, 6)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()   # sentinel at index 0; rows go before it

        self._add_row = AddTopicRow()
        self._add_row.hide()
        self._add_row.topic_added.connect(self._on_topic_added)

        scroll.setWidget(self._list_widget)
        root.addWidget(scroll)

    def _style_header_btn(self, btn: QPushButton):
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_MUTED}; "
            f"border: none; border-radius: 4px; font-size: 15px; }}"
            f"QPushButton:hover {{ background: {C_HOVER_BG}; color: {C_TEXT}; }}"
            f"QPushButton:checked {{ background: {C_ACTIVE_BG}; color: {C_ACCENT}; }}"
        )

    def _build_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_make_icon(C_ACCENT))
        self._tray.setToolTip("Stopwatch")

        menu = QMenu()
        show_act = QAction("Show", self)
        show_act.triggered.connect(self._show_window)
        quit_act = QAction("Quit", self)
        quit_act.triggered.connect(self._quit)
        menu.addAction(show_act)
        menu.addSeparator()
        menu.addAction(quit_act)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    # ── topic list management ──

    def _load_topics(self):
        """
        Called once at startup. Always begins in Idle: if the DB's last event
        is not Idle (e.g. after an unrecovered crash with a fresh heartbeat),
        a transition to Idle is logged before computing today's totals.
        """
        idle = db.get_idle_name()
        last_active = db.get_active_topic()
        if last_active and last_active != idle:
            db.log_transition(idle)

        self._base_totals = db.get_today_totals()
        self._active       = idle
        self._active_since = time.time()

        for name, is_idle in db.get_topics():
            self._add_row_widget(name, bool(is_idle))

        # add_row sits just before the stretch sentinel
        stretch_idx = self._list_layout.count() - 1
        self._list_layout.insertWidget(stretch_idx, self._add_row)

        self._refresh_active_highlight()

    def _add_row_widget(self, name: str, is_idle: bool):
        """Insert a new TopicRow into the list, just before add_row / stretch."""
        seconds = self._base_totals.get(name, 0)
        active  = (name == self._active)
        row = TopicRow(name, is_idle, seconds, active)
        row.activated.connect(self._on_activated)
        row.rename_committed.connect(self._on_renamed)
        row.delete_requested.connect(self._on_delete)
        row.set_edit_mode(self._edit_mode)

        # self._rows tracks widgets in display order; add_row follows them
        insert_idx = len(self._rows)
        self._list_layout.insertWidget(insert_idx, row)
        self._rows.append(row)

    def _refresh_active_highlight(self):
        for row in self._rows:
            row.set_active(row.topic_name == self._active)

    # ── slot handlers ──

    def _on_activated(self, name: str):
        if name == self._active:
            return
        now = time.time()
        self._base_totals[self._active] = (
            self._base_totals.get(self._active, 0) + (now - self._active_since)
        )
        self._active       = name
        self._active_since = now
        db.log_transition(name)
        self._refresh_active_highlight()

    def _on_renamed(self, old: str, new: str):
        db.rename_topic(old, new)
        if self._active == old:
            self._active = new
        if old in self._base_totals:
            self._base_totals[new] = self._base_totals.pop(old)

    def _on_delete(self, name: str):
        if name == self._active:
            self._on_activated(db.get_idle_name())
        db.delete_topic(name)
        self._base_totals.pop(name, None)
        for i, row in enumerate(self._rows):
            if row.topic_name == name:
                self._list_layout.removeWidget(row)
                row.deleteLater()
                self._rows.pop(i)
                break

    def _on_topic_added(self, name: str):
        db.add_topic(name)
        self._add_row_widget(name, False)

    def _toggle_edit(self, checked: bool):
        self._edit_mode = checked
        for row in self._rows:
            row.set_edit_mode(checked)
        if checked:
            self._add_row.show()
        else:
            self._add_row.hide()
            self._add_row.clear()

    def _show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {C_HEADER_BG}; color: {C_TEXT}; "
            f"border: 1px solid #2a2a3e; border-radius: 4px; padding: 4px; }}"
            f"QMenu::item {{ padding: 4px 16px; }}"
            f"QMenu::item:selected {{ background: {C_ACTIVE_BG}; border-radius: 3px; }}"
        )
        top_act = QAction("Stay on top", self)
        top_act.setCheckable(True)
        top_act.setChecked(bool(self.windowFlags() & Qt.WindowStaysOnTopHint))
        top_act.triggered.connect(self._toggle_stay_on_top)

        quit_act = QAction("Quit", self)
        quit_act.triggered.connect(self._quit)

        menu.addAction(top_act)
        menu.addSeparator()
        menu.addAction(quit_act)
        menu.exec(self.mapToGlobal(self.rect().topRight()))

    # ── timers ──

    def _tick(self):
        elapsed = time.time() - self._active_since
        total   = self._base_totals.get(self._active, 0) + elapsed
        for row in self._rows:
            if row.topic_name == self._active:
                row.set_seconds(total)
                break

    # ── window / tray helpers ──

    def _toggle_stay_on_top(self, checked: bool):
        flags = self.windowFlags()
        if checked:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        self.show()

    def _show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self._show_window()

    def _quit(self):
        idle = db.get_idle_name()
        if self._active != idle:
            db.log_transition(idle)
        QApplication.quit()

    def closeEvent(self, event):
        """Hide to tray on window close; actual quit goes through _quit()."""
        if hasattr(self, '_tray'):
            event.ignore()
            self.hide()
        else:
            self._quit()
            event.accept()
