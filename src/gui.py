import json
import os
import sys

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QPushButton, QFrame, QComboBox, QDialog, QGridLayout, QSlider,
    QSizePolicy, QInputDialog, QMessageBox, QSystemTrayIcon, QMenu, QAction,
    QFileDialog, QCheckBox, QListWidget, QListWidgetItem, QScrollArea,
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QFont

import theme
from widgets import (
    StatusBadge, NavButton, KeyCard, MacroAssignDialog, EncoderCard
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
        header.addWidget(title)
        header.addSpacing(14)
        header.addWidget(hint)
        header.addStretch()
        root.addLayout(header)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        root.addWidget(line)

        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setContentsMargins(0, 8, 0, 0)

        for row, keys in enumerate(self.KEY_LAYOUT):
            for col, key_id in enumerate(keys):
                card = KeyCard(key_id)
                card.assign_clicked.connect(self._on_key_clicked)
                self._cards[key_id] = card
                grid.addWidget(card, row, col, Qt.AlignCenter)

        wrap = QWidget()
        wrap.setStyleSheet('background: transparent;')
        wrap.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        wrap.setLayout(grid)

        center = QHBoxLayout()
        center.addStretch(1)
        center.addWidget(wrap, 0, Qt.AlignTop)
        center.addStretch(1)
        root.addLayout(center, 1)

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
        header.addWidget(title)
        header.addSpacing(14)
        header.addWidget(hint)
        header.addStretch()
        root.addLayout(header)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f'background: {theme.BORDER}; border: none;')
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

        title = QLabel('Settings')
        title.setStyleSheet('font-size: 20px; font-weight: 700; letter-spacing: -0.3px;')
        root.addWidget(title)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        root.addWidget(line)

        card = QFrame()
        card.setMaximumWidth(560)
        card.setStyleSheet(f'''
            QFrame {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER};
                border-radius: 12px;
            }}
            QLabel {{ background: transparent; color: {theme.TEXT}; }}
            QComboBox {{ background-color: {theme.BG_ELEVATED}; }}
        ''')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 24)
        card_layout.setSpacing(16)

        section_lbl = QLabel('SERIAL CONNECTION')
        section_lbl.setStyleSheet(f'font-size: 11px; font-weight: 600; color: {theme.TEXT_MUTED}; letter-spacing: 1px;')
        card_layout.addWidget(section_lbl)

        self._status = StatusBadge()
        card_layout.addWidget(self._status)

        port_row = QHBoxLayout()
        port_lbl = QLabel('Port')
        port_lbl.setStyleSheet(f'color: {theme.TEXT_MUTED}; min-width: 80px;')
        self._port_combo = QComboBox()
        refresh_btn = QPushButton('↻')
        refresh_btn.setFixedSize(34, 34)
        refresh_btn.setToolTip('Refresh ports')
        refresh_btn.setStyleSheet(f'QPushButton {{ background: {theme.BG_ELEVATED}; border: 1px solid {theme.BORDER}; border-radius: 8px; color: {theme.TEXT_MUTED}; font-size: 16px; padding: 0; }} QPushButton:hover {{ border-color: {theme.ACCENT}; color: {theme.ACCENT}; }}')
        refresh_btn.clicked.connect(self._refresh_ports)
        port_row.addWidget(port_lbl)
        port_row.addWidget(self._port_combo, 1)
        port_row.addWidget(refresh_btn)
        card_layout.addLayout(port_row)

        baud_row = QHBoxLayout()
        baud_lbl = QLabel('Baud Rate')
        baud_lbl.setStyleSheet(f'color: {theme.TEXT_MUTED}; min-width: 80px;')
        self._baud_combo = QComboBox()
        self._baud_combo.addItems(['115200', '500000', '230400', '57600', '9600'])
        baud_row.addWidget(baud_lbl)
        baud_row.addWidget(self._baud_combo, 1)
        card_layout.addLayout(baud_row)

        self._connect_btn = QPushButton('Connect')
        self._connect_btn.setFixedWidth(130)
        self._connect_btn.setStyleSheet(f'''
            QPushButton {{
                background: {theme.ACCENT}; color: #000; border: none;
                border-radius: 8px; padding: 10px 20px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {theme.ACCENT_HOVER}; }}
        ''')
        self._connect_btn.clicked.connect(self._request_connect)
        card_layout.addWidget(self._connect_btn)

        root.addWidget(card)

        # ── LED Brightness card ──────────────────────────────────────────────
        bright_card = QFrame()
        bright_card.setMaximumWidth(560)
        bright_card.setStyleSheet(f'''
            QFrame {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER};
                border-radius: 12px;
            }}
            QLabel {{ background: transparent; color: {theme.TEXT}; }}
            QSlider::groove:horizontal {{
                background: {theme.BG_ELEVATED};
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {theme.ACCENT};
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
            QSlider::sub-page:horizontal {{
                background: {theme.ACCENT};
                border-radius: 3px;
            }}
        ''')
        bright_layout = QVBoxLayout(bright_card)
        bright_layout.setContentsMargins(24, 20, 24, 24)
        bright_layout.setSpacing(14)

        bright_title = QLabel('LED BRIGHTNESS')
        bright_title.setStyleSheet(f'font-size: 11px; font-weight: 600; color: {theme.TEXT_MUTED}; letter-spacing: 1px;')
        bright_layout.addWidget(bright_title)

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
        enc_timeout_lbl = QLabel('Enc LED Off')
        enc_timeout_lbl.setStyleSheet(f'color: {theme.TEXT_MUTED}; min-width: 80px; font-size: 13px;')
        self._enc_timeout_combo = QComboBox()
        self._enc_timeout_combo.addItems(['2 seconds', '5 seconds', '10 seconds'])
        self._enc_timeout_combo.setCurrentText('2 seconds')
        self._enc_timeout_combo.currentIndexChanged.connect(self._on_encoder_led_timeout_changed)
        enc_timeout_row.addWidget(enc_timeout_lbl)
        enc_timeout_row.addWidget(self._enc_timeout_combo, 1)
        bright_layout.addLayout(enc_timeout_row)

        effect_speed_row = QHBoxLayout()
        effect_speed_lbl = QLabel('Effect Speed')
        effect_speed_lbl.setStyleSheet(f'color: {theme.TEXT_MUTED}; min-width: 80px; font-size: 13px;')
        self._effect_speed_combo = QComboBox()
        self._effect_speed_combo.addItems(['5 ms — Ultra', '10 ms — Smooth', '20 ms — Medium', '33 ms — Standard', '50 ms — Light'])
        self._effect_speed_combo.setCurrentText('10 ms — Smooth')
        self._effect_speed_combo.currentIndexChanged.connect(self._on_effect_speed_changed)
        effect_speed_row.addWidget(effect_speed_lbl)
        effect_speed_row.addWidget(self._effect_speed_combo, 1)
        bright_layout.addLayout(effect_speed_row)

        root.addWidget(bright_card)

        # ── Startup + Profile I/O card ───────────────────────────────────────
        misc_card = QFrame()
        misc_card.setMaximumWidth(560)
        misc_card.setStyleSheet(f'''
            QFrame {{
                background-color: {theme.BG_CARD}; border: 1px solid {theme.BORDER};
                border-radius: 12px;
            }}
            QLabel {{ background: transparent; color: {theme.TEXT}; }}
        ''')
        misc_layout = QVBoxLayout(misc_card)
        misc_layout.setContentsMargins(24, 20, 24, 20)
        misc_layout.setSpacing(14)

        misc_title = QLabel('GENERAL')
        misc_title.setStyleSheet(f'font-size: 11px; font-weight: 600; color: {theme.TEXT_MUTED}; letter-spacing: 1px;')
        misc_layout.addWidget(misc_title)

        self._startup_cb = QCheckBox('Start with Windows')
        self._startup_cb.setStyleSheet(f'color: {theme.TEXT}; font-size: 13px;')
        self._startup_cb.setChecked(self._read_startup_registry())
        self._startup_cb.stateChanged.connect(self._on_startup_changed)
        misc_layout.addWidget(self._startup_cb)

        io_row = QHBoxLayout()
        _btn_style = f'''
            QPushButton {{
                background: {theme.BG_ELEVATED}; border: 1px solid {theme.BORDER_LIGHT};
                border-radius: 8px; color: {theme.TEXT_MUTED}; padding: 7px 16px; font-size: 12px;
            }}
            QPushButton:hover {{ border-color: {theme.ACCENT}; color: {theme.ACCENT}; }}
        '''
        exp_btn = QPushButton('↓  Export Profile')
        exp_btn.setStyleSheet(_btn_style)
        exp_btn.clicked.connect(self.export_requested)
        imp_btn = QPushButton('↑  Import Profile')
        imp_btn.setStyleSheet(_btn_style)
        imp_btn.clicked.connect(self.import_requested)
        io_row.addWidget(exp_btn)
        io_row.addWidget(imp_btn)
        io_row.addStretch()
        misc_layout.addLayout(io_row)

        root.addWidget(misc_card)
        root.addStretch()

        self._refresh_ports()

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
        hint = QLabel('Press any key or encoder button — the active macro is shown below.')
        hint.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_DIM};')
        root.addWidget(title)
        root.addWidget(hint)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        root.addWidget(line)

        grid = QGridLayout()
        grid.setSpacing(10)
        for idx, key in enumerate(self.KEY_ORDER):
            card = QFrame()
            card.setFixedHeight(64)
            card.setStyleSheet(f'''
                QFrame {{
                    background: {theme.BG_CARD}; border: 1px solid {theme.BORDER};
                    border-radius: 10px;
                }}
            ''')
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
            grid.addWidget(card, idx // 4, idx % 4)

        root.addLayout(grid)

        log_lbl = QLabel('RECENT EVENTS')
        log_lbl.setStyleSheet(f'font-size: 10px; font-weight: 600; color: {theme.TEXT_DIM}; letter-spacing: 1px; margin-top: 4px;')
        root.addWidget(log_lbl)

        self._log = QListWidget()
        self._log.setFixedHeight(160)
        self._log.setStyleSheet(f'''
            QListWidget {{
                background: {theme.BG_CARD}; border: 1px solid {theme.BORDER};
                border-radius: 10px; color: {theme.TEXT}; font-size: 12px;
                padding: 6px;
            }}
        ''')
        root.addWidget(self._log)
        root.addStretch()

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
        self._tray = None
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

        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFixedWidth(1)
        divider.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        root.addWidget(divider)

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

        for page in (self._macros_page, self._encoders_page,
                     self._settings_page, self._upload_page, self._test_page):
            self._stack.addWidget(page)

        root.addWidget(self._stack, 1)

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(216)
        sidebar.setStyleSheet(f'''
            QFrame {{
                background-color: {theme.SIDEBAR_BG};
                border: none;
            }}
        ''')

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 20)
        layout.setSpacing(0)

        # Logo area
        logo_frame = QWidget()
        logo_frame.setFixedHeight(68)
        logo_frame.setStyleSheet(
            f'background: transparent; border-bottom: 1px solid {theme.BORDER};')
        logo_row = QHBoxLayout(logo_frame)
        logo_row.setContentsMargins(16, 0, 16, 0)
        logo_row.setSpacing(11)

        icon_box = QLabel('◈')
        icon_box.setFixedSize(32, 32)
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setStyleSheet(f'''
            background: {theme.ACCENT}20; color: {theme.ACCENT};
            border: 1px solid {theme.ACCENT}40; border-radius: 8px;
            font-size: 16px;
        ''')

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        name_lbl = QLabel('MacroPad')
        name_lbl.setStyleSheet(
            f'font-size: 14px; font-weight: 700; color: {theme.TEXT}; letter-spacing: 0.3px;')
        sub_lbl = QLabel('Controller')
        sub_lbl.setStyleSheet(
            f'font-size: 10px; color: {theme.TEXT_DIM}; letter-spacing: 0.5px;')
        title_col.addWidget(name_lbl)
        title_col.addWidget(sub_lbl)

        logo_row.addWidget(icon_box)
        logo_row.addLayout(title_col)
        logo_row.addStretch()
        layout.addWidget(logo_frame)

        # ── Profile selector ─────────────────────────────────────────────────
        prof_frame = QWidget()
        prof_frame.setFixedHeight(56)
        prof_frame.setStyleSheet(
            f'background: transparent; border-bottom: 1px solid {theme.BORDER};')
        prof_outer = QVBoxLayout(prof_frame)
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
        new_prof_btn = QPushButton('+')
        new_prof_btn.setFixedSize(24, 24)
        new_prof_btn.setToolTip('New profile')
        new_prof_btn.setStyleSheet(_prof_btn_style)
        new_prof_btn.clicked.connect(self._new_profile)

        del_prof_btn = QPushButton('×')
        del_prof_btn.setFixedSize(24, 24)
        del_prof_btn.setToolTip('Delete profile')
        del_prof_btn.setStyleSheet(_prof_btn_style)
        del_prof_btn.clicked.connect(self._delete_profile)

        trig_btn = QPushButton('⚡')
        trig_btn.setFixedSize(24, 24)
        trig_btn.setToolTip('Auto-switch trigger apps')
        trig_btn.setStyleSheet(_prof_btn_style)
        trig_btn.clicked.connect(self._edit_trigger_apps)

        prof_row.addWidget(self._profile_combo, 1)
        prof_row.addWidget(new_prof_btn)
        prof_row.addWidget(trig_btn)
        prof_row.addWidget(del_prof_btn)
        prof_outer.addLayout(prof_row)
        layout.addWidget(prof_frame)
        layout.addSpacing(4)

        self._nav_btns = []
        for icon, label, idx in [
            ('⌨', 'Macros', 0),
            ('⚙', 'Encoders', 1),
            ('◎', 'Settings', 2),
            ('⬆', 'Upload', 3),
            ('▶', 'Test', 4),
        ]:
            btn = NavButton(icon, label)
            btn.clicked.connect(lambda i=idx: self._navigate(i))
            self._nav_btns.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Status area
        status_frame = QWidget()
        status_frame.setStyleSheet(
            f'background: transparent; border-top: 1px solid {theme.BORDER};')
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(14, 12, 14, 0)
        status_layout.setSpacing(0)
        self._sidebar_status = StatusBadge()
        status_layout.addWidget(self._sidebar_status)
        layout.addWidget(status_frame)

        return sidebar

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
        self._setup_tray()

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
                           self._settings_page.get_effect_speed_ms())
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

    # ── System tray ───────────────────────────────────────────────────────────
    def _setup_tray(self):
        from utils import resource_path
        from PyQt5.QtGui import QIcon
        icon = QIcon(resource_path('Assets/Images/icon.ico'))
        self._tray = QSystemTrayIcon(icon, self)
        self._tray_menu = QMenu()
        self._tray_profile_menu = QMenu('Profile')
        self._tray_menu.addMenu(self._tray_profile_menu)
        self._refresh_tray_profiles()
        self._tray_menu.addSeparator()
        show_act = QAction('Show', self)
        show_act.triggered.connect(self._show_from_tray)
        self._tray_menu.addAction(show_act)
        quit_act = QAction('Quit', self)
        quit_act.triggered.connect(self._quit_app)
        self._tray_menu.addAction(quit_act)
        self._tray.setContextMenu(self._tray_menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _refresh_tray_profiles(self):
        self._tray_profile_menu.clear()
        active = profile_manager.get_active_name(self._profile_data)
        for name in profile_manager.get_names(self._profile_data):
            act = QAction(('✓  ' if name == active else '    ') + name, self)
            act.triggered.connect(lambda checked=False, n=name: self._on_profile_changed(n))
            self._tray_profile_menu.addAction(act)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_app(self):
        self._tray.hide()
        self._save_current_profile()
        import sys
        sys.exit(0)

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
        self._refresh_tray_profiles()
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
        if self._tray and self._tray.isVisible():
            self.hide()
            event.ignore()
            return

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


def _save_settings(port, baud_rate, brightness_pct=10, enc_led_timeout_secs=2, effect_speed_ms=10):
    _ensure_data_dir()
    with open(get_data_path('settings_serial.json'), 'w') as f:
        json.dump({
            'port': port,
            'baud_rate': str(baud_rate),
            'brightness_pct': brightness_pct,
            'enc_led_timeout_secs': enc_led_timeout_secs,
            'effect_speed_ms': effect_speed_ms,
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
        )
    except (FileNotFoundError, json.JSONDecodeError):
        return None
