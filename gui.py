"""
gui.py – The DMod settings panel and hotkey-capture dialog.
Kept separate from dmod.py so the core app logic stays uncluttered,
mirroring the existing veil.py split.
"""

import winutils
from PyQt5.QtWidgets import (
    QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QSlider, QSpinBox, QColorDialog
)
from PyQt5.QtCore import Qt, pyqtSignal
from pynput import keyboard

from veil import VEIL_LABELS
from shapes import SELECTION_SHAPE_LABELS


STYLE_SHEET = """
QWidget {
    background-color: #1b1d23;
    color: #e7e9ee;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #32353e;
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #9aa0ad;
}
QPushButton {
    background-color: #2a2d36;
    border: 1px solid #3a3e4a;
    border-radius: 5px;
    padding: 5px 12px;
}
QPushButton:hover {
    background-color: #323641;
    border-color: #4d8df0;
}
QPushButton:pressed {
    background-color: #232630;
}
QComboBox, QSpinBox {
    background-color: #232630;
    border: 1px solid #3a3e4a;
    border-radius: 5px;
    padding: 3px 6px;
}
QLabel#hotkeyValue {
    color: #7fd1ff;
    font-weight: 600;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #32353e;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #4d8df0;
    width: 14px;
    margin: -6px 0;
    border-radius: 7px;
}
"""


# ── Hotkey capture dialog ───────────────────────────────────────────────────

