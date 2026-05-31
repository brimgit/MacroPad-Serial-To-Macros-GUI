import json

from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QColorDialog, QDialog, QSizePolicy, QSlider
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPoint
from PyQt5.QtGui import QPainter, QColor, QBrush, QFont
import theme


MACRO_TYPES = ['Keyboard Key', 'Media Control', 'Function Key', 'Modifier Key',
               'Type Text', 'Mute App', 'Recorded']

MACRO_ACTIONS = {
    'Keyboard Key': (
        [chr(i) for i in range(ord('a'), ord('z') + 1)] +
        [str(i) for i in range(0, 10)] +
        ['space', 'enter', 'backspace', 'tab', 'escape', 'delete',
         'insert', 'home', 'end', 'page up', 'page down',
         'up', 'down', 'left', 'right',
         'print screen', 'scroll lock', 'pause',
         'num lock', 'caps lock']
    ),
    'Media Control': [
        'play/pause', 'next track', 'previous track', 'stop',
        'volume up', 'volume down',
    ],
    'Function Key': [f'f{i}' for i in range(1, 25)],
    'Modifier Key': [
        'ctrl', 'shift', 'alt', 'win',
        'ctrl+c', 'ctrl+v', 'ctrl+x', 'ctrl+z', 'ctrl+y',
        'ctrl+s', 'ctrl+a', 'ctrl+shift+esc',
        'alt+f4', 'alt+tab', 'win+d', 'win+l', 'win+e',
    ],
    'Type Text': [],
    'Mute App': ['Toggle mute for assigned app'],
    'Recorded': [],
}


class StatusBadge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(7)

        self.dot = QLabel('●')
        self.dot.setFixedWidth(10)
        self.dot.setStyleSheet(f'font-size: 9px; color: {theme.DANGER};')

        self.text = QLabel('Not Connected')
        self.text.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_MUTED};')

        layout.addWidget(self.dot)
        layout.addWidget(self.text)

    def set_connected(self, connected, port=''):
        if connected:
            self.dot.setStyleSheet(f'font-size: 9px; color: {theme.SUCCESS};')
            self.text.setText(port if port else 'Connected')
            self.text.setStyleSheet(f'font-size: 12px; color: {theme.TEXT};')
        else:
            self.dot.setStyleSheet(f'font-size: 9px; color: {theme.DANGER};')
            self.text.setText('Not Connected')
            self.text.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_MUTED};')


class NavButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, icon_char, label, parent=None):
        super().__init__(parent)
        self._active = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(46)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(11)

        self._icon = QLabel(icon_char)
        self._icon.setFixedSize(24, 24)
        self._icon.setAlignment(Qt.AlignCenter)
        self._icon.setStyleSheet(f'font-size: 14px; color: {theme.TEXT_DIM};')

        self._label = QLabel(label)
        self._label.setStyleSheet(f'font-size: 13px; color: {theme.TEXT_MUTED}; letter-spacing: 0.2px;')

        layout.addWidget(self._icon)
        layout.addWidget(self._label)
        layout.addStretch()

        self._set_style(False)

    def set_active(self, active):
        self._active = active
        self._set_style(active)

    def _set_style(self, active):
        if active:
            self.setStyleSheet(f'''
                NavButton {{
                    background-color: {theme.ACCENT}18;
                    border-left: 2px solid {theme.ACCENT};
                    border-right: 2px solid transparent;
                }}
            ''')
            self._icon.setStyleSheet(f'font-size: 14px; color: {theme.ACCENT};')
            self._label.setStyleSheet(
                f'font-size: 13px; color: {theme.ACCENT}; font-weight: 600; letter-spacing: 0.2px;')
        else:
            self.setStyleSheet(f'''
                NavButton {{
                    background-color: transparent;
                    border-left: 2px solid transparent;
                    border-right: 2px solid transparent;
                }}
                NavButton:hover {{
                    background-color: {theme.BG_ELEVATED}88;
                    border-left: 2px solid {theme.BORDER_LIGHT};
                }}
            ''')
            self._icon.setStyleSheet(f'font-size: 14px; color: {theme.TEXT_DIM};')
            self._label.setStyleSheet(
                f'font-size: 13px; color: {theme.TEXT_MUTED}; letter-spacing: 0.2px;')

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class LEDPreview(QWidget):
    N_LEDS = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._r, self._g, self._b = 6, 182, 212
        self._r2, self._g2, self._b2 = 255, 100, 0   # fade end colour
        self._blend_start = 0
        self._percentage = 70
        self._mode = 'default'
        self._led_colors = [QColor(20, 30, 40)] * self.N_LEDS
        self.setFixedHeight(30)
        self.setMinimumWidth(self.N_LEDS * 24)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self._recalculate()

    def set_state(self, r, g, b, mode='solid', percentage=70,
                  r2=None, g2=None, b2=None, blend_start=0):
        self._r, self._g, self._b = r, g, b
        self._r2 = r2 if r2 is not None else self._r2
        self._g2 = g2 if g2 is not None else self._g2
        self._b2 = b2 if b2 is not None else self._b2
        self._blend_start = blend_start
        self._percentage = max(0, min(100, percentage))
        self._mode = mode
        self._recalculate()
        self.update()

    def set_percentage(self, percentage):
        self._percentage = max(0, min(100, percentage))
        self._recalculate()
        self.update()

    def _recalculate(self):
        r, g, b = self._r, self._g, self._b
        lit = round(self.N_LEDS * self._percentage / 100)
        off = QColor(20, 30, 40)

        if self._mode == 'default':
            colors = []
            for i in range(self.N_LEDS):
                if i >= lit:
                    colors.append(off)
                else:
                    t = i / max(1, self.N_LEDS - 1)
                    colors.append(QColor(
                        int(200 * t),
                        int(200 * (1 - t)),
                        0
                    ))
            self._led_colors = colors

        elif self._mode == 'fade':
            # Position-based gradient: blendStart% = LED position where transition begins
            blend_s = self._blend_start / 100.0
            colors = []
            for i in range(self.N_LEDS):
                if i >= lit:
                    colors.append(off)
                else:
                    led_pos = i / max(1, self.N_LEDS - 1)
                    if led_pos <= blend_s:
                        t = 0.0
                    elif blend_s >= 1.0:
                        t = 0.0
                    else:
                        t = (led_pos - blend_s) / (1.0 - blend_s)
                    t = min(1.0, max(0.0, t))
                    colors.append(QColor(
                        int(r + (self._r2 - r) * t),
                        int(g + (self._g2 - g) * t),
                        int(b + (self._b2 - b) * t)
                    ))
            self._led_colors = colors

        else:
            self._led_colors = [
                QColor(r, g, b) if i < lit else off
                for i in range(self.N_LEDS)
            ]

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(13, 19, 32))

        w = self.width() / self.N_LEDS
        h = self.height()
        radius = min(w, h) / 2 - 3

        for i, color in enumerate(self._led_colors):
            cx = i * w + w / 2
            cy = h / 2

            is_off = (color.red() <= 20 and color.green() <= 30 and color.blue() <= 40)
            if not is_off:
                glow = QColor(color.red(), color.green(), color.blue(), 45)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(glow))
                p.drawEllipse(QPoint(int(cx), int(cy)), int(radius + 4), int(radius + 4))

            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(color))
            p.drawEllipse(QPoint(int(cx), int(cy)), int(radius), int(radius))

        p.end()


class KeyRecorderWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._events = []
        self._hook = None
        self._recording = False
        self._recorded_json = ''
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._record_btn = QPushButton('● Record')
        self._record_btn.setFixedHeight(28)
        self._record_btn.setStyleSheet(f'''
            QPushButton {{
                background: {theme.DANGER}; color: #fff; border: none;
                border-radius: 6px; padding: 0 10px; font-size: 11px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {theme.DANGER}cc; }}
            QPushButton:disabled {{
                background: {theme.BG_ELEVATED}; color: {theme.TEXT_DIM};
                border: 1px solid {theme.BORDER};
            }}
        ''')
        self._record_btn.clicked.connect(self._start_recording)

        self._stop_btn = QPushButton('■ Stop')
        self._stop_btn.setFixedHeight(28)
        self._stop_btn.setEnabled(False)
        self._stop_btn.setStyleSheet(f'''
            QPushButton {{
                background: {theme.BG_ELEVATED}; color: {theme.TEXT_MUTED};
                border: 1px solid {theme.BORDER}; border-radius: 6px;
                padding: 0 10px; font-size: 11px;
            }}
            QPushButton:enabled:hover {{ border-color: {theme.ACCENT}; color: {theme.ACCENT}; }}
            QPushButton:disabled {{ color: {theme.TEXT_DIM}; }}
        ''')
        self._stop_btn.clicked.connect(self._stop_recording)

        self._display = QLabel('No recording')
        self._display.setStyleSheet(f'font-size: 11px; color: {theme.TEXT_MUTED};')

        layout.addWidget(self._record_btn)
        layout.addWidget(self._stop_btn)
        layout.addWidget(self._display, 1)

    def _start_recording(self):
        import keyboard as _kb
        self._events = []
        self._recording = True
        self._record_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._display.setText('Recording...')
        self._display.setStyleSheet(f'font-size: 11px; color: {theme.DANGER};')
        self._hook = _kb.hook(self._on_key_event)

    def _stop_recording(self):
        if self._hook:
            import keyboard as _kb
            _kb.unhook(self._hook)
            self._hook = None
        self._recording = False
        self._record_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._serialize()
        self._update_display()

    def _on_key_event(self, event):
        self._events.append({
            'event_type': event.event_type,
            'scan_code': event.scan_code,
            'name': event.name,
            'time': event.time,
        })

    def _serialize(self):
        if not self._events:
            self._recorded_json = ''
            return
        t0 = self._events[0]['time']
        normalized = [{**e, 'time': round(e['time'] - t0, 4)} for e in self._events]
        self._recorded_json = json.dumps(normalized)

    def _update_display(self):
        if not self._events:
            self._display.setText('No recording')
            self._display.setStyleSheet(f'font-size: 11px; color: {theme.TEXT_MUTED};')
            return
        down_events = [e for e in self._events if e['event_type'] == 'down']
        groups, current, last_t = [], [], None
        for e in down_events:
            t = e['time']
            if last_t is None or (t - last_t) < 0.12:
                current.append(e['name'])
            else:
                groups.append(current)
                current = [e['name']]
            last_t = t
        if current:
            groups.append(current)
        summary = ' → '.join('+'.join(g) for g in groups) or 'recorded'
        self._display.setText(summary)
        self._display.setStyleSheet(f'font-size: 11px; color: {theme.ACCENT};')

    def get_recorded_json(self):
        return self._recorded_json

    def set_recorded_json(self, s):
        self._recorded_json = s or ''
        if s:
            try:
                self._events = json.loads(s)
                self._update_display()
            except (json.JSONDecodeError, KeyError):
                pass
        else:
            self._events = []
            self._update_display()

    def clear(self):
        self.stop_if_recording()
        self._events = []
        self._recorded_json = ''
        self._display.setText('No recording')
        self._display.setStyleSheet(f'font-size: 11px; color: {theme.TEXT_MUTED};')

    def stop_if_recording(self):
        if self._recording:
            self._stop_recording()


