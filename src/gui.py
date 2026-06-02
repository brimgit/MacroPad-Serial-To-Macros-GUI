import json
import os
import sys

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QPushButton, QFrame, QComboBox, QDialog, QGridLayout, QSlider,
    QSizePolicy, QInputDialog, QMessageBox,
    QFileDialog, QCheckBox, QListWidget, QListWidgetItem, QScrollArea,
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QFont

import theme
from widgets import (
    StatusBadge, NavButton, KeyCard, MacroAssignDialog, EncoderCard, ToggleSwitch
)
from utils import get_data_path
import macro_manager
import profile_manager
from auto_profile import ForegroundWatcher


# ── Thread-safe bridge from serial thread → main thread ──────────────────────

class _Bridge(QObject):
    data_received = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)


# ── Volume worker ─────────────────────────────────────────────────────────────

class VolumeThread(QThread):
    done = pyqtSignal(int, int)  # encoder_id, percentage

    def __init__(self, volume_manager, app_name, delta, encoder_id, parent=None):
        super().__init__(parent)
        self._vm = volume_manager
        self._app = app_name
        self._delta = delta
        self._enc_id = encoder_id

    def run(self):
        found = False
        pct = 50
        steps = abs(self._delta)
        increase = self._delta > 0
        for _ in range(steps):
            result = self._vm.adjust_volume(self._app, increase=increase)
            if result is not None:
                pct = result
                found = True
        self.done.emit(self._enc_id, pct if found else -1)


# ── Pages ─────────────────────────────────────────────────────────────────────

class MacrosPage(QWidget):
    macros_changed = pyqtSignal()

    KEY_LAYOUT = [
        ['1', '2', '3', '4'],
        ['5', '6', '7', '8'],
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(24)

        header = QHBoxLayout()
        title = QLabel('Macros')
        title.setStyleSheet('font-size: 20px; font-weight: 700; letter-spacing: -0.3px;')
        hint = QLabel('Click a key to assign macros')
        hint.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_DIM};')
        self._hint_lbl = hint
        header.addWidget(title)
        header.addSpacing(14)
        header.addWidget(hint)
        header.addStretch()
        root.addLayout(header)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        self._line = line
        root.addWidget(line)

        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setContentsMargins(0, 8, 0, 0)
        for col in range(4):
            grid.setColumnStretch(col, 1)
        for row in range(2):
            grid.setRowStretch(row, 1)

        for row, keys in enumerate(self.KEY_LAYOUT):
            for col, key_id in enumerate(keys):
                card = KeyCard(key_id)
                card.assign_clicked.connect(self._on_key_clicked)
                self._cards[key_id] = card
                grid.addWidget(card, row, col)

        root.addLayout(grid, 1)

    def _on_key_clicked(self, key_id):
        card = self._cards[key_id]
        dlg = MacroAssignDialog(key_id, card.press_data, card.hold_data, self)
        if dlg.exec_() == QDialog.Accepted:
            press, hold = dlg.get_results()
            card.set_macros(press, hold)
            self._persist(key_id, press, hold)

    def _persist(self, key_id, press_data, hold_data):
        for data, suffix in [(press_data, ''), (hold_data, ':HOLD')]:
            key = f'KP:{key_id}{suffix}'
            if data:
                macro_manager.set_macro(key, data['type'], data['action'])
            else:
                try:
                    macro_manager.delete_macro(key)
                except KeyError:
                    pass
        macro_manager.save_macros()
        self.macros_changed.emit()

    def load_macros(self, macros_dict):
        for key_id, card in self._cards.items():
            press = macros_dict.get(f'KP:{key_id}')
            hold = macros_dict.get(f'KP:{key_id}:HOLD')
            card.set_macros(press, hold)

    def refresh_theme(self):
        self._hint_lbl.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_DIM};')
        self._line.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        for card in self._cards.values():
            card.refresh_theme()


class EncodersPage(QWidget):
    send_command = pyqtSignal(str)
    encoder_app_changed = pyqtSignal(int, str)
    settings_changed = pyqtSignal()

    # Encoder 0→A, 1→B, 2→C, 3→D (matches KP: key names from firmware)
    BTN_LABELS = ['A', 'B', 'C', 'D']

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = {}      # 0-indexed to match Arduino E:0..E:3
        self._volume_manager = None
        self._active_threads = []
        self._build_ui()

    def set_volume_manager(self, vm):
        self._volume_manager = vm

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(24)

        header = QHBoxLayout()
        title = QLabel('Encoders')
        title.setStyleSheet('font-size: 20px; font-weight: 700; letter-spacing: -0.3px;')
        hint = QLabel('LED color, mode, volume app, and button macro per encoder')
        hint.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_DIM};')
        self._hint_lbl = hint
        header.addWidget(title)
        header.addSpacing(14)
        header.addWidget(hint)
        header.addStretch()
        root.addLayout(header)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        self._line = line
        root.addWidget(line)

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        for i in range(4):
            card = EncoderCard(i)   # 0-indexed
            card.color_command.connect(self.send_command)
            card.color_command.connect(lambda _: self.settings_changed.emit())
            card.app_refresh_requested.connect(self._refresh_apps_for)
            card.button_macro_requested.connect(self._on_button_macro_requested)
            card.app_changed.connect(self.encoder_app_changed)
            card.app_changed.connect(lambda *_: self.settings_changed.emit())
            self._cards[i] = card
            grid.addWidget(card, i // 2, i % 2)

        root.addLayout(grid, 1)

    def refresh_theme(self):
        self._hint_lbl.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_DIM};')
        self._line.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        for card in self._cards.values():
            card.refresh_theme()

    def refresh_all_apps(self):
        self._load_apps(None)

    def _refresh_apps_for(self, encoder_id):
        self._load_apps(encoder_id)

    def _load_apps(self, target_id):
        if not self._volume_manager:
            return
        try:
            apps = self._volume_manager.get_available_processes()
            for enc_id, card in self._cards.items():
                if target_id is None or enc_id == target_id:
                    card.populate_apps(apps)
        except Exception:
            pass

    def _on_button_macro_requested(self, enc_id):
        card = self._cards.get(enc_id)
        if not card:
            return
        btn_label = self.BTN_LABELS[enc_id]
        dlg = MacroAssignDialog(
            f'Button {btn_label} (Enc {enc_id + 1})',
            card.get_button_macro_press(),
            card.get_button_macro_hold(),
            self
        )
        if dlg.exec_() == QDialog.Accepted:
            press, hold = dlg.get_results()
            card.set_button_macros(press, hold)
            self._save_button_macros(enc_id, press, hold)

    def _save_button_macros(self, enc_id, press_data, hold_data):
        btn_key = self.BTN_LABELS[enc_id]
        for data, suffix in [(press_data, ''), (hold_data, ':HOLD')]:
            key = f'KP:{btn_key}{suffix}'
            if data:
                macro_manager.set_macro(key, data['type'], data['action'])
            else:
                try:
                    macro_manager.delete_macro(key)
                except KeyError:
                    pass
        macro_manager.save_macros()
        self.settings_changed.emit()

    def load_button_macros(self, macros_dict):
        for enc_id, card in self._cards.items():
            btn_key = self.BTN_LABELS[enc_id]
            press = macros_dict.get(f'KP:{btn_key}')
            hold = macros_dict.get(f'KP:{btn_key}:HOLD')
            card.set_button_macros(press, hold)

    def get_encoder_app(self, encoder_id):
        card = self._cards.get(encoder_id)
        return card.get_selected_app() if card else ''

    def get_encoder_color_command(self, encoder_id):
        card = self._cards.get(encoder_id)
        return card.get_color_command() if card else None

    def get_encoder_mode(self, encoder_id):
        card = self._cards.get(encoder_id)
        return card.get_mode() if card else ''

    def get_all_states(self):
        return [self._cards[i].get_state() for i in range(4)]

    def restore_all_states(self, states):
        for i, state in enumerate(states):
            if i in self._cards:
                self._cards[i].restore_state(state)

    def update_volume_display(self, encoder_id, pct):
        card = self._cards.get(encoder_id)
        if card:
            card.set_percentage(pct)