class HotkeyCaptureDialog(QDialog):
    """
    Modal dialog that records a key combination by running a temporary
    pynput listener (separate from the app's main global listener) and
    returns it as a pynput hotkey string, e.g. '<ctrl>+<shift>+f3'.
    """

    _modifiers_updated = pyqtSignal(str)
    _combo_finished = pyqtSignal(str)
    _cancelled = pyqtSignal()

    _MODIFIER_TOKENS = {
        keyboard.Key.ctrl_l: "<ctrl>",  keyboard.Key.ctrl_r: "<ctrl>",
        keyboard.Key.alt_l: "<alt>",    keyboard.Key.alt_r: "<alt>",
        keyboard.Key.shift_l: "<shift>", keyboard.Key.shift_r: "<shift>",
        keyboard.Key.cmd_l: "<cmd>",    keyboard.Key.cmd_r: "<cmd>",
    }

    def __init__(self, parent=None, current=""):
        super().__init__(parent)
        self.setWindowTitle("Set Hotkey")
        self.setFixedSize(360, 150)
        self.setModal(True)

        self.result_hotkey = None
        self._held_modifiers = []
        self._listener = None

        self._modifiers_updated.connect(self._on_modifiers_updated)
        self._combo_finished.connect(self._on_combo_finished)
        self._cancelled.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        prompt = QLabel("Press the desired key combination…\n(Esc to cancel)")
        prompt.setAlignment(Qt.AlignCenter)
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        self.preview = QLabel(current or " ")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("font-size: 18px; font-weight: 600; color: #7fd1ff;")
        layout.addWidget(self.preview)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def showEvent(self, event):
        super().showEvent(event)
        self._start_listener()

    def reject(self):
        self._stop_listener()
        super().reject()

    def _start_listener(self):
        self._held_modifiers = []

        def on_press(key):
            if key == keyboard.Key.esc:
                self._cancelled.emit()
                return
            if key in self._MODIFIER_TOKENS:
                token = self._MODIFIER_TOKENS[key]
                if token not in self._held_modifiers:
                    self._held_modifiers.append(token)
                    self._modifiers_updated.emit(" + ".join(self._held_modifiers))
            else:
                token = self._key_to_token(key)
                if token:
                    combo = "+".join(self._held_modifiers + [token])
                    self._combo_finished.emit(combo)

        # Separate listener instance from the app's global one – the
        # caller is responsible for pausing the global listener so the
        # combo being typed doesn't also fire an existing hotkey.
        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.start()

    def _stop_listener(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _key_to_token(self, key):
        try:
            if hasattr(key, "char") and key.char is not None:
                return key.char.lower()
            name = str(key).replace("Key.", "")
            return f"<{name}>"
        except Exception:
            return None

    def _on_modifiers_updated(self, text):
        self.preview.setText(text)

    def _on_combo_finished(self, combo):
        self._stop_listener()
        self.result_hotkey = combo
        self.preview.setText(combo)
        self.accept()


# ── Settings window ─────────────────────────────────────────────────────────

class SettingsWindow(QWidget):
    """Sleek, lightweight settings panel covering every option in one place."""

    def __init__(self, overlay, hotkey_mgr):
        super().__init__()
        self.overlay = overlay
        self.hotkey_mgr = hotkey_mgr

        self.setWindowTitle("DMod — Settings")
        self.setFixedWidth(420)
        self.setStyleSheet(STYLE_SHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(18)
        root.addWidget(self._build_hotkeys_group())
        root.addWidget(self._build_selection_group())
        root.addWidget(self._build_veil_group())
        root.addWidget(self._build_admin_group())
        root.addStretch()
        
    def _build_admin_group(self):
        box = QGroupBox("Admin Access")
        layout = QVBoxLayout(box)

        if winutils.is_admin():
            status = QLabel("Already running as Administrator — Always On Top works on any window.")
            status.setWordWrap(True)
            layout.addWidget(status)
        else:
            info = QLabel("Some windows (elevated games, admin tools) need this app running as "
                          "Administrator for Always On Top to affect them.")
            info.setWordWrap(True)
            layout.addWidget(info)
            btn = QPushButton("Restart as Administrator")
            btn.clicked.connect(self._on_relaunch_admin)
            layout.addWidget(btn)

        return box

    def _on_relaunch_admin(self):
        winutils.relaunch_as_admin()
        QApplication.instance().quit()

    # ---- Hotkeys group ------------------------------------------------------

    def _build_hotkeys_group(self):
        box = QGroupBox("Hotkeys")
        grid = QGridLayout(box)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        self.main_hotkey_label = QLabel(self.hotkey_mgr.primary_str)
        self.pause_hotkey_label = QLabel(self.hotkey_mgr.secondary_str)
        self.cursorlock_hotkey_label = QLabel(self.hotkey_mgr.cursorlock_str)
        self.aot_hotkey_label = QLabel(self.hotkey_mgr.aot_str)

        rows = [
            ("DMod", self.main_hotkey_label, self.hotkey_mgr.set_primary_hotkey),
            ("Pause / Unpause", self.pause_hotkey_label, self.hotkey_mgr.set_secondary_hotkey),
            ("Cursor Lock", self.cursorlock_hotkey_label, self.hotkey_mgr.set_cursorlock_hotkey),
            ("Always On Top", self.aot_hotkey_label, self.hotkey_mgr.set_aot_hotkey),
        ]
        for i, (name, value_label, setter) in enumerate(rows):
            value_label.setObjectName("hotkeyValue")
            grid.addWidget(QLabel(name), i, 0)
            grid.addWidget(value_label, i, 1)
            btn = QPushButton("Set…")
            btn.clicked.connect(lambda _, lbl=value_label, fn=setter: self._capture_and_apply(lbl, fn))
            grid.addWidget(btn, i, 2)

        return box

    def _capture_and_apply(self, label, setter):
        # Pause the global listener so the combo being recorded doesn't
        # also trigger an existing hotkey while it's being typed.
        self.hotkey_mgr.pause()
        dlg = HotkeyCaptureDialog(self, current=label.text())
        if dlg.exec_() == QDialog.Accepted and dlg.result_hotkey:
            setter(dlg.result_hotkey)   # internally restarts the listener
            label.setText(dlg.result_hotkey)
        else:
            self.hotkey_mgr.resume()

    # ---- Selection group ----------------------------------------------------

    def _build_selection_group(self):
        box = QGroupBox("Selection Tool")
        layout = QVBoxLayout(box)
        layout.setSpacing(12)

        row = QHBoxLayout()
        row.addWidget(QLabel("Shape"))
        self.shape_combo = QComboBox()
        for key, label in SELECTION_SHAPE_LABELS:
            self.shape_combo.addItem(label, userData=key)
        idx = self.shape_combo.findData(self.overlay.selection_shape)
        if idx >= 0:
            self.shape_combo.setCurrentIndex(idx)
        self.shape_combo.currentIndexChanged.connect(self._on_selection_shape_changed)
        row.addWidget(self.shape_combo, 1)
        layout.addLayout(row)

        hint = QLabel("Drag to draw the selected shape. Release the hotkey when finished.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9aa0ad; font-size: 12px;")
        layout.addWidget(hint)

        return box

    def _on_selection_shape_changed(self, index):
        shape = self.shape_combo.itemData(index)
        self.overlay.set_selection_shape(shape)

    # ---- Veil group -----------------------------------------------------------

    def _build_veil_group(self):
        box = QGroupBox("Veil")
        layout = QVBoxLayout(box)
        layout.setSpacing(12)

        # Veil type
        row = QHBoxLayout()
        row.addWidget(QLabel("Type"))
        self.veil_combo = QComboBox()
        for key, label in VEIL_LABELS:
            self.veil_combo.addItem(label, userData=key)
        idx = self.veil_combo.findData(self.overlay.veil_type)
        if idx >= 0:
            self.veil_combo.setCurrentIndex(idx)
        self.veil_combo.currentIndexChanged.connect(self._on_veil_type_changed)
        row.addWidget(self.veil_combo, 1)
        layout.addLayout(row)

        # Color swatch (used by Flat Color)
        row = QHBoxLayout()
        row.addWidget(QLabel("Color"))
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(60, 24)
        self._update_color_swatch()
        self.color_btn.clicked.connect(self._on_pick_color)
        row.addWidget(self.color_btn)
        row.addStretch()
        layout.addLayout(row)

        # Opacity
        row = QHBoxLayout()
        row.addWidget(QLabel("Opacity"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(int(self.overlay.target_opacity * 100))
        self.opacity_value_label = QLabel(f"{int(self.overlay.target_opacity * 100)}%")
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        row.addWidget(self.opacity_slider, 1)
        row.addWidget(self.opacity_value_label)
        layout.addLayout(row)

        # Fade delay
        row = QHBoxLayout()
        row.addWidget(QLabel("Fade In Delay (ms)"))
        self.fade_spin = QSpinBox()
        self.fade_spin.setRange(0, 10000)
        self.fade_spin.setSingleStep(100)
        self.fade_spin.setValue(self.overlay.fade_duration)
        self.fade_spin.valueChanged.connect(self._on_fade_changed)
        row.addWidget(self.fade_spin)
        layout.addLayout(row)

        # Pause fade delay
        row = QHBoxLayout()
        row.addWidget(QLabel("Pause Fade Delay (ms)"))
        self.pause_fade_spin = QSpinBox()
        self.pause_fade_spin.setRange(0, 10000)
        self.pause_fade_spin.setSingleStep(100)
        self.pause_fade_spin.setValue(self.overlay.fade_duration_pause)
        self.pause_fade_spin.valueChanged.connect(self._on_pause_fade_changed)
        row.addWidget(self.pause_fade_spin)
        layout.addLayout(row)

        return box

    def _on_veil_type_changed(self, index):
        key = self.veil_combo.itemData(index)
        self.overlay.set_veil_type(key)

    def _update_color_swatch(self):
        self.color_btn.setStyleSheet(
            f"background-color: {self.overlay.veil_color.name()}; "
            f"border: 1px solid #444; border-radius: 4px;"
        )

    def _on_pick_color(self):
        color = QColorDialog.getColor(self.overlay.veil_color, self, "Veil Color")
        if color.isValid():
            self.overlay.veil_color = color
            self.overlay.settings.setValue("color", color.name())
            self._update_color_swatch()

    def _on_opacity_changed(self, value):
        self.opacity_value_label.setText(f"{value}%")
        self.overlay.target_opacity = value / 100.0
        self.overlay.settings.setValue("opacity", self.overlay.target_opacity)

    def _on_fade_changed(self, value):
        self.overlay.fade_duration = value
        self.overlay.settings.setValue("delay", value)

    def _on_pause_fade_changed(self, value):
        self.overlay.fade_duration_pause = value
        self.overlay.settings.setValue("delay_pause", value)

    # ---- Window behavior ------------------------------------------------------

    def closeEvent(self, event):
        # Hide rather than destroy so re-opening from the tray is instant
        # and doesn't rebuild the whole panel.
        event.ignore()
        self.hide()
