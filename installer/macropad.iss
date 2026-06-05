; MacroPad Inno Setup Script
; AppVersion is injected at build time by build.py:
;   ISCC.exe /DAppVersion=1.2.0 installer\macropad.iss

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

#define AppName      "MacroPad"
#define AppPublisher "Brim"
#define AppURL       "https://github.com/brimgit/MacroPad-Serial-To-Macros-GUI"
#define AppExeName   "MacroPad.exe"
#define BuildDir     "..\dist_build\MacroPad"

; Detect whether the CP210x INF package was downloaded
#define HasCP210x  FileExists(SourcePath + "drivers\cp210x\silabser.inf")

[Setup]
AppId={{A3F7B2D1-4E8C-4A2F-9B6D-1234567890EF}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=..\dist_build
OutputBaseFilename=MacroPad_Setup_v{#AppVersion}
SetupIconFile=..\Assets\Images\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startuprun";  Description: "Start MacroPad automatically at login"; GroupDescription: "Startup:"; Flags: unchecked
; CH340 installed via winget (ships with Windows 10 1809+ and Windows 11)
Name: "drv_ch340";   Description: "CH340/CH341  (most cheap and clone ESP32 boards)"; GroupDescription: "USB Serial Driver:"; Flags: unchecked
#if HasCP210x
Name: "drv_cp210x";  Description: "CP2102/CP210x  (official Espressif and branded boards)"; GroupDescription: "USB Serial Driver:"; Flags: unchecked
#endif

[Files]
; Main app bundle
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#if HasCP210x
; CP210x — INF driver package, installed via pnputil
Source: "drivers\cp210x\*"; DestDir: "{tmp}\cp210x"; Flags: ignoreversion recursesubdirs dontcopy
#endif

[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}";   Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#AppName}"; \
  ValueData: """{app}\{#AppExeName}"""; \
  Flags: uninsdeletevalue; Tasks: startuprun

[Run]
; CH340 via winget (no file to bundle — winget fetches from WCH)
Filename: "{cmd}"; \
  Parameters: "/c winget install --id WCHSoftGroup.CH341SER --silent --accept-package-agreements --accept-source-agreements"; \
  Tasks: drv_ch340; Flags: waituntilterminated runascurrentuser; \
  StatusMsg: "Installing CH340 USB driver via winget..."
#if HasCP210x
; CP210x via pnputil (built into every Windows 10/11 install)
Filename: "{sysnative}\pnputil.exe"; \
  Parameters: "/add-driver ""{tmp}\cp210x\silabser.inf"" /install"; \
  Tasks: drv_cp210x; Flags: waituntilterminated runascurrentuser; \
  StatusMsg: "Installing CP2102 USB driver..."
#endif
Filename: "{app}\{#AppExeName}"; \
  Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; User data in %APPDATA%\BrimPad is intentionally kept on uninstall
