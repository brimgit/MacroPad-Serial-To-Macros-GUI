import json
import os
import sys

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QPushButton, QFrame, QComboBox, QDialog, QGridLayout, QSlider,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QFont

import theme
from widgets import (
    StatusBadge, NavButton, KeyCard, MacroAssignDialog, EncoderCard
)
from utils import get_data_path
import macro_manager


# ── Thread-safe bridge from serial thread → main thread ──────────────────────

class _Bridge(QObject):
    data_received = pyqtSignal(str)


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
    # Keys 1-8 are the regular pad buttons; A-D are encoder buttons (handled in EncodersPage)
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

    def load_macros(self, macros_dict):
        for key_id, card in self._cards.items():
            press = macros_dict.get(f'KP:{key_id}')
            hold = macros_dict.get(f'KP:{key_id}:HOLD')
            card.set_macros(press, hold)


class EncodersPage(QWidget):
    send_command = pyqtSignal(str)

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
            card.app_refresh_requested.connect(self._refresh_apps_for)
            card.button_macro_requested.connect(self._on_button_macro_requested)
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

    def update_volume_display(self, encoder_id, pct):
        card = self._cards.get(encoder_id)
        if card:
            card.set_percentage(pct)


class SettingsPage(QWidget):
    reconnect_requested = pyqtSignal(str, int)
    brightness_changed = pyqtSignal(int)   # 0-255
    timeout_changed = pyqtSignal(int)      # seconds (0 = off)

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

        timeout_row = QHBoxLayout()
        timeout_lbl = QLabel('Timeout')
        timeout_lbl.setStyleSheet(f'color: {theme.TEXT_MUTED}; min-width: 80px; font-size: 13px;')
        self._timeout_combo = QComboBox()
        self._timeout_combo.addItems(['Off', '30 seconds', '1 minute', '5 minutes', '10 minutes'])
        self._timeout_combo.setCurrentText('1 minute')
        self._timeout_combo.currentIndexChanged.connect(self._on_timeout_changed)
        timeout_row.addWidget(timeout_lbl)
        timeout_row.addWidget(self._timeout_combo, 1)
        bright_layout.addLayout(timeout_row)

        root.addWidget(bright_card)
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

    _TIMEOUT_SECONDS = {'Off': 0, '30 seconds': 30, '1 minute': 60,
                        '5 minutes': 300, '10 minutes': 600}

    def _on_brightness_changed(self, pct):
        self._bright_value_lbl.setText(f'{pct}%')
        self._bright_debounce.start(150)  # send only after 150 ms of no movement

    def _emit_brightness(self):
        pct = self._bright_slider.value()
        self.brightness_changed.emit(round(pct * 255 / 100))

    def _on_timeout_changed(self):
        secs = self._TIMEOUT_SECONDS.get(self._timeout_combo.currentText(), 60)
        self.timeout_changed.emit(secs)

    def get_timeout_seconds(self):
        return self._TIMEOUT_SECONDS.get(self._timeout_combo.currentText(), 60)

    def set_timeout_seconds(self, secs):
        reverse = {v: k for k, v in self._TIMEOUT_SECONDS.items()}
        label = reverse.get(secs, '1 minute')
        self._timeout_combo.blockSignals(True)
        self._timeout_combo.setCurrentText(label)
        self._timeout_combo.blockSignals(False)

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
        self._enc_percentages = {0: 50, 1: 50, 2: 50, 3: 50}  # local LED state
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

        self._encoders_page.send_command.connect(self._serial_send)
        self._settings_page.reconnect_requested.connect(self._do_connect)
        self._settings_page.brightness_changed.connect(self._on_brightness_slider)
        self._settings_page.timeout_changed.connect(self._on_timeout_changed)

        for page in (self._macros_page, self._encoders_page,
                     self._settings_page, self._upload_page):
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
        layout.addSpacing(8)

        self._nav_btns = []
        for icon, label, idx in [
            ('⌨', 'Macros', 0),
            ('⚙', 'Encoders', 1),
            ('◎', 'Settings', 2),
            ('⬆', 'Upload', 3),
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

    def _load_on_startup(self):
        loaded = macro_manager.reload_macros()
        self._macros_page.load_macros(loaded)
        self._encoders_page.load_button_macros(loaded)

        settings = _load_settings()
        port           = settings[0] if settings else 'COM6'
        baud           = int(settings[1]) if settings else 115200
        brightness_pct = int(settings[2]) if settings and settings[2] else 10
        timeout_secs   = int(settings[3]) if settings and len(settings) > 3 and settings[3] is not None else 60

        self._settings_page.prefill(port, baud)
        self._settings_page.set_brightness_pct(brightness_pct)
        self._settings_page.set_timeout_seconds(timeout_secs)
        self._do_connect(port, baud)
        self._navigate(0)

    def _do_connect(self, port, baud_rate):
        if self._serial_manager:
            self._serial_manager.stop()

        try:
            from serial_manager import SerialManager
            self._serial_manager = SerialManager(
                data_callback=self._bridge.data_received.emit,
                port=port,
                baud_rate=baud_rate,
            )
            self._encoders_page.set_volume_manager(self._serial_manager.volume_manager)
            self._upload_page.set_serial_manager(self._serial_manager)
            self._sidebar_status.set_connected(True, port)
            self._settings_page.set_status(True, port)
            _save_settings(port, str(baud_rate), self._settings_page._bright_slider.value(),
                           self._settings_page.get_timeout_seconds())
            # Push brightness then LED state after Arduino has had time to boot
            QTimer.singleShot(2500, self._send_initial_brightness)
            QTimer.singleShot(2600, self._send_initial_led_state)
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
            # DOWN events intentionally ignored — we act on UP so we know hold duration
            return

        # Log anything else (Arduino error responses, debug output)
        import logging
        logging.debug(f'Arduino: {data}')

    def _execute_macro_or_mute(self, key, macro_key):
        """Run the macro for macro_key, but intercept 'Mute App' and route it
        to the app assigned to that encoder (A→enc0, B→enc1, C→enc2, D→enc3)."""
        macro = macro_manager.macros.get(macro_key)
        if macro and macro.get('type') == 'Mute App' and key in ('A', 'B', 'C', 'D'):
            enc_id = ord(key) - ord('A')
            app_name = self._encoders_page.get_encoder_app(enc_id)
            if app_name and self._serial_manager:
                self._serial_manager.volume_manager.toggle_mute(app_name)
        else:
            macro_manager.execute_macro(macro_key)

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
            self._settings_page.get_timeout_seconds(),
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
            # App assigned but no longer running — flash red and turn off
            self._flash_red(enc_id)
            return
        self._enc_percentages[enc_id] = pct
        self._encoders_page.update_volume_display(enc_id, pct)
        # Arduino LED strips are 1-indexed: strip 1 = encoder 0
        self._serial_send(f'{enc_id + 1}:{pct}')

    def _send_initial_brightness(self):
        self._serial_send(f'BRIGHT:{self._settings_page.get_brightness_255()}')
        self._serial_send(f'TIMEOUT:{self._settings_page.get_timeout_seconds()}')

    def _on_timeout_changed(self, secs):
        self._serial_send(f'TIMEOUT:{secs}')

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

    def closeEvent(self, event):
        # Stop all encoder timers so no new volume threads are spawned
        for timer in self._enc_timers.values():
            timer.stop()
        self._enc_timers.clear()

        # Wait for any in-flight volume threads to finish
        for thread in list(self._active_threads):
            thread.quit()
            thread.wait(300)
        self._active_threads.clear()

        # Stop serial (wakes sleeping reconnect thread immediately)
        if self._serial_manager:
            self._serial_manager.stop()

        event.accept()


# ── Settings persistence ──────────────────────────────────────────────────────

def _ensure_data_dir():
    os.makedirs(os.path.dirname(get_data_path('x')), exist_ok=True)


def _save_settings(port, baud_rate, brightness_pct=10, timeout_secs=60):
    _ensure_data_dir()
    with open(get_data_path('settings_serial.json'), 'w') as f:
        json.dump({
            'port': port,
            'baud_rate': str(baud_rate),
            'brightness_pct': brightness_pct,
            'timeout_secs': timeout_secs,
        }, f)


def _load_settings():
    try:
        with open(get_data_path('settings_serial.json'), 'r') as f:
            data = json.load(f)
        return (
            data.get('port'),
            data.get('baud_rate', '115200'),
            data.get('brightness_pct', 10),
            data.get('timeout_secs', 60),
        )
    except (FileNotFoundError, json.JSONDecodeError):
        return None
