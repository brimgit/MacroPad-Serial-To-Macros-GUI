// MacroPad SignalRGB Plugin
//
// Installation:
//   Copy this file to:
//   %USERPROFILE%\AppData\Local\WhirlwindFX\SignalRGB\Plugins\MacroPad.js
//   Then RESTART SignalRGB.
//
// Requirements:
//   - MacroPad app must be running (starts the RGB server on 127.0.0.1:7237 automatically)
//   - Enable "RGB Passthrough" on each encoder you want SignalRGB to control
//
// LED layout — 40 LEDs total, 4 rows of 10:
//   Row 0 (y=0): Encoder 1, LEDs  0–9
//   Row 1 (y=1): Encoder 2, LEDs 10–19
//   Row 2 (y=2): Encoder 3, LEDs 20–29
//   Row 3 (y=3): Encoder 4, LEDs 30–39

export function Name()            { return "MacroPad"; }
export function Version()         { return "1.1.0"; }
export function Type()            { return "network"; }
export function Publisher()       { return "Brim"; }
export function Size()            { return [10, 4]; }
export function DefaultPosition() { return [0, 0]; }
export function DefaultScale()    { return 8.0; }
export function SubdeviceController() { return true; }
export function DefaultComponentBrand() { return "MacroPad"; }

/* global
controller:readonly
LightingMode:readonly
forcedColor:readonly
*/

export function ControllableParameters() {
	return [
		{ property: "LightingMode", group: "settings", label: "Lighting Mode",
		  type: "combobox", values: ["Canvas", "Forced"], default: "Canvas" },
		{ property: "forcedColor", group: "settings", label: "Forced Color",
		  min: "0", max: "360", type: "color", default: "#009bde" },
	];
}

// ── LED metadata ──────────────────────────────────────────────────────────────
const ENC_COUNT = 4;
const LEDS_PER_ENC = 10;
const LED_COUNT = ENC_COUNT * LEDS_PER_ENC;
const CHANNEL = "Encoders";

export function LedNames() {
	const names = [];
	for (let enc = 1; enc <= ENC_COUNT; enc++)
		for (let led = 1; led <= LEDS_PER_ENC; led++)
			names.push(`Enc${enc} LED${led}`);
	return names;
}

export function LedPositions() {
	const pos = [];
	for (let enc = 0; enc < ENC_COUNT; enc++)
		for (let led = 0; led < LEDS_PER_ENC; led++)
			pos.push([led, enc]);
	return pos;
}

// ── Discovery ─────────────────────────────────────────────────────────────────
class MacroPadController {
	constructor() {
		this.id       = "macropad-localhost-7237";
		this.name     = "MacroPad";
		this.ip       = "127.0.0.1";
		this.port     = 7237;
	}
}

export function DiscoveryService() {
	this.IconUrl = "";

	this.Initialize = function() {
		// Check if MacroPad app is already registered
		const existing = service.getController("macropad-localhost-7237");
		if (existing) return;

		// Verify the MacroPad RGB server is running before registering
		const xhr = new XMLHttpRequest();
		xhr.open("GET", "http://127.0.0.1:7237/status", false);
		try {
			xhr.send();
			if (xhr.status === 200) {
				service.log("MacroPad: app found, registering device");
				const ctrl = new MacroPadController();
				service.addController(ctrl);
				service.announceController(ctrl);
			} else {
				service.log("MacroPad: app responded with status " + xhr.status);
			}
		} catch (e) {
			service.log("MacroPad: app not running (start MacroPad first)");
		}
	};

	this.Update = function() {};
	this.Discovered = function() {};
}

// ── Device lifecycle ──────────────────────────────────────────────────────────
export function Initialize() {
	device.setName(controller.name || "MacroPad");
	device.addChannel(CHANNEL, LED_COUNT);
}

export function Shutdown() {}

// ── Render ────────────────────────────────────────────────────────────────────
// Capped at 20 fps (50 ms min interval) to avoid overwhelming the serial link.
// Keepalive fires every 3 s when colors are static so the watchdog stays alive.

const MIN_FRAME_MS = 50;

let _lastHash = "";
let _lastSent = 0;

export function Render() {
	const now = Date.now();
	const ch  = device.channel(CHANNEL);
	if (!ch) return;

	const raw = ch.getColors("Inline");
	if (!raw || raw.length < LED_COUNT * 3) return;

	const isKeepalive = now - _lastSent >= 3000;
	if (!isKeepalive && now - _lastSent < MIN_FRAME_MS) return;

	const hash = raw.slice(0, LED_COUNT * 3).join(",");
	if (hash === _lastHash && !isKeepalive) return;
	_lastHash = hash;
	_lastSent = now;

	const leds = [];
	for (let i = 0; i < LED_COUNT; i++)
		leds.push([raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2]]);

	const xhr = new XMLHttpRequest();
	xhr.open("POST", `http://${controller.ip}:${controller.port}/rgb`, true);
	xhr.setRequestHeader("Content-Type", "application/json");
	xhr.send(JSON.stringify({ leds }));
}