class SettingsPage(QWidget):
    reconnect_requested = pyqtSignal(str, int)
    brightness_changed = pyqtSignal(int)
    encoder_led_timeout_changed = pyqtSignal(int)
    effect_speed_changed = pyqtSignal(int)   # ms
    export_requested = pyqtSignal()
    import_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(24)

        self._settings_title = QLabel('Settings')
        self._settings_title.setStyleSheet('font-size: 20px; font-weight: 700; letter-spacing: -0.3px;')
        root.addWidget(self._settings_title)

        self._settings_line = QFrame()
        self._settings_line.setFrameShape(QFrame.HLine)
        self._settings_line.setFixedHeight(1)
        self._settings_line.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        root.addWidget(self._settings_line)

        self._serial_card = QFrame()
        self._serial_card.setMaximumWidth(560)
        self._serial_card_apply_style()
        card_layout = QVBoxLayout(self._serial_card)
        card_layout.setContentsMargins(24, 20, 24, 24)
        card_layout.setSpacing(16)

        self._section_lbl = QLabel('SERIAL CONNECTION')
        self._section_lbl.setStyleSheet(f'font-size: 11px; font-weight: 600; color: {theme.TEXT_MUTED}; letter-spacing: 1px;')
        card_layout.addWidget(self._section_lbl)

        self._status = StatusBadge()
        card_layout.addWidget(self._status)

        port_row = QHBoxLayout()
        self._port_lbl = QLabel('Port')
        self._port_lbl.setStyleSheet(f'color: {theme.TEXT_MUTED}; min-width: 80px;')
        self._port_combo = QComboBox()
        self._port_refresh_btn = QPushButton('↻')
        self._port_refresh_btn.setFixedSize(34, 34)
        self._port_refresh_btn.setToolTip('Refresh ports')
        self._port_refresh_btn.setStyleSheet(self._small_btn_style())
        self._port_refresh_btn.clicked.connect(self._refresh_ports)
        port_row.addWidget(self._port_lbl)
        port_row.addWidget(self._port_combo, 1)
        port_row.addWidget(self._port_refresh_btn)
        card_layout.addLayout(port_row)

        baud_row = QHBoxLayout()
        self._baud_lbl = QLabel('Baud Rate')
        self._baud_lbl.setStyleSheet(f'color: {theme.TEXT_MUTED}; min-width: 80px;')
        self._baud_combo = QComboBox()
        self._baud_combo.addItems(['115200', '500000', '230400', '57600', '9600'])
        baud_row.addWidget(self._baud_lbl)
        baud_row.addWidget(self._baud_combo, 1)
        card_layout.addLayout(baud_row)

        self._connect_btn = QPushButton('Connect')
        self._connect_btn.setFixedWidth(130)
        self._connect_btn.setStyleSheet(self._connect_btn_style())
        self._connect_btn.clicked.connect(self._request_connect)
        card_layout.addWidget(self._connect_btn)

        root.addWidget(self._serial_card)

        # ── LED Brightness card ──────────────────────────────────────────────
        self._bright_card = QFrame()
        self._bright_card.setMaximumWidth(560)
        self._bright_card_apply_style()
        bright_layout = QVBoxLayout(self._bright_card)
        bright_layout.setContentsMargins(24, 20, 24, 24)
        bright_layout.setSpacing(14)

        self._bright_title = QLabel('LED BRIGHTNESS')
        self._bright_title.setStyleSheet(f'font-size: 11px; font-weight: 600; color: {theme.TEXT_MUTED}; letter-spacing: 1px;')
        bright_layout.addWidget(self._bright_title)

        slider_row = QHBoxLayout()
        self._bright_slider = QSlider(Qt.Horizontal)
        self._bright_slider.setRange(1, 100)
        self._bright_slider.setValue(10)
        self._bright_slider.setTickPosition(QSlider.NoTicks)

        self._bright_value_lbl = QLabel('10%')
        self._bright_value_lbl.setFixedWidth(40)
        self._bright_value_lbl.setStyleSheet(f'color: {theme.ACCENT}; font-weight: 600; font-size: 14px;')

        self._bright_debounce = QTimer(self)
        self._bright_debounce.setSingleShot(True)
        self._bright_debounce.timeout.connect(self._emit_brightness)
        self._bright_slider.valueChanged.connect(self._on_brightness_changed)

        slider_row.addWidget(self._bright_slider, 1)
        slider_row.addWidget(self._bright_value_lbl)
        bright_layout.addLayout(slider_row)

        enc_timeout_row = QHBoxLayout()
        self._enc_timeout_lbl = QLabel('Enc LED Off')
        self._enc_timeout_lbl.setStyleSheet(f'color: {theme.TEXT_MUTED}; min-width: 80px; font-size: 13px;')
        self._enc_timeout_combo = QComboBox()
        self._enc_timeout_combo.addItems(['2 seconds', '5 seconds', '10 seconds'])
        self._enc_timeout_combo.setCurrentText('2 seconds')
        self._enc_timeout_combo.currentIndexChanged.connect(self._on_encoder_led_timeout_changed)
        enc_timeout_row.addWidget(self._enc_timeout_lbl)
        enc_timeout_row.addWidget(self._enc_timeout_combo, 1)
        bright_layout.addLayout(enc_timeout_row)

        effect_speed_row = QHBoxLayout()
        self._effect_speed_lbl = QLabel('Effect Speed')
        self._effect_speed_lbl.setStyleSheet(f'color: {theme.TEXT_MUTED}; min-width: 80px; font-size: 13px;')
        self._effect_speed_combo = QComboBox()
        self._effect_speed_combo.addItems(['5 ms — Ultra', '10 ms — Smooth', '20 ms — Medium', '33 ms — Standard', '50 ms — Light'])
        self._effect_speed_combo.setCurrentText('10 ms — Smooth')
        self._effect_speed_combo.currentIndexChanged.connect(self._on_effect_speed_changed)
        effect_speed_row.addWidget(self._effect_speed_lbl)
        effect_speed_row.addWidget(self._effect_speed_combo, 1)
        bright_layout.addLayout(effect_speed_row)

        root.addWidget(self._bright_card)

        # ── Startup + Profile I/O card ───────────────────────────────────────
        self._misc_card = QFrame()
        self._misc_card.setMaximumWidth(560)
        self._misc_card_apply_style()
        misc_layout = QVBoxLayout(self._misc_card)
        misc_layout.setContentsMargins(24, 20, 24, 20)
        misc_layout.setSpacing(14)

        self._misc_title = QLabel('GENERAL')
        self._misc_title.setStyleSheet(f'font-size: 11px; font-weight: 600; color: {theme.TEXT_MUTED}; letter-spacing: 1px;')
        misc_layout.addWidget(self._misc_title)

        self._startup_cb = QCheckBox('Start with Windows')
        self._startup_cb.setChecked(self._read_startup_registry())
        self._startup_cb.stateChanged.connect(self._on_startup_changed)
        misc_layout.addWidget(self._startup_cb)

        io_row = QHBoxLayout()
        self._exp_btn = QPushButton('↓  Export Profile')
        self._exp_btn.setStyleSheet(self._io_btn_style())
        self._exp_btn.clicked.connect(self.export_requested)
        self._imp_btn = QPushButton('↑  Import Profile')
        self._imp_btn.setStyleSheet(self._io_btn_style())
        self._imp_btn.clicked.connect(self.import_requested)
        io_row.addWidget(self._exp_btn)
        io_row.addWidget(self._imp_btn)
        io_row.addStretch()
        misc_layout.addLayout(io_row)

        root.addWidget(self._misc_card)
        root.addStretch()

        self._refresh_ports()

    def _card_style(self):
        return f'''
            QFrame {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER};
                border-radius: 12px;
            }}
            QLabel {{ background: transparent; color: {theme.TEXT}; }}
            QComboBox {{ background-color: {theme.BG_ELEVATED}; }}
        '''

    def _serial_card_apply_style(self):
        self._serial_card.setStyleSheet(self._card_style())

    def _bright_card_apply_style(self):
        self._bright_card.setStyleSheet(f'''
            QFrame {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER};
                border-radius: 12px;
            }}
            QLabel {{ background: transparent; color: {theme.TEXT}; }}
            QSlider::groove:horizontal {{ background: {theme.BG_ELEVATED}; height: 6px; border-radius: 3px; }}
            QSlider::handle:horizontal {{ background: {theme.ACCENT}; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }}
            QSlider::sub-page:horizontal {{ background: {theme.ACCENT}; border-radius: 3px; }}
        ''')

    def _misc_card_apply_style(self):
        self._misc_card.setStyleSheet(f'''
            QFrame {{
                background-color: {theme.BG_CARD}; border: 1px solid {theme.BORDER};
                border-radius: 12px;
            }}
            QLabel {{ background: transparent; color: {theme.TEXT}; }}
        ''')

    def _small_btn_style(self):
        return (f'QPushButton {{ background: {theme.BG_ELEVATED}; border: 1px solid {theme.BORDER}; '
                f'border-radius: 8px; color: {theme.TEXT_MUTED}; font-size: 16px; padding: 0; }} '
                f'QPushButton:hover {{ border-color: {theme.ACCENT}; color: {theme.ACCENT}; }}')

    def _connect_btn_style(self):
        return (f'QPushButton {{ background: {theme.ACCENT}; color: #000; border: none; '
                f'border-radius: 8px; padding: 10px 20px; font-weight: 700; }} '
                f'QPushButton:hover {{ background: {theme.ACCENT_HOVER}; }}')

    def _io_btn_style(self):
        return (f'QPushButton {{ background: {theme.BG_ELEVATED}; border: 1px solid {theme.BORDER_LIGHT}; '
                f'border-radius: 8px; color: {theme.TEXT_MUTED}; padding: 7px 16px; font-size: 12px; }} '
                f'QPushButton:hover {{ border-color: {theme.ACCENT}; color: {theme.ACCENT}; }}')

    def _lbl_muted(self):
        return f'color: {theme.TEXT_MUTED}; min-width: 80px;'

    def _section_lbl_style(self):
        return f'font-size: 11px; font-weight: 600; color: {theme.TEXT_MUTED}; letter-spacing: 1px;'

    def refresh_theme(self):
        self._settings_line.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        self._serial_card_apply_style()
        self._bright_card_apply_style()
        self._misc_card_apply_style()
        self._section_lbl.setStyleSheet(self._section_lbl_style())
        self._port_lbl.setStyleSheet(self._lbl_muted())
        self._baud_lbl.setStyleSheet(self._lbl_muted())
        self._port_refresh_btn.setStyleSheet(self._small_btn_style())
        self._connect_btn.setStyleSheet(self._connect_btn_style())
        self._bright_title.setStyleSheet(self._section_lbl_style())
        self._bright_value_lbl.setStyleSheet(f'color: {theme.ACCENT}; font-weight: 600; font-size: 14px;')
        self._enc_timeout_lbl.setStyleSheet(f'color: {theme.TEXT_MUTED}; min-width: 80px; font-size: 13px;')
        self._effect_speed_lbl.setStyleSheet(f'color: {theme.TEXT_MUTED}; min-width: 80px; font-size: 13px;')
        self._misc_title.setStyleSheet(self._section_lbl_style())
        self._exp_btn.setStyleSheet(self._io_btn_style())
        self._imp_btn.setStyleSheet(self._io_btn_style())
        self._status.refresh_theme()

    def _refresh_ports(self):
        from serial_manager import list_ports
        self._port_combo.clear()
        self._port_combo.addItems(list_ports())

    def _request_connect(self):
        port = self._port_combo.currentText()
        try:
            baud = int(self._baud_combo.currentText())
        except ValueError:
            baud = 115200
        if port:
            self.reconnect_requested.emit(port, baud)

    _ENCODER_LED_TIMEOUT_SECONDS = {'2 seconds': 2, '5 seconds': 5, '10 seconds': 10}
    _EFFECT_SPEED_MS = {'5 ms — Ultra': 5, '10 ms — Smooth': 10, '20 ms — Medium': 20,
                        '33 ms — Standard': 33, '50 ms — Light': 50}

    def _on_brightness_changed(self, pct):
        self._bright_value_lbl.setText(f'{pct}%')
        self._bright_debounce.start(150)  # send only after 150 ms of no movement

    def _emit_brightness(self):
        pct = self._bright_slider.value()
        self.brightness_changed.emit(round(pct * 255 / 100))

    _REG_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
    _REG_NAME = 'MacroPad'

    def _read_startup_registry(self):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._REG_KEY)
            winreg.QueryValueEx(key, self._REG_NAME)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def _on_startup_changed(self, state):
        import winreg, os, sys
        enabled = bool(state)
        base = os.path.dirname(os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..')))
        vbs = os.path.join(base, 'Launch MacroPad.vbs')
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._REG_KEY,
                                 0, winreg.KEY_SET_VALUE)
            if enabled:
                winreg.SetValueEx(key, self._REG_NAME, 0, winreg.REG_SZ,
                                  f'wscript.exe "{vbs}"')
            else:
                try:
                    winreg.DeleteValue(key, self._REG_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass

    def _on_effect_speed_changed(self):
        ms = self._EFFECT_SPEED_MS.get(self._effect_speed_combo.currentText(), 10)
        self.effect_speed_changed.emit(ms)

    def get_effect_speed_ms(self):
        return self._EFFECT_SPEED_MS.get(self._effect_speed_combo.currentText(), 10)

    def set_effect_speed_ms(self, ms):
        reverse = {v: k for k, v in self._EFFECT_SPEED_MS.items()}
        label = reverse.get(ms, '10 ms — Smooth')
        self._effect_speed_combo.blockSignals(True)
        self._effect_speed_combo.setCurrentText(label)
        self._effect_speed_combo.blockSignals(False)

    def _on_encoder_led_timeout_changed(self):
        secs = self._ENCODER_LED_TIMEOUT_SECONDS.get(self._enc_timeout_combo.currentText(), 2)
        self.encoder_led_timeout_changed.emit(secs)

    def get_encoder_led_timeout_seconds(self):
        return self._ENCODER_LED_TIMEOUT_SECONDS.get(self._enc_timeout_combo.currentText(), 2)

    def set_encoder_led_timeout_seconds(self, secs):
        reverse = {v: k for k, v in self._ENCODER_LED_TIMEOUT_SECONDS.items()}
        label = reverse.get(secs, '2 seconds')
        self._enc_timeout_combo.blockSignals(True)
        self._enc_timeout_combo.setCurrentText(label)
        self._enc_timeout_combo.blockSignals(False)

    def get_brightness_255(self):
        return round(self._bright_slider.value() * 255 / 100)

    def set_brightness_pct(self, pct):
        self._bright_slider.blockSignals(True)
        self._bright_slider.setValue(max(1, min(100, pct)))
        self._bright_value_lbl.setText(f'{pct}%')
        self._bright_slider.blockSignals(False)

    def set_status(self, connected, port=''):
        self._status.set_connected(connected, port)
        self._connect_btn.setText('Reconnect' if connected else 'Connect')

    def prefill(self, port, baud_rate):
        idx = self._port_combo.findText(port)
        if idx >= 0:
            self._port_combo.setCurrentIndex(idx)
        idx = self._baud_combo.findText(str(baud_rate))
        if idx >= 0:
            self._baud_combo.setCurrentIndex(idx)


class TestModePage(QWidget):
    KEY_ORDER = ['1','2','3','4','5','6','7','8','A','B','C','D']
    KEY_LABELS = {**{str(i): f'Key {i}' for i in range(1,9)},
                  'A':'Enc 1 Btn','B':'Enc 2 Btn','C':'Enc 3 Btn','D':'Enc 4 Btn'}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = {}
        self._log_items = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(20)

        title = QLabel('Test Mode')
        title.setStyleSheet('font-size: 20px; font-weight: 700; letter-spacing: -0.3px;')
        self._test_hint = QLabel('Press any key or encoder button — the active macro is shown below.')
        self._test_hint.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_DIM};')
        root.addWidget(title)
        root.addWidget(self._test_hint)

        self._test_line = QFrame()
        self._test_line.setFrameShape(QFrame.HLine)
        self._test_line.setFixedHeight(1)
        self._test_line.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        root.addWidget(self._test_line)

        grid = QGridLayout()
        grid.setSpacing(10)
        self._key_name_lbls = {}
        for idx, key in enumerate(self.KEY_ORDER):
            card = QFrame()
            card.setFixedHeight(64)
            card.setStyleSheet(self._card_style())
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 8, 10, 8)
            cl.setSpacing(3)
            lbl_key = QLabel(self.KEY_LABELS[key])
            lbl_key.setStyleSheet(f'font-size: 10px; font-weight: 700; color: {theme.TEXT_DIM};')
            lbl_macro = QLabel('—')
            lbl_macro.setStyleSheet(f'font-size: 11px; color: {theme.TEXT_MUTED};')
            lbl_macro.setWordWrap(True)
            cl.addWidget(lbl_key)
            cl.addWidget(lbl_macro)
            self._cards[key] = (card, lbl_macro)
            self._key_name_lbls[key] = lbl_key
            grid.addWidget(card, idx // 4, idx % 4)

        root.addLayout(grid)

        self._log_lbl = QLabel('RECENT EVENTS')
        self._log_lbl.setStyleSheet(f'font-size: 10px; font-weight: 600; color: {theme.TEXT_DIM}; letter-spacing: 1px; margin-top: 4px;')
        root.addWidget(self._log_lbl)

        self._log = QListWidget()
        self._log.setFixedHeight(160)
        self._log.setStyleSheet(self._log_style())
        root.addWidget(self._log)
        root.addStretch()

    def _card_style(self):
        return (f'QFrame {{ background: {theme.BG_CARD}; border: 1px solid {theme.BORDER}; '
                f'border-radius: 10px; }}')

    def _log_style(self):
        return (f'QListWidget {{ background: {theme.BG_CARD}; border: 1px solid {theme.BORDER}; '
                f'border-radius: 10px; color: {theme.TEXT}; font-size: 12px; padding: 6px; }}')

    def refresh_theme(self):
        self._test_hint.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_DIM};')
        self._test_line.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        self._log_lbl.setStyleSheet(
            f'font-size: 10px; font-weight: 600; color: {theme.TEXT_DIM}; letter-spacing: 1px; margin-top: 4px;')
        self._log.setStyleSheet(self._log_style())
        for key, (card, lbl_macro) in self._cards.items():
            card.setStyleSheet(self._card_style())
            self._key_name_lbls[key].setStyleSheet(
                f'font-size: 10px; font-weight: 700; color: {theme.TEXT_DIM};')
            lbl_macro.setStyleSheet(f'font-size: 11px; color: {theme.TEXT_MUTED};')

    def refresh_macros(self, macros_dict):
        for key, (card, lbl) in self._cards.items():
            m = macros_dict.get(f'KP:{key}')
            if m:
                text = f"{m['type']}: {m['action'][:24]}"
            else:
                text = '—'
            lbl.setText(text)
            lbl.setStyleSheet(f'font-size: 11px; color: {"" + theme.ACCENT if m else theme.TEXT_MUTED};')

    def flash_key(self, key):
        if key not in self._cards:
            return
        card, _ = self._cards[key]
        card.setStyleSheet(f'''
            QFrame {{
                background: {theme.ACCENT}22; border: 1px solid {theme.ACCENT};
                border-radius: 10px;
            }}
        ''')
        QTimer.singleShot(600, lambda c=card: c.setStyleSheet(f'''
            QFrame {{
                background: {theme.BG_CARD}; border: 1px solid {theme.BORDER};
                border-radius: 10px;
            }}
        '''))

    def log_event(self, key, macro_key, macros_dict):
        m = macros_dict.get(macro_key)
        label = self.KEY_LABELS.get(key, key)
        if m:
            text = f'{label}  →  {m["type"]}: {m["action"][:32]}'
        else:
            text = f'{label}  →  (no macro)'
        item = QListWidgetItem(text)
        item.setForeground(
            __import__('PyQt5.QtGui', fromlist=['QColor']).QColor(theme.ACCENT if m else theme.TEXT_DIM)
        )
        self._log.insertItem(0, item)
        if self._log.count() > 30:
            self._log.takeItem(self._log.count() - 1)


class UploadPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._uploader = None
        self._build_ui()

    def set_serial_manager(self, sm):
        if self._uploader:
            self._uploader.set_serial_manager(sm)

    def _build_ui(self):
        from arduino_uploader import ArduinoUploader

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(24)

        title = QLabel('Upload Firmware')
        title.setStyleSheet('font-size: 22px; font-weight: 700;')
        root.addWidget(title)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        root.addWidget(line)

        self._uploader = ArduinoUploader()
        root.addWidget(self._uploader)
        root.addStretch()


# ── Main window ───────────────────────────────────────────────────────────────

class MacroPadApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self._serial_manager = None
        self._bridge = _Bridge()
        self._bridge.data_received.connect(self._handle_data)
        self._enc_tick_queue = {}
        self._enc_timers = {}
        self._active_threads = []
        self._enc_percentages = {0: 50, 1: 50, 2: 50, 3: 50}
        self._enc_muted = {0: False, 1: False, 2: False, 3: False}
        self._mute_flash_timers = {}
        self._mute_flash_state = {}
        self._mute_stop_timers = {}
        self._profile_data = {}
        self._switching_profile = False
        self._profile_save_timer = QTimer(self)
        self._profile_save_timer.setSingleShot(True)
        self._profile_save_timer.setInterval(400)
        self._profile_save_timer.timeout.connect(self._save_current_profile)
        self._fg_watcher = ForegroundWatcher(self)
        self._fg_watcher.app_changed.connect(self._on_foreground_app_changed)
        self._fg_watcher.start()
        self._build_ui()
        self._load_on_startup()

    def _build_ui(self):
        self.setWindowTitle('MacroPad')
        self.setMinimumSize(960, 720)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())

        self._divider = QFrame()
        self._divider.setFrameShape(QFrame.VLine)
        self._divider.setFixedWidth(1)
        self._divider.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        root.addWidget(self._divider)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f'background: {theme.BG};')

        self._macros_page = MacrosPage()
        self._encoders_page = EncodersPage()
        self._settings_page = SettingsPage()
        self._upload_page = UploadPage()
        self._test_page = TestModePage()

        self._bridge.connection_changed.connect(self._on_connection_changed)
        self._encoders_page.send_command.connect(self._serial_send)
        self._encoders_page.encoder_app_changed.connect(self._on_encoder_app_changed)
        self._encoders_page.settings_changed.connect(self._queue_profile_save)
        self._macros_page.macros_changed.connect(self._queue_profile_save)
        self._settings_page.reconnect_requested.connect(self._do_connect)
        self._settings_page.brightness_changed.connect(self._on_brightness_slider)
        self._settings_page.encoder_led_timeout_changed.connect(self._on_encoder_led_timeout_changed)
        self._settings_page.effect_speed_changed.connect(self._on_effect_speed_changed)
        self._settings_page.export_requested.connect(self._export_profile)
        self._settings_page.import_requested.connect(self._import_profile)

        def _make_scroll(widget):
            scroll = QScrollArea()
            scroll.setWidget(widget)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')
            return scroll

        for page in (self._macros_page, self._encoders_page,
                     self._settings_page, self._upload_page, self._test_page):
            self._stack.addWidget(_make_scroll(page))

        root.addWidget(self._stack, 1)

    def _build_sidebar(self):
        self._sidebar_collapsed = False
        self._sidebar = QFrame()
        self._sidebar.setFixedWidth(216)
        self._sidebar.setStyleSheet(f'background-color: {theme.SIDEBAR_BG};')

        layout = QVBoxLayout(self._sidebar)
        layout.setContentsMargins(0, 0, 0, 20)
        layout.setSpacing(0)

        # Logo area
        self._logo_frame = QWidget()
        self._logo_frame.setFixedHeight(68)
        self._logo_frame.setStyleSheet(
            f'background: transparent; border-bottom: 1px solid {theme.BORDER};')
        logo_row = QHBoxLayout(self._logo_frame)
        logo_row.setContentsMargins(16, 0, 16, 0)
        logo_row.setSpacing(11)

        self._icon_box = QLabel('◈')
        self._icon_box.setFixedSize(32, 32)
        self._icon_box.setAlignment(Qt.AlignCenter)
        self._icon_box.setStyleSheet(f'''
            background: {theme.ACCENT}20; color: {theme.ACCENT};
            border: 1px solid {theme.ACCENT}40; border-radius: 8px;
            font-size: 16px;
        ''')

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        self._name_lbl = QLabel('MacroPad')
        self._name_lbl.setStyleSheet(
            f'font-size: 14px; font-weight: 700; color: {theme.TEXT}; letter-spacing: 0.3px;')
        self._sub_lbl = QLabel('Controller')
        self._sub_lbl.setStyleSheet(
            f'font-size: 10px; color: {theme.TEXT_DIM}; letter-spacing: 0.5px;')
        title_col.addWidget(self._name_lbl)
        title_col.addWidget(self._sub_lbl)

        self._collapse_btn = QPushButton('‹')
        self._collapse_btn.setFixedSize(24, 24)
        self._collapse_btn.setCursor(Qt.PointingHandCursor)
        self._collapse_btn.setToolTip('Collapse sidebar')
        self._collapse_btn.setStyleSheet(self._collapse_btn_style())
        self._collapse_btn.clicked.connect(self._toggle_sidebar)

        logo_row.addWidget(self._icon_box)
        logo_row.addLayout(title_col)
        logo_row.addStretch()
        logo_row.addWidget(self._collapse_btn)
        layout.addWidget(self._logo_frame)

        # ── Profile selector ─────────────────────────────────────────────────
        self._prof_frame = QWidget()
        self._prof_frame.setFixedHeight(56)
        self._prof_frame.setStyleSheet(
            f'background: transparent; border-bottom: 1px solid {theme.BORDER};')
        prof_outer = QVBoxLayout(self._prof_frame)
        prof_outer.setContentsMargins(14, 6, 14, 6)
        prof_outer.setSpacing(4)

        prof_lbl = QLabel('PROFILE')
        prof_lbl.setStyleSheet(
            f'font-size: 9px; font-weight: 600; color: {theme.TEXT_DIM}; letter-spacing: 1px;')
        prof_outer.addWidget(prof_lbl)

        prof_row = QHBoxLayout()
        prof_row.setSpacing(5)
        self._profile_combo = QComboBox()
        self._profile_combo.setFixedHeight(24)
        self._profile_combo.setStyleSheet(f'''
            QComboBox {{
                background: {theme.BG_ELEVATED}; border: 1px solid {theme.BORDER_LIGHT};
                border-radius: 6px; color: {theme.TEXT}; padding: 2px 22px 2px 8px;
                font-size: 12px;
            }}
            QComboBox:hover {{ border-color: {theme.ACCENT}; }}
            QComboBox QAbstractItemView {{
                background: {theme.BG_CARD}; border: 1px solid {theme.BORDER_LIGHT};
                color: {theme.TEXT}; selection-background-color: {theme.ACCENT};
                selection-color: #000;
            }}
        ''')

        _prof_btn_style = f'''
            QPushButton {{
                background: {theme.BG_ELEVATED}; border: 1px solid {theme.BORDER_LIGHT};
                border-radius: 6px; color: {theme.TEXT_MUTED}; font-size: 14px;
                padding: 0;
            }}
            QPushButton:hover {{ border-color: {theme.ACCENT}; color: {theme.ACCENT}; }}
        '''
        self._new_prof_btn = QPushButton('+')
        self._new_prof_btn.setFixedSize(24, 24)
        self._new_prof_btn.setToolTip('New profile')
        self._new_prof_btn.setStyleSheet(_prof_btn_style)
        self._new_prof_btn.clicked.connect(self._new_profile)

        self._del_prof_btn = QPushButton('×')
        self._del_prof_btn.setFixedSize(24, 24)
        self._del_prof_btn.setToolTip('Delete profile')
        self._del_prof_btn.setStyleSheet(_prof_btn_style)
        self._del_prof_btn.clicked.connect(self._delete_profile)

        self._trig_btn = QPushButton('⚡')
        self._trig_btn.setFixedSize(24, 24)
        self._trig_btn.setToolTip('Auto-switch trigger apps')
        self._trig_btn.setStyleSheet(_prof_btn_style)
        self._trig_btn.clicked.connect(self._edit_trigger_apps)

        prof_row.addWidget(self._profile_combo, 1)
        prof_row.addWidget(self._new_prof_btn)
        prof_row.addWidget(self._trig_btn)
        prof_row.addWidget(self._del_prof_btn)
        prof_outer.addLayout(prof_row)
        layout.addWidget(self._prof_frame)
        layout.addSpacing(6)

        self._nav_btns = []
        for icon, label, idx in [
            ('⌨', 'Macros',   0),
            ('⚙', 'Encoders', 1),
            ('◎', 'Settings', 2),
            ('⬆', 'Upload',   3),
            ('▶', 'Test',     4),
        ]:
            btn = NavButton(icon, label)
            btn.clicked.connect(lambda i=idx: self._navigate(i))
            self._nav_btns.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # ── Bottom: separator + status + dark/light toggle ───────────────────
        self._bottom_sep = QFrame()
        self._bottom_sep.setFrameShape(QFrame.HLine)
        self._bottom_sep.setFixedHeight(1)
        self._bottom_sep.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        layout.addWidget(self._bottom_sep)

        # Status row
        self._status_frame = QWidget()
        self._status_frame.setStyleSheet('background: transparent;')
        status_layout = QVBoxLayout(self._status_frame)
        status_layout.setContentsMargins(14, 8, 14, 4)
        status_layout.setSpacing(0)
        self._sidebar_status = StatusBadge()
        status_layout.addWidget(self._sidebar_status)
        layout.addWidget(self._status_frame)

        # Theme toggle row
        self._toggle_row = QWidget()
        self._toggle_row.setStyleSheet('background: transparent;')
        toggle_layout = QHBoxLayout(self._toggle_row)
        toggle_layout.setContentsMargins(14, 4, 14, 12)
        toggle_layout.setSpacing(8)

        self._mode_icon_lbl = QLabel('☀' if theme.get_mode() == 'light' else '🌙')
        self._mode_icon_lbl.setStyleSheet(f'font-size: 14px; color: {theme.TEXT_DIM};')
        self._mode_text_lbl = QLabel('Light mode' if theme.get_mode() == 'light' else 'Dark mode')
        self._mode_text_lbl.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_MUTED};')

        self._mode_toggle = ToggleSwitch()
        self._mode_toggle.setChecked(theme.get_mode() == 'light')
        self._mode_toggle.toggled.connect(lambda _: self._toggle_theme())

        toggle_layout.addWidget(self._mode_icon_lbl)
        toggle_layout.addWidget(self._mode_text_lbl, 1)
        toggle_layout.addWidget(self._mode_toggle)
        layout.addWidget(self._toggle_row)

        return self._sidebar

    def _collapse_btn_style(self):
        return (f'QPushButton {{ background: transparent; border: none; '
                f'color: {theme.TEXT_DIM}; font-size: 16px; font-weight: 700; padding: 0; }} '
                f'QPushButton:hover {{ color: {theme.TEXT_MUTED}; }}')

    def _toggle_sidebar(self):
        self._sidebar_collapsed = not self._sidebar_collapsed
        collapsed = self._sidebar_collapsed

        if collapsed:
            self._sidebar.setFixedWidth(56)
            self._collapse_btn.setText('›')
            self._collapse_btn.setToolTip('Expand sidebar')
        else:
            self._sidebar.setFixedWidth(216)
            self._collapse_btn.setText('‹')
            self._collapse_btn.setToolTip('Collapse sidebar')

        # Logo area
        self._name_lbl.setVisible(not collapsed)
        self._sub_lbl.setVisible(not collapsed)

        # Profile section
        self._prof_frame.setVisible(not collapsed)

        # Nav buttons
        for btn in self._nav_btns:
            btn.set_collapsed(collapsed)

        # Theme toggle row
        self._toggle_row.setVisible(not collapsed)

    def _theme_btn_style(self):
        return f'''
            QPushButton {{
                background: {theme.BG_ELEVATED}; border: 1px solid {theme.BORDER_LIGHT};
                border-radius: 8px; color: {theme.TEXT_MUTED}; font-size: 16px; padding: 0;
            }}
            QPushButton:hover {{ border-color: {theme.ACCENT}; color: {theme.ACCENT}; }}
        '''

    def _toggle_theme(self):
        from PyQt5.QtWidgets import QApplication
        new_mode = 'light' if theme.get_mode() == 'dark' else 'dark'
        theme.set_mode(new_mode)
        QApplication.instance().setStyleSheet(theme.build_stylesheet())
        self._refresh_all_theme()

    def _refresh_all_theme(self):
        # Sidebar background — unscoped so it applies directly to this widget
        border_right = f'; border-right: 1px solid {theme.BORDER}' if theme.get_mode() == 'light' else ''
        self._sidebar.setStyleSheet(f'background-color: {theme.SIDEBAR_BG}{border_right};')
        self._logo_frame.setStyleSheet(f'background: transparent; border-bottom: 1px solid {theme.BORDER};')
        self._icon_box.setStyleSheet(f'''
            background: {theme.ACCENT}20; color: {theme.ACCENT};
            border: 1px solid {theme.ACCENT}40; border-radius: 8px; font-size: 16px;
        ''')
        self._name_lbl.setStyleSheet(f'font-size: 14px; font-weight: 700; color: {theme.TEXT}; letter-spacing: 0.3px;')
        self._sub_lbl.setStyleSheet(f'font-size: 10px; color: {theme.TEXT_DIM}; letter-spacing: 0.5px;')
        self._prof_frame.setStyleSheet(f'background: transparent; border-bottom: 1px solid {theme.BORDER};')
        self._bottom_sep.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        self._status_frame.setStyleSheet('background: transparent;')
        self._divider.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        self._stack.setStyleSheet(f'background: {theme.BG};')

        # Profile combo
        self._profile_combo.setStyleSheet(f'''
            QComboBox {{
                background: {theme.BG_ELEVATED}; border: 1px solid {theme.BORDER_LIGHT};
                border-radius: 6px; color: {theme.TEXT}; padding: 2px 22px 2px 8px; font-size: 12px;
            }}
            QComboBox:hover {{ border-color: {theme.ACCENT}; }}
            QComboBox QAbstractItemView {{
                background: {theme.BG_CARD}; border: 1px solid {theme.BORDER_LIGHT};
                color: {theme.TEXT}; selection-background-color: {theme.ACCENT}; selection-color: #000;
            }}
        ''')

        _prof_btn_style = f'''
            QPushButton {{
                background: {theme.BG_ELEVATED}; border: 1px solid {theme.BORDER_LIGHT};
                border-radius: 6px; color: {theme.TEXT_MUTED}; font-size: 14px; padding: 0;
            }}
            QPushButton:hover {{ border-color: {theme.ACCENT}; color: {theme.ACCENT}; }}
        '''
        self._new_prof_btn.setStyleSheet(_prof_btn_style)
        self._del_prof_btn.setStyleSheet(_prof_btn_style)
        self._trig_btn.setStyleSheet(_prof_btn_style)

        # Theme toggle row
        is_light = theme.get_mode() == 'light'
        self._mode_icon_lbl.setText('☀' if is_light else '🌙')
        self._mode_icon_lbl.setStyleSheet(f'font-size: 14px; color: {theme.TEXT_DIM};')
        self._mode_text_lbl.setText('Light mode' if is_light else 'Dark mode')
        self._mode_text_lbl.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_MUTED};')
        self._mode_toggle.setChecked(is_light)
        self._mode_toggle.update()
        self._collapse_btn.setStyleSheet(self._collapse_btn_style())

        # Nav buttons and status
        for btn in self._nav_btns:
            btn.refresh_theme()
        self._sidebar_status.refresh_theme()

        # Pages
        self._macros_page.refresh_theme()
        self._encoders_page.refresh_theme()
        self._settings_page.refresh_theme()
        self._test_page.refresh_theme()

    def _navigate(self, idx):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.set_active(i == idx)
        if idx == 1:
            self._encoders_page.refresh_all_apps()
        if idx == 4:
            self._test_page.refresh_macros(macro_manager.macros)

    def _load_on_startup(self):
        # Load macros.json first so profile_manager can seed from it on first run
        existing = macro_manager.reload_macros()

        self._profile_data = profile_manager.load(existing)
        active = profile_manager.get_active(self._profile_data)

        # Restore macros from active profile
        macro_manager.macros.clear()
        macro_manager.macros.update(active.get('macros', existing))

        self._macros_page.load_macros(macro_manager.macros)
        self._encoders_page.load_button_macros(macro_manager.macros)

        # Restore encoder states from active profile
        enc_states = active.get('encoders', [{} for _ in range(4)])
        self._encoders_page.restore_all_states(enc_states)

        # Populate profile combo
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        self._profile_combo.addItems(profile_manager.get_names(self._profile_data))
        self._profile_combo.setCurrentText(profile_manager.get_active_name(self._profile_data))
        self._profile_combo.blockSignals(False)
        self._profile_combo.currentTextChanged.connect(self._on_profile_changed)

        settings = _load_settings()
        port            = settings[0] if settings else 'COM6'
        baud            = int(settings[1]) if settings else 115200
        brightness_pct  = int(settings[2]) if settings and settings[2] else 10
        enc_led_timeout = int(settings[3]) if settings and len(settings) > 3 and settings[3] is not None else 2
        effect_speed    = int(settings[4]) if settings and len(settings) > 4 and settings[4] is not None else 10

        self._settings_page.prefill(port, baud)
        self._settings_page.set_brightness_pct(brightness_pct)
        self._settings_page.set_encoder_led_timeout_seconds(enc_led_timeout)
        self._settings_page.set_effect_speed_ms(effect_speed)

        saved_mode = settings[5] if settings and len(settings) > 5 else 'dark'
        if saved_mode != theme.get_mode():
            theme.set_mode(saved_mode)
            from PyQt5.QtWidgets import QApplication
            QApplication.instance().setStyleSheet(theme.build_stylesheet())
            self._refresh_all_theme()

        self._do_connect(port, baud)
        self._navigate(0)

    def _do_connect(self, port, baud_rate):
        if self._serial_manager:
            self._serial_manager.stop()

        try:
            from serial_manager import SerialManager
            self._serial_manager = SerialManager(
                data_callback=self._bridge.data_received.emit,
                connected_callback=self._bridge.connection_changed.emit,
                port=port,
                baud_rate=baud_rate,
            )
            self._encoders_page.set_volume_manager(self._serial_manager.volume_manager)
            self._upload_page.set_serial_manager(self._serial_manager)
            self._sidebar_status.set_connected(True, port)
            self._settings_page.set_status(True, port)
            _save_settings(port, str(baud_rate), self._settings_page._bright_slider.value(),
                           self._settings_page.get_encoder_led_timeout_seconds(),
                           self._settings_page.get_effect_speed_ms(),
                           theme.get_mode())
            # Push brightness then LED state after Arduino has had time to boot
            QTimer.singleShot(2500, self._send_initial_brightness)
            QTimer.singleShot(2600, self._send_initial_led_state)
            QTimer.singleShot(3200, self._sync_mute_states)
        except Exception:
            self._sidebar_status.set_connected(False)
            self._settings_page.set_status(False)

    def _serial_send(self, cmd):
        if self._serial_manager:
            self._serial_manager.send_data(cmd + '\n')

    def _handle_data(self, data):
        data = data.strip()
        if not data:
            return

        parts = data.split(':')

        # Encoder rotation — E:N:+  or  E:N:-
        if parts[0] == 'E' and len(parts) == 3:
            try:
                enc_id = int(parts[1])
                self._queue_encoder_tick(enc_id, parts[2] == '+')
            except (ValueError, IndexError):
                pass
            return

        # Key event — KP:KEY:DOWN  or  KP:KEY:UP:MS
        if parts[0] == 'KP' and len(parts) >= 3:
            key = parts[1]
            event = parts[2]
            if event == 'UP':
                try:
                    ms = int(parts[3]) if len(parts) >= 4 else 0
                except ValueError:
                    ms = 0
                macro_key = f'KP:{key}:HOLD' if ms >= 500 else f'KP:{key}'
                self._execute_macro_or_mute(key, macro_key)
                if self._stack.currentIndex() == 4:
                    self._test_page.flash_key(key)
                    self._test_page.log_event(key, macro_key, macro_manager.macros)
            return

        # Log anything else (Arduino error responses, debug output)
        import logging
        logging.debug(f'Arduino: {data}')

    def _execute_macro_or_mute(self, key, macro_key):
        if key in ('A', 'B', 'C', 'D'):
            enc_id = ord(key) - ord('A')
            mode = self._encoders_page.get_encoder_mode(enc_id)
            app_name = self._encoders_page.get_encoder_app(enc_id)
            macro = macro_manager.macros.get(macro_key)
            is_mute = (mode == 'default') or (macro and macro.get('type') == 'Mute App')
            if is_mute and app_name and self._serial_manager:
                new_muted = self._serial_manager.volume_manager.toggle_mute(app_name)
                self._enc_muted[enc_id] = bool(new_muted)
                self._update_mute_leds(enc_id)
                return

        macro_manager.execute_macro(macro_key)

    def _on_encoder_app_changed(self, enc_id, app_name):
        if not app_name or not self._serial_manager:
            self._enc_muted[enc_id] = False
            return
        try:
            is_muted = self._serial_manager.volume_manager.get_mute(app_name)
        except Exception:
            is_muted = False
        self._enc_muted[enc_id] = is_muted
        self._update_mute_leds(enc_id)

    def _sync_mute_states(self):
        if not self._serial_manager:
            return
        for enc_id in range(4):
            app_name = self._encoders_page.get_encoder_app(enc_id)
            if not app_name:
                self._enc_muted[enc_id] = False
                continue
            try:
                is_muted = self._serial_manager.volume_manager.get_mute(app_name)
            except Exception:
                is_muted = False
            self._enc_muted[enc_id] = is_muted
            if is_muted:
                self._update_mute_leds(enc_id)

    def _update_mute_leds(self, enc_id):
        # Stop any in-progress flash timers from rotation
        t = self._mute_flash_timers.get(enc_id)
        if t:
            t.stop()
        t = self._mute_stop_timers.get(enc_id)
        if t:
            t.stop()

        n = enc_id + 1
        if self._enc_muted[enc_id]:
            self._serial_send(f'{n}:color(200,0,0)')
            self._serial_send(f'{n}:100')
        else:
            color_cmd = self._encoders_page.get_encoder_color_command(enc_id)
            if color_cmd:
                self._serial_send(color_cmd)
            pct = self._enc_percentages.get(enc_id, 50)
            self._serial_send(f'{n}:{pct}')

    def _queue_encoder_tick(self, enc_id, increase):
        delta = self._enc_tick_queue.get(enc_id, 0)
        self._enc_tick_queue[enc_id] = delta + (1 if increase else -1)

        if enc_id in self._enc_timers:
            self._enc_timers[enc_id].stop()

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._flush_encoder(enc_id))
        timer.start(40)
        self._enc_timers[enc_id] = timer

    def _flush_encoder(self, enc_id):
        delta = self._enc_tick_queue.pop(enc_id, 0)
        if delta == 0 or not self._serial_manager:
            return

        app_name = self._encoders_page.get_encoder_app(enc_id)

        if app_name:
            # Volume app assigned — adjust real volume, LED follows actual level
            thread = VolumeThread(
                self._serial_manager.volume_manager, app_name, delta, enc_id
            )
            thread.done.connect(self._on_volume_done)
            thread.finished.connect(
                lambda t=thread: self._active_threads.remove(t)
                if t in self._active_threads else None
            )
            self._active_threads.append(thread)
            thread.start()
        else:
            pass  # No app assigned — LED stays off, ignore the turn

    def _on_brightness_slider(self, value_255):
        self._serial_send(f'BRIGHT:{value_255}')
        self._persist_settings()

    def _persist_settings(self):
        _save_settings(
            self._settings_page._port_combo.currentText(),
            self._settings_page._baud_combo.currentText(),
            self._settings_page._bright_slider.value(),
            self._settings_page.get_encoder_led_timeout_seconds(),
            self._settings_page.get_effect_speed_ms(),
            theme.get_mode(),
        )

    def _flash_red(self, enc_id):
        n = enc_id + 1
        self._serial_send(f'{n}:color(200,0,0)')
        self._serial_send(f'{n}:80')

        def restore():
            color_cmd = self._encoders_page.get_encoder_color_command(enc_id)
            if color_cmd:
                self._serial_send(color_cmd)
            self._serial_send(f'{n}:0')
            self._enc_percentages[enc_id] = 0
            self._encoders_page.update_volume_display(enc_id, 0)

        QTimer.singleShot(500, restore)

    def _on_volume_done(self, enc_id, pct):
        if pct < 0:
            self._flash_red(enc_id)
            return
        self._enc_percentages[enc_id] = pct
        self._encoders_page.update_volume_display(enc_id, pct)
        if self._enc_muted.get(enc_id, False):
            self._start_mute_flash(enc_id)
        else:
            self._serial_send(f'{enc_id + 1}:{pct}')

    def _start_mute_flash(self, enc_id):
        # Reset the "stopped rotating" debounce
        stop_timer = self._mute_stop_timers.get(enc_id)
        if stop_timer is None:
            stop_timer = QTimer(self)
            stop_timer.setSingleShot(True)
            stop_timer.timeout.connect(lambda i=enc_id: self._on_mute_rotation_stopped(i))
            self._mute_stop_timers[enc_id] = stop_timer
        stop_timer.start(400)

        # Start the steady blink if not already running
        flash_timer = self._mute_flash_timers.get(enc_id)
        if flash_timer is None or not flash_timer.isActive():
            flash_timer = QTimer(self)
            flash_timer.timeout.connect(lambda i=enc_id: self._mute_flash_tick(i))
            self._mute_flash_timers[enc_id] = flash_timer
            self._mute_flash_state[enc_id] = True
            self._mute_flash_tick(enc_id)   # immediate first on
            flash_timer.start(200)

    def _mute_flash_tick(self, enc_id):
        if not self._enc_muted.get(enc_id, False):
            return
        n = enc_id + 1
        if self._mute_flash_state.get(enc_id, True):
            self._serial_send(f'{n}:color(200,0,0)')
            self._serial_send(f'{n}:100')
        else:
            self._serial_send(f'{n}:0')
        self._mute_flash_state[enc_id] = not self._mute_flash_state.get(enc_id, True)

    def _on_mute_rotation_stopped(self, enc_id):
        flash_timer = self._mute_flash_timers.get(enc_id)
        if flash_timer:
            flash_timer.stop()
        n = enc_id + 1
        def on():
            if not self._enc_muted.get(enc_id, False):
                return
            self._serial_send(f'{n}:color(200,0,0)')
            self._serial_send(f'{n}:100')
        def off():
            if not self._enc_muted.get(enc_id, False):
                return
            self._serial_send(f'{n}:0')
        on()
        QTimer.singleShot(200, off)
        QTimer.singleShot(400, on)
        QTimer.singleShot(600, off)
        QTimer.singleShot(800, on)

    def _send_initial_brightness(self):
        self._serial_send(f'BRIGHT:{self._settings_page.get_brightness_255()}')
        self._serial_send(f'ENC_TIMEOUT:{self._settings_page.get_encoder_led_timeout_seconds()}')
        self._serial_send(f'EFFECT_SPEED:{self._settings_page.get_effect_speed_ms()}')

    def _on_encoder_led_timeout_changed(self, secs):
        self._serial_send(f'ENC_TIMEOUT:{secs}')
        self._persist_settings()

    def _on_effect_speed_changed(self, ms):
        self._serial_send(f'EFFECT_SPEED:{ms}')
        self._persist_settings()

    def _send_initial_led_state(self):
        """Push color mode + percentage to every LED strip on connect.
        The color command must come first — the Arduino's lightUpPercentage
        uses stripsData[n].color which may be (0,0,0) from blank EEPROM.
        Commands are staggered via QTimer so the ESP32 has time to process each one.
        """
        import logging
        logging.info('Sending initial LED state to Arduino...')
        commands = []
        for enc_id in range(4):
            color_cmd = self._encoders_page.get_encoder_color_command(enc_id)
            app_name = self._encoders_page.get_encoder_app(enc_id)
            pct = self._enc_percentages.get(enc_id, 50) if app_name else 0
            if not app_name:
                self._enc_percentages[enc_id] = 0
            if color_cmd:
                commands.append(color_cmd)
            commands.append(f'{enc_id + 1}:{pct}')

        def send_next(idx=0):
            if idx >= len(commands):
                return
            self._serial_send(commands[idx])
            QTimer.singleShot(60, lambda: send_next(idx + 1))

        send_next()

    # ── Auto-reconnect ────────────────────────────────────────────────────────
    def _on_connection_changed(self, connected):
        port = self._settings_page._port_combo.currentText()
        self._sidebar_status.set_connected(connected, port if connected else '')
        self._settings_page.set_status(connected, port if connected else '')
        if connected:
            QTimer.singleShot(2500, self._send_initial_brightness)
            QTimer.singleShot(2600, self._send_initial_led_state)
            QTimer.singleShot(3200, self._sync_mute_states)

    # ── Export / Import profiles ──────────────────────────────────────────────
    def _export_profile(self):
        active_name = profile_manager.get_active_name(self._profile_data)
        self._save_current_profile()
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export Profile', f'{active_name}.json', 'JSON files (*.json)')
        if not path:
            return
        import json
        exported = profile_manager.export_profile(self._profile_data, active_name)
        with open(path, 'w') as f:
            json.dump(exported, f, indent=2)
        QMessageBox.information(self, 'Exported', f'Profile "{active_name}" saved.')

    def _import_profile(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Import Profile', '', 'JSON files (*.json)')
        if not path:
            return
        import json
        try:
            with open(path, 'r') as f:
                exported = json.load(f)
            name = profile_manager.import_profile(self._profile_data, exported)
            self._profile_combo.blockSignals(True)
            self._profile_combo.addItem(name)
            self._profile_combo.blockSignals(False)
            profile_manager.save(self._profile_data)
            QMessageBox.information(self, 'Imported', f'Profile "{name}" imported.')
        except Exception as e:
            QMessageBox.critical(self, 'Import failed', str(e))

    # ── Trigger apps ──────────────────────────────────────────────────────────
    def _edit_trigger_apps(self):
        active_name = profile_manager.get_active_name(self._profile_data)
        current = profile_manager.get_active(self._profile_data).get('trigger_apps', [])

        dlg = QDialog(self)
        dlg.setWindowTitle(f'Trigger Apps — {active_name}')
        dlg.setMinimumWidth(360)
        dlg.setStyleSheet(f'QDialog {{ background: {theme.BG}; }} QLabel {{ color: {theme.TEXT}; }}')
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        info = QLabel('When any listed .exe is in focus, this profile auto-activates.')
        info.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_MUTED};')
        info.setWordWrap(True)
        lay.addWidget(info)

        lst = QListWidget()
        lst.setStyleSheet(f'background: {theme.BG_CARD}; border: 1px solid {theme.BORDER}; border-radius: 8px; color: {theme.TEXT};')
        for app in current:
            lst.addItem(app)
        lay.addWidget(lst)

        inp_row = QHBoxLayout()
        from PyQt5.QtWidgets import QLineEdit
        inp = QLineEdit()
        inp.setPlaceholderText('e.g. chrome.exe')
        inp.setStyleSheet(f'background: {theme.BG_ELEVATED}; border: 1px solid {theme.BORDER_LIGHT}; border-radius: 8px; color: {theme.TEXT}; padding: 6px 10px;')
        add_btn = QPushButton('Add')
        add_btn.setStyleSheet(f'QPushButton {{ background: {theme.ACCENT}; color: #000; border: none; border-radius: 8px; padding: 6px 14px; font-weight: 700; }} QPushButton:hover {{ background: {theme.ACCENT_HOVER}; }}')
        add_btn.clicked.connect(lambda: (lst.addItem(inp.text().strip()), inp.clear()) if inp.text().strip() else None)
        rem_btn = QPushButton('Remove')
        rem_btn.setStyleSheet(f'QPushButton {{ background: transparent; border: 1px solid {theme.BORDER_LIGHT}; border-radius: 8px; color: {theme.TEXT_MUTED}; padding: 6px 14px; }} QPushButton:hover {{ border-color: {theme.DANGER}; color: {theme.DANGER}; }}')
        rem_btn.clicked.connect(lambda: lst.takeItem(lst.currentRow()) if lst.currentRow() >= 0 else None)
        inp_row.addWidget(inp, 1)
        inp_row.addWidget(add_btn)
        inp_row.addWidget(rem_btn)
        lay.addLayout(inp_row)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton('Cancel')
        cancel.setStyleSheet(f'QPushButton {{ background: transparent; border: 1px solid {theme.BORDER_LIGHT}; color: {theme.TEXT_MUTED}; border-radius: 8px; padding: 8px 20px; }} QPushButton:hover {{ border-color: {theme.TEXT_DIM}; }}')
        cancel.clicked.connect(dlg.reject)
        save = QPushButton('Save')
        save.setStyleSheet(f'QPushButton {{ background: {theme.ACCENT}; color: #000; border: none; border-radius: 8px; padding: 8px 24px; font-weight: 700; }} QPushButton:hover {{ background: {theme.ACCENT_HOVER}; }}')
        save.clicked.connect(dlg.accept)
        btns.addWidget(cancel)
        btns.addSpacing(8)
        btns.addWidget(save)
        lay.addLayout(btns)

        if dlg.exec_() == QDialog.Accepted:
            apps = [lst.item(i).text() for i in range(lst.count())]
            profile_manager.set_trigger_apps(self._profile_data, active_name, apps)
            profile_manager.save(self._profile_data)

    # ── Auto profile switching ────────────────────────────────────────────────
    def _on_foreground_app_changed(self, app_name):
        if self._switching_profile:
            return
        match = profile_manager.find_profile_for_app(self._profile_data, app_name)
        if match and match != profile_manager.get_active_name(self._profile_data):
            self._profile_combo.blockSignals(True)
            self._profile_combo.setCurrentText(match)
            self._profile_combo.blockSignals(False)
            self._on_profile_changed(match)

    def _queue_profile_save(self):
        if not self._switching_profile:
            self._profile_save_timer.start()

    def _save_current_profile(self):
        if self._switching_profile:
            return
        enc_states = self._encoders_page.get_all_states()
        profile_manager.update_profile(self._profile_data, macro_manager.macros, enc_states)
        profile_manager.save(self._profile_data)

    def _apply_profile(self, profile):
        macro_manager.macros.clear()
        macro_manager.macros.update(profile.get('macros', {}))
        macro_manager.save_macros()

        self._macros_page.load_macros(macro_manager.macros)
        self._encoders_page.load_button_macros(macro_manager.macros)

        enc_states = profile.get('encoders', [{} for _ in range(4)])
        self._encoders_page.restore_all_states(enc_states)

        # Refresh apps so restored app selections populate correctly
        self._encoders_page.refresh_all_apps()
        QTimer.singleShot(300, self._sync_mute_states)

        # Push updated LED colors to Arduino
        if self._serial_manager:
            QTimer.singleShot(100, self._send_initial_led_state)

    def _on_profile_changed(self, name):
        if self._switching_profile or name == profile_manager.get_active_name(self._profile_data):
            return
        self._switching_profile = True
        self._save_current_profile()
        profile_manager.switch(self._profile_data, name)
        self._profile_combo.blockSignals(True)
        self._profile_combo.setCurrentText(name)
        self._profile_combo.blockSignals(False)
        self._apply_profile(profile_manager.get_active(self._profile_data))
        self._switching_profile = False

    def _new_profile(self):
        name, ok = QInputDialog.getText(self, 'New Profile', 'Profile name:')
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in profile_manager.get_names(self._profile_data):
            QMessageBox.warning(self, 'Profile exists', f'"{name}" already exists.')
            return
        self._switching_profile = True
        self._save_current_profile()
        profile_manager.create(self._profile_data, name)
        self._profile_combo.blockSignals(True)
        self._profile_combo.addItem(name)
        self._profile_combo.setCurrentText(name)
        self._profile_combo.blockSignals(False)
        self._apply_profile(profile_manager.get_active(self._profile_data))
        profile_manager.save(self._profile_data)
        self._switching_profile = False

    def _delete_profile(self):
        name = self._profile_combo.currentText()
        if len(profile_manager.get_names(self._profile_data)) <= 1:
            QMessageBox.information(self, 'Cannot delete', 'You need at least one profile.')
            return
        ans = QMessageBox.question(self, 'Delete profile',
                                   f'Delete "{name}"?',
                                   QMessageBox.Yes | QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        self._switching_profile = True
        profile_manager.delete(self._profile_data, name)
        new_name = profile_manager.get_active_name(self._profile_data)
        self._profile_combo.blockSignals(True)
        idx = self._profile_combo.findText(name)
        if idx >= 0:
            self._profile_combo.removeItem(idx)
        self._profile_combo.setCurrentText(new_name)
        self._profile_combo.blockSignals(False)
        self._apply_profile(profile_manager.get_active(self._profile_data))
        profile_manager.save(self._profile_data)
        self._switching_profile = False

    def closeEvent(self, event):
        self._fg_watcher.stop()
        # Stop all encoder timers so no new volume threads are spawned
        for timer in self._enc_timers.values():
            timer.stop()
        self._enc_timers.clear()
        for timer in self._mute_flash_timers.values():
            timer.stop()
        self._mute_flash_timers.clear()
        for timer in self._mute_stop_timers.values():
            timer.stop()
        self._mute_stop_timers.clear()

        # Wait for any in-flight volume threads to finish
        for thread in list(self._active_threads):
            thread.quit()
            thread.wait(300)
        self._active_threads.clear()

        # Stop serial (wakes sleeping reconnect thread immediately)
        if self._serial_manager:
            self._serial_manager.stop()

        self._save_current_profile()
        event.accept()


# ── Settings persistence ──────────────────────────────────────────────────────

def _ensure_data_dir():
    os.makedirs(os.path.dirname(get_data_path('x')), exist_ok=True)


def _save_settings(port, baud_rate, brightness_pct=10, enc_led_timeout_secs=2, effect_speed_ms=10, theme_mode='dark'):
    _ensure_data_dir()
    with open(get_data_path('settings_serial.json'), 'w') as f:
        json.dump({
            'port': port,
            'baud_rate': str(baud_rate),
            'brightness_pct': brightness_pct,
            'enc_led_timeout_secs': enc_led_timeout_secs,
            'effect_speed_ms': effect_speed_ms,
            'theme_mode': theme_mode,
        }, f)


def _load_settings():
    try:
        with open(get_data_path('settings_serial.json'), 'r') as f:
            data = json.load(f)
        return (
            data.get('port'),
            data.get('baud_rate', '115200'),
            data.get('brightness_pct', 10),
            data.get('enc_led_timeout_secs', 2),
            data.get('effect_speed_ms', 10),
            data.get('theme_mode', 'dark'),
        )
    except (FileNotFoundError, json.JSONDecodeError):
        return None