class KeyCard(QFrame):
    assign_clicked = pyqtSignal(str)

    def __init__(self, key_id, parent=None):
        super().__init__(parent)
        self.key_id = key_id
        self.press_data = None
        self.hold_data = None
        self.setFixedSize(100, 100)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._build_ui()
        self._refresh_style()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(3)

        self._key_lbl = QLabel(self.key_id)
        self._key_lbl.setAlignment(Qt.AlignCenter)
        font = QFont('Segoe UI Variable', 18, QFont.Bold)
        self._key_lbl.setFont(font)
        self._key_lbl.setStyleSheet('background: transparent;')

        self._press_lbl = QLabel('—')
        self._press_lbl.setAlignment(Qt.AlignCenter)
        self._press_lbl.setStyleSheet(
            f'font-size: 11px; color: {theme.TEXT_MUTED}; background: transparent;')
        self._press_lbl.setWordWrap(True)

        self._hold_lbl = QLabel('')
        self._hold_lbl.setAlignment(Qt.AlignCenter)
        self._hold_lbl.setStyleSheet(
            f'font-size: 10px; color: {theme.TEXT_DIM}; font-style: italic; background: transparent;')

        layout.addWidget(self._key_lbl)
        layout.addWidget(self._press_lbl)
        layout.addWidget(self._hold_lbl)

    def set_macros(self, press_data=None, hold_data=None):
        self.press_data = press_data
        self.hold_data = hold_data

        if press_data:
            if press_data.get('type') == 'Recorded':
                display = '[recorded]'
            else:
                action = press_data.get('action', '—')
                display = action if len(action) <= 12 else action[:10] + '..'
            self._press_lbl.setText(display)
            self._press_lbl.setStyleSheet(
                f'font-size: 11px; color: {theme.ACCENT}; background: transparent; font-weight: 600;')
        else:
            self._press_lbl.setText('—')
            self._press_lbl.setStyleSheet(
                f'font-size: 11px; color: {theme.TEXT_MUTED}; background: transparent;')

        if hold_data:
            action = hold_data.get('action', '')
            display = action if len(action) <= 9 else action[:7] + '..'
            self._hold_lbl.setText(f'hold: {display}')
        else:
            self._hold_lbl.setText('')

        self._refresh_style()

    def _refresh_style(self):
        if self.press_data:
            self.setStyleSheet(f'''
                KeyCard {{
                    background-color: {theme.BG_CARD};
                    border: 1px solid {theme.ACCENT}44;
                    border-top: 1px solid {theme.ACCENT}88;
                    border-radius: 12px;
                }}
                KeyCard:hover {{
                    background-color: {theme.BG_ELEVATED};
                    border: 1px solid {theme.ACCENT}99;
                    border-top: 1px solid {theme.ACCENT};
                }}
            ''')
        else:
            self.setStyleSheet(f'''
                KeyCard {{
                    background-color: {theme.BG_CARD};
                    border: 1px solid {theme.BORDER};
                    border-radius: 12px;
                }}
                KeyCard:hover {{
                    background-color: {theme.BG_ELEVATED};
                    border: 1px solid {theme.BORDER_LIGHT};
                    border-top: 1px solid {theme.TEXT_DIM};
                }}
            ''')

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.assign_clicked.emit(self.key_id)
        super().mousePressEvent(event)


class MacroAssignDialog(QDialog):
    def __init__(self, key_id, press_data=None, hold_data=None, parent=None):
        super().__init__(parent)
        self.key_id = key_id
        self._press_result = dict(press_data) if press_data else None
        self._hold_result = dict(hold_data) if hold_data else None
        self._press_cleared = False
        self._hold_cleared = False

        self.setWindowTitle(f'Assign — Key {key_id}')
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setStyleSheet(f'''
            QDialog {{ background-color: {theme.BG}; }}
            QLabel {{ background: transparent; color: {theme.TEXT}; }}
            QFrame {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER};
                border-top: 1px solid {theme.BORDER_LIGHT};
                border-radius: 12px;
            }}
            QComboBox {{
                background-color: {theme.BG_ELEVATED};
                border: 1px solid {theme.BORDER_LIGHT};
                border-radius: 8px;
                color: {theme.TEXT};
                padding: 6px 32px 6px 10px;
            }}
            QComboBox:hover {{ border-color: {theme.ACCENT}; }}
            QComboBox QAbstractItemView {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER_LIGHT};
                color: {theme.TEXT};
                selection-background-color: {theme.ACCENT};
                selection-color: #000;
            }}
        ''')
        self._build_ui()
        self._populate(press_data, hold_data)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        header_row = QHBoxLayout()
        key_badge = QLabel(f' {self.key_id} ')
        key_badge.setStyleSheet(f'''
            background: {theme.ACCENT}22; color: {theme.ACCENT};
            border: 1px solid {theme.ACCENT}55; border-radius: 6px;
            font-size: 13px; font-weight: 700; padding: 2px 8px;
        ''')
        title = QLabel('Assign Macro')
        title.setStyleSheet(f'font-size: 18px; font-weight: 700; color: {theme.TEXT};')
        header_row.addWidget(title)
        header_row.addSpacing(10)
        header_row.addWidget(key_badge)
        header_row.addStretch()
        root.addLayout(header_row)

        self._press_type, self._press_action, self._press_recorder, self._press_text = self._add_section(root, 'Press', 'press')
        self._hold_type, self._hold_action, self._hold_recorder, self._hold_text = self._add_section(root, 'Hold', 'hold')

        btns = QHBoxLayout()
        btns.addStretch()

        cancel = QPushButton('Cancel')
        cancel.setStyleSheet(f'''
            QPushButton {{
                background: transparent; border: 1px solid {theme.BORDER_LIGHT};
                color: {theme.TEXT_MUTED}; border-radius: 8px; padding: 8px 20px;
            }}
            QPushButton:hover {{ border-color: {theme.TEXT_DIM}; color: {theme.TEXT}; }}
        ''')
        cancel.clicked.connect(self.reject)

        save = QPushButton('Save')
        save.setStyleSheet(f'''
            QPushButton {{
                background: {theme.ACCENT}; color: #000; border: none;
                border-radius: 8px; padding: 8px 28px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {theme.ACCENT_HOVER}; }}
        ''')
        save.clicked.connect(self._on_save)

        btns.addWidget(cancel)
        btns.addSpacing(8)
        btns.addWidget(save)
        root.addLayout(btns)

    def _add_section(self, parent_layout, label, prefix):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f'font-size: 10px; font-weight: 700; color: {theme.TEXT_DIM}; letter-spacing: 1.5px;')
        clear_btn = QPushButton('Clear')
        clear_btn.setFixedSize(52, 24)
        clear_btn.setStyleSheet(f'''
            QPushButton {{
                background: transparent; border: 1px solid {theme.DANGER}44;
                color: {theme.DANGER}99; border-radius: 6px; font-size: 11px; padding: 0;
            }}
            QPushButton:hover {{ background: {theme.DANGER}18; border-color: {theme.DANGER}; color: {theme.DANGER}; }}
        ''')
        clear_btn.clicked.connect(lambda: self._clear(prefix))
        header.addWidget(lbl)
        header.addStretch()
        header.addWidget(clear_btn)
        layout.addLayout(header)

        type_row = QHBoxLayout()
        type_lbl = QLabel('Type')
        type_lbl.setStyleSheet(f'color: {theme.TEXT_MUTED}; font-size: 12px; min-width: 52px;')
        type_combo = QComboBox()
        type_combo.addItems(MACRO_TYPES)
        type_row.addWidget(type_lbl)
        type_row.addWidget(type_combo, 1)

        action_container = QWidget()
        action_container.setStyleSheet('background: transparent;')
        action_inner = QHBoxLayout(action_container)
        action_inner.setContentsMargins(0, 0, 0, 0)
        action_lbl = QLabel('Action')
        action_lbl.setStyleSheet(f'color: {theme.TEXT_MUTED}; font-size: 12px; min-width: 52px;')
        action_combo = QComboBox()
        action_combo.setEditable(False)
        action_combo.addItems(MACRO_ACTIONS['Keyboard Key'])
        action_inner.addWidget(action_lbl)
        action_inner.addWidget(action_combo, 1)

        from PyQt5.QtWidgets import QLineEdit
        text_input = QLineEdit()
        text_input.setPlaceholderText('Text to type...')
        text_input.setVisible(False)
        text_input.setStyleSheet(f'''
            QLineEdit {{
                background: {theme.BG_ELEVATED}; border: 1px solid {theme.BORDER_LIGHT};
                border-radius: 8px; color: {theme.TEXT}; padding: 6px 10px;
            }}
            QLineEdit:focus {{ border-color: {theme.ACCENT}; }}
        ''')

        recorder = KeyRecorderWidget()
        recorder.setVisible(False)

        def _on_type_changed(t, ac=action_combo, aw=action_container,
                             rw=recorder, tw=text_input):
            aw.setVisible(t not in ('Recorded', 'Type Text'))
            rw.setVisible(t == 'Recorded')
            tw.setVisible(t == 'Type Text')

        type_combo.currentTextChanged.connect(
            lambda t, ac=action_combo: self._refresh_actions(t, ac)
        )
        type_combo.currentTextChanged.connect(_on_type_changed)
        type_combo.currentTextChanged.connect(
            lambda _: self._unmark_cleared(prefix)
        )
        action_combo.currentTextChanged.connect(
            lambda _: self._unmark_cleared(prefix)
        )
        text_input.textChanged.connect(
            lambda _: self._unmark_cleared(prefix)
        )

        layout.addLayout(type_row)
        layout.addWidget(action_container)
        layout.addWidget(text_input)
        layout.addWidget(recorder)
        parent_layout.addWidget(frame)

        return type_combo, action_combo, recorder, text_input

    def _refresh_actions(self, action_type, combo):
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(MACRO_ACTIONS.get(action_type, []))
        combo.blockSignals(False)

    def _unmark_cleared(self, prefix):
        if prefix == 'press':
            self._press_cleared = False
        else:
            self._hold_cleared = False

    def _clear(self, prefix):
        if prefix == 'press':
            self._press_cleared = True
            self._press_type.blockSignals(True)
            self._press_action.blockSignals(True)
            self._press_type.setCurrentIndex(0)
            self._press_action.setCurrentIndex(0)
            self._press_type.blockSignals(False)
            self._press_action.blockSignals(False)
            self._press_recorder.clear()
        else:
            self._hold_cleared = True
            self._hold_type.blockSignals(True)
            self._hold_action.blockSignals(True)
            self._hold_type.setCurrentIndex(0)
            self._hold_action.setCurrentIndex(0)
            self._hold_type.blockSignals(False)
            self._hold_action.blockSignals(False)
            self._hold_recorder.clear()

    def _populate(self, press_data, hold_data):
        for data, type_combo, action_combo, recorder, text_input in [
            (press_data, self._press_type, self._press_action, self._press_recorder, self._press_text),
            (hold_data, self._hold_type, self._hold_action, self._hold_recorder, self._hold_text),
        ]:
            if not data:
                continue
            t = data.get('type', 'Keyboard Key')
            if t in MACRO_TYPES:
                type_combo.setCurrentText(t)
            if t == 'Recorded':
                recorder.set_recorded_json(data.get('action', ''))
            elif t == 'Type Text':
                text_input.setText(data.get('action', ''))
            else:
                self._refresh_actions(t, action_combo)
                a = data.get('action', '')
                if a in [action_combo.itemText(i) for i in range(action_combo.count())]:
                    action_combo.setCurrentText(a)

    def _on_save(self):
        if self._press_cleared:
            self._press_result = None
        else:
            press_type = self._press_type.currentText()
            if press_type == 'Recorded':
                j = self._press_recorder.get_recorded_json()
                self._press_result = {'type': press_type, 'action': j} if j else None
            elif press_type == 'Type Text':
                t = self._press_text.text()
                self._press_result = {'type': press_type, 'action': t} if t else None
            else:
                self._press_result = {'type': press_type, 'action': self._press_action.currentText()}

        if self._hold_cleared:
            self._hold_result = None
        else:
            hold_type = self._hold_type.currentText()
            if hold_type == 'Recorded':
                j = self._hold_recorder.get_recorded_json()
                self._hold_result = {'type': hold_type, 'action': j} if j else None
            elif hold_type == 'Type Text':
                t = self._hold_text.text()
                self._hold_result = {'type': hold_type, 'action': t} if t else None
            else:
                self._hold_result = {'type': hold_type, 'action': self._hold_action.currentText()}

        self.accept()

    def closeEvent(self, event):
        self._press_recorder.stop_if_recording()
        self._hold_recorder.stop_if_recording()
        super().closeEvent(event)

    def get_results(self):
        return self._press_result, self._hold_result


class EncoderCard(QFrame):
    color_command = pyqtSignal(str)
    app_refresh_requested = pyqtSignal(int)
    button_macro_requested = pyqtSignal(int)
    app_changed = pyqtSignal(int, str)          # encoder_id, app_name

    _BTN_LABELS = ['A', 'B', 'C', 'D']

    def __init__(self, encoder_id, parent=None):
        super().__init__(parent)
        self.encoder_id = encoder_id           # 0-indexed, matches Arduino E:0..E:3
        self._r, self._g, self._b = 6, 182, 212      # begin / solid colour
        self._r2, self._g2, self._b2 = 255, 100, 0  # fade end colour
        self._blend_start = 0
        self._mode = 'default'
        self._percentage = 50
        self._selected_app = ''
        self._btn_press_data = None
        self._btn_hold_data = None

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumWidth(260)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName(f'encoder_card_{encoder_id}')
        self.setStyleSheet(f'''
            #encoder_card_{encoder_id} {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER};
                border-top: 1px solid {theme.BORDER_LIGHT};
                border-radius: 14px;
            }}
            #encoder_card_{encoder_id} QLabel {{
                background: transparent;
                color: {theme.TEXT};
            }}
            #encoder_card_{encoder_id} QComboBox {{
                background-color: {theme.BG_ELEVATED};
                border: 1px solid {theme.BORDER_LIGHT};
                border-radius: 8px;
                color: {theme.TEXT};
                padding: 5px 30px 5px 10px;
            }}
            #encoder_card_{encoder_id} QComboBox:hover {{
                border-color: {theme.ACCENT};
            }}
            #encoder_card_{encoder_id} QComboBox QAbstractItemView {{
                background-color: {theme.BG_CARD};
                border: 1px solid {theme.BORDER_LIGHT};
                color: {theme.TEXT};
                selection-background-color: {theme.ACCENT};
                selection-color: #000;
            }}
        ''')
        self._build_ui()
        self._color_row.setVisible(self._mode != 'default')
        self._arrow_lbl.setVisible(self._mode == 'fade')
        self._color2_btn.setVisible(self._mode == 'fade')

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        # Header: encoder + button badges only
        header_row = QHBoxLayout()
        enc_badge = QLabel(f'ENC {self.encoder_id + 1}')
        enc_badge.setStyleSheet(f'''
            background: {theme.ACCENT}18; color: {theme.ACCENT};
            border: 1px solid {theme.ACCENT}40; border-radius: 5px;
            font-size: 10px; font-weight: 700; padding: 2px 7px; letter-spacing: 0.5px;
        ''')
        btn_lbl_char = ['A', 'B', 'C', 'D'][self.encoder_id]
        btn_badge = QLabel(f'BTN {btn_lbl_char}')
        btn_badge.setStyleSheet(f'''
            background: {theme.BG_ELEVATED}; color: {theme.TEXT_DIM};
            border: 1px solid {theme.BORDER_LIGHT}; border-radius: 5px;
            font-size: 10px; font-weight: 600; padding: 2px 7px; letter-spacing: 0.5px;
        ''')
        header_row.addWidget(enc_badge)
        header_row.addSpacing(6)
        header_row.addWidget(btn_badge)
        header_row.addStretch()
        layout.addLayout(header_row)

        # LED strip preview + volume %
        led_row = QHBoxLayout()
        self._led = LEDPreview()
        self._led.set_state(self._r, self._g, self._b, self._mode, self._percentage)
        self._pct_lbl = QLabel('-- %')
        self._pct_lbl.setFixedWidth(36)
        self._pct_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._pct_lbl.setStyleSheet(f'font-size: 11px; color: {theme.ACCENT}; font-weight: 600;')
        led_row.addWidget(self._led, 1)
        led_row.addWidget(self._pct_lbl)
        layout.addLayout(led_row)

        # Mode selector
        mode_row = QHBoxLayout()
        mode_lbl = QLabel('Mode')
        mode_lbl.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_MUTED}; min-width: 60px;')
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(['Default', 'Fade', 'Solid'])
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_row.addWidget(mode_lbl)
        mode_row.addWidget(self._mode_combo, 1)
        layout.addLayout(mode_row)

        # Colour row — start and end buttons side by side in one row
        self._color_row = QWidget()
        self._color_row.setStyleSheet('background: transparent;')
        color_inner = QHBoxLayout(self._color_row)
        color_inner.setContentsMargins(0, 0, 0, 0)
        color_inner.setSpacing(8)

        color_lbl = QLabel('Color')
        color_lbl.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_MUTED};')
        color_lbl.setFixedWidth(50)

        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(68, 26)
        self._color_btn.setToolTip('Start color')
        self._color_btn.clicked.connect(self._pick_color)
        self._refresh_color_btn()

        self._arrow_lbl = QLabel('→')
        self._arrow_lbl.setStyleSheet(f'color: {theme.TEXT_DIM}; font-size: 14px;')
        self._arrow_lbl.setVisible(False)

        self._color2_btn = QPushButton()
        self._color2_btn.setFixedSize(68, 26)
        self._color2_btn.setToolTip('End color')
        self._color2_btn.clicked.connect(self._pick_end_color)
        self._color2_btn.setVisible(False)
        self._refresh_color2_btn()

        color_inner.addWidget(color_lbl)
        color_inner.addWidget(self._color_btn)
        color_inner.addWidget(self._arrow_lbl)
        color_inner.addWidget(self._color2_btn)
        color_inner.addStretch()
        layout.addWidget(self._color_row)

        # Fade-only extras: blend slider only
        self._fade_widget = QWidget()
        self._fade_widget.setStyleSheet('background: transparent;')
        self._fade_widget.setVisible(False)
        fade_inner = QVBoxLayout(self._fade_widget)
        fade_inner.setContentsMargins(0, 0, 0, 0)
        fade_inner.setSpacing(6)

        # Blend start slider
        blend_row = QHBoxLayout()
        blend_lbl = QLabel('Blend from')
        blend_lbl.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_MUTED}; min-width: 60px;')
        self._blend_slider = QSlider(Qt.Horizontal)
        self._blend_slider.setRange(0, 90)
        self._blend_slider.setValue(0)
        self._blend_slider.setStyleSheet(f'''
            QSlider::groove:horizontal {{ background: {theme.BG_ELEVATED}; height: 4px; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {theme.ACCENT}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}
            QSlider::sub-page:horizontal {{ background: {theme.ACCENT}; border-radius: 2px; }}
        ''')
        self._blend_val_lbl = QLabel('0%')
        self._blend_val_lbl.setFixedWidth(32)
        self._blend_val_lbl.setStyleSheet(f'font-size: 11px; color: {theme.ACCENT};')
        self._blend_debounce = QTimer(self)
        self._blend_debounce.setSingleShot(True)
        self._blend_debounce.timeout.connect(self._emit_blend)
        self._blend_slider.valueChanged.connect(self._on_blend_changed)
        blend_row.addWidget(blend_lbl)
        blend_row.addWidget(self._blend_slider, 1)
        blend_row.addWidget(self._blend_val_lbl)
        fade_inner.addLayout(blend_row)
        layout.addWidget(self._fade_widget)

        # Idle animation
        idle_row = QHBoxLayout()
        idle_lbl = QLabel('Idle')
        idle_lbl.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_MUTED}; min-width: 60px;')
        self._idle_combo = QComboBox()
        self._idle_combo.addItems(['Off', 'Breathe', 'Wave', 'Rainbow', 'Chase', 'Color Cycle', 'Sparkle'])
        self._idle_combo.currentTextChanged.connect(self._on_idle_changed)
        idle_row.addWidget(idle_lbl)
        idle_row.addWidget(self._idle_combo, 1)
        layout.addLayout(idle_row)

        # Volume app selector — always visible
        app_row = QHBoxLayout()
        app_lbl = QLabel('App')
        app_lbl.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_MUTED}; min-width: 60px;')
        self._app_combo = QComboBox()
        self._app_combo.setPlaceholderText('Select app...')
        self._app_combo.currentTextChanged.connect(self._on_app_changed)
        refresh_btn = QPushButton('↻')
        refresh_btn.setFixedSize(30, 30)
        refresh_btn.setToolTip('Refresh audio apps')
        refresh_btn.setStyleSheet(f'''
            QPushButton {{
                background: {theme.BG_ELEVATED}; border: 1px solid {theme.BORDER_LIGHT};
                border-radius: 8px; color: {theme.TEXT_MUTED}; font-size: 15px; padding: 0;
            }}
            QPushButton:hover {{ border-color: {theme.ACCENT}; color: {theme.ACCENT}; }}
        ''')
        refresh_btn.clicked.connect(lambda: self.app_refresh_requested.emit(self.encoder_id))
        app_row.addWidget(app_lbl)
        app_row.addWidget(self._app_combo, 1)
        app_row.addWidget(refresh_btn)
        layout.addLayout(app_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f'background: {theme.BORDER}; border: none;')
        layout.addWidget(sep)

        # Encoder button macro row
        btn_label = self._BTN_LABELS[self.encoder_id]
        btn_row = QHBoxLayout()

        btn_lbl = QLabel(f'Button {btn_label}')
        btn_lbl.setStyleSheet(f'font-size: 12px; color: {theme.TEXT_MUTED}; min-width: 62px;')

        self._btn_macro_lbl = QLabel('—')
        self._btn_macro_lbl.setStyleSheet(f'font-size: 11px; color: {theme.TEXT_DIM};')

        assign_btn = QPushButton('Assign')
        assign_btn.setFixedSize(60, 28)
        assign_btn.setStyleSheet(f'''
            QPushButton {{
                background: {theme.BG_ELEVATED}; border: 1px solid {theme.BORDER_LIGHT};
                border-radius: 7px; color: {theme.TEXT_MUTED}; font-size: 11px; padding: 0;
            }}
            QPushButton:hover {{ border-color: {theme.ACCENT}; color: {theme.ACCENT}; background: {theme.BG_HOVER}; }}
        ''')
        assign_btn.clicked.connect(lambda: self.button_macro_requested.emit(self.encoder_id))

        btn_row.addWidget(btn_lbl)
        btn_row.addWidget(self._btn_macro_lbl, 1)
        btn_row.addWidget(assign_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

    def _pick_color(self):
        color = QColorDialog.getColor(
            QColor(self._r, self._g, self._b), self,
            f'Encoder {self.encoder_id + 1} — Begin colour'
        )
        if color.isValid():
            self._r, self._g, self._b = color.red(), color.green(), color.blue()
            self._refresh_color_btn()
            self._update_led_preview()
            self._emit_color_cmd()

    def _pick_end_color(self):
        color = QColorDialog.getColor(
            QColor(self._r2, self._g2, self._b2), self,
            f'Encoder {self.encoder_id + 1} — End colour'
        )
        if color.isValid():
            self._r2, self._g2, self._b2 = color.red(), color.green(), color.blue()
            self._refresh_color2_btn()
            self._update_led_preview()
            self._emit_color_cmd()

    def _on_blend_changed(self, val):
        self._blend_start = val
        self._blend_val_lbl.setText(f'{val}%')
        self._update_led_preview()          # preview updates live
        self._blend_debounce.start(150)     # serial command waits until slider stops

    def _emit_blend(self):
        self._emit_color_cmd()

    def _refresh_color_btn(self):
        self._color_btn.setStyleSheet(f'''
            QPushButton {{
                background-color: rgb({self._r},{self._g},{self._b});
                border: 2px solid {theme.BORDER_LIGHT};
                border-radius: 7px;
            }}
            QPushButton:hover {{ border-color: {theme.ACCENT}; }}
        ''')

    def _refresh_color2_btn(self):
        self._color2_btn.setStyleSheet(f'''
            QPushButton {{
                background-color: rgb({self._r2},{self._g2},{self._b2});
                border: 2px solid {theme.BORDER_LIGHT};
                border-radius: 7px;
            }}
            QPushButton:hover {{ border-color: {theme.ACCENT}; }}
        ''')

    def _on_mode_changed(self, mode_text):
        self._mode = mode_text.lower()
        is_default = self._mode == 'default'
        is_fade = self._mode == 'fade'
        self._color_row.setVisible(not is_default)
        self._arrow_lbl.setVisible(is_fade)
        self._color2_btn.setVisible(is_fade)
        self._fade_widget.setVisible(is_fade)
        if is_default:
            self._r, self._g, self._b = 0, 200, 0    # green
            self._r2, self._g2, self._b2 = 200, 0, 0  # red
            self._blend_start = 0
        self._update_led_preview()
        self._emit_color_cmd()

    def _update_led_preview(self):
        if self._mode == 'fade':
            self._led.set_state(self._r, self._g, self._b, 'fade', self._percentage,
                                self._r2, self._g2, self._b2, self._blend_start)
        else:
            self._led.set_state(self._r, self._g, self._b, self._mode, self._percentage)

    def _emit_color_cmd(self):
        self.color_command.emit(self.get_color_command())

    def _on_app_changed(self, app_name):
        self._selected_app = app_name
        self.app_changed.emit(self.encoder_id, app_name)

    def populate_apps(self, apps, restore=None):
        self._app_combo.blockSignals(True)
        self._app_combo.clear()
        self._app_combo.addItems(apps)
        if restore and restore in apps:
            self._app_combo.setCurrentText(restore)
        elif self._selected_app and self._selected_app in apps:
            self._app_combo.setCurrentText(self._selected_app)
        self._app_combo.blockSignals(False)

    def get_selected_app(self):
        return self._app_combo.currentText()

    _EFFECT_MAP = {'Off': 0, 'Breathe': 1, 'Wave': 2, 'Rainbow': 3,
                   'Chase': 4, 'Color Cycle': 5, 'Sparkle': 6}

    def _on_idle_changed(self, mode):
        n = self.encoder_id + 1
        val = self._EFFECT_MAP.get(mode, 0)
        self.color_command.emit(f'EFFECT:{n}:{val}')

    def set_percentage(self, pct):
        self._percentage = pct
        self._pct_lbl.setText(f'{pct}%' if pct >= 0 else '-- %')
        self._update_led_preview()

    def set_button_macros(self, press_data, hold_data):
        self._btn_press_data = press_data
        self._btn_hold_data = hold_data
        if press_data:
            if press_data.get('type') == 'Recorded':
                display = '[recorded]'
            else:
                action = press_data.get('action', '—')
                display = action if len(action) <= 16 else action[:14] + '..'
            if hold_data:
                display += f'  /  hold: {hold_data.get("action", "")}'
            self._btn_macro_lbl.setText(display)
            self._btn_macro_lbl.setStyleSheet(f'font-size: 11px; color: {theme.ACCENT};')
        else:
            self._btn_macro_lbl.setText('—')
            self._btn_macro_lbl.setStyleSheet(f'font-size: 11px; color: {theme.TEXT_DIM};')

    def get_button_macro_press(self):
        return self._btn_press_data

    def get_button_macro_hold(self):
        return self._btn_hold_data

    def get_color(self):
        return (self._r, self._g, self._b)

    def get_mode(self):
        return self._mode

    def get_state(self):
        return {
            'app': self._selected_app,
            'mode': self._mode,
            'color': [self._r, self._g, self._b],
            'color2': [self._r2, self._g2, self._b2],
            'blend_start': self._blend_start,
            'effect': self._idle_combo.currentText(),
        }

    def restore_state(self, state):
        if not state:
            return
        self._mode = state.get('mode', 'default')
        c = state.get('color', [6, 182, 212])
        self._r, self._g, self._b = c[0], c[1], c[2]
        c2 = state.get('color2', [255, 100, 0])
        self._r2, self._g2, self._b2 = c2[0], c2[1], c2[2]
        self._blend_start = state.get('blend_start', 0)
        self._selected_app = state.get('app', '')

        self._mode_combo.blockSignals(True)
        self._mode_combo.setCurrentText(self._mode.capitalize())
        self._mode_combo.blockSignals(False)

        is_default = self._mode == 'default'
        is_fade = self._mode == 'fade'
        self._color_row.setVisible(not is_default)
        self._arrow_lbl.setVisible(is_fade)
        self._color2_btn.setVisible(is_fade)
        self._fade_widget.setVisible(is_fade)

        self._refresh_color_btn()
        self._refresh_color2_btn()

        self._blend_slider.blockSignals(True)
        self._blend_slider.setValue(self._blend_start)
        self._blend_val_lbl.setText(f'{self._blend_start}%')
        self._blend_slider.blockSignals(False)

        self._update_led_preview()
        self._emit_color_cmd()

        # support old 'breathe' bool key as well as new 'effect' string
        effect = state.get('effect') or ('Breathe' if state.get('breathe') else 'Off')
        self._idle_combo.blockSignals(True)
        self._idle_combo.setCurrentText(effect)
        self._idle_combo.blockSignals(False)
        self._on_idle_changed(effect)   # push EFFECT command to Arduino

        self._app_combo.blockSignals(True)
        idx = self._app_combo.findText(self._selected_app)
        if idx >= 0:
            self._app_combo.setCurrentIndex(idx)
        self._app_combo.blockSignals(False)

    def get_color_command(self):
        """Returns the full Arduino colour command for this strip (1-indexed)."""
        n = self.encoder_id + 1
        if self._mode == 'default':
            # Fixed green→red gradient, no custom colours
            return f'{n}:colorfade(0,200,0,200,0,0,0)'
        elif self._mode == 'fade':
            return (f'{n}:colorfade({self._r},{self._g},{self._b},'
                    f'{self._r2},{self._g2},{self._b2},{self._blend_start})')
        else:  # solid
            return f'{n}:color({self._r},{self._g},{self._b})'
