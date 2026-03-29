; =============================================================================
; Thoth v3.7.0 – Inno Setup Script
; Self-contained installer: bundles embedded Python with all pip packages
; pre-installed.  No internet downloads at install time.
; =============================================================================
;
; Prerequisites (placed in installer\build\ by build_installer.ps1):
;   build\python\          – Embedded Python with all packages pre-installed
;
; Compile with:  iscc installer\thoth_setup.iss

#define MyAppName      "Thoth"
#define MyAppVersion   "3.7.0"
#define MyAppPublisher "Thoth"
#define MyAppURL       "https://github.com/siddsachar/Thoth"
#define MyAppExeName   "launch_thoth.vbs"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=ThothSetup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\thoth.ico
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; ── App source code ──────────────────────────────────────────────────────────
Source: "..\app_nicegui.py";             DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\agent.py";                 DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\memory.py";                DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\memory_extraction.py";     DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\knowledge_graph.py";       DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\tasks.py";                 DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\models.py";                DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\data_reader.py";            DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\documents.py";             DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\threads.py";               DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\api_keys.py";              DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\voice.py";                 DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\tts.py";                   DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\vision.py";                DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\launcher.py";              DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\notifications.py";         DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\prompts.py";               DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\requirements.txt";         DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\thoth.ico";                DestDir: "{app}\app"; Flags: ignoreversion

; ── Static assets (JS libraries) ──────────────────────────────────────────────
Source: "..\static\*";                 DestDir: "{app}\app\static"; Flags: ignoreversion

; ── Sounds ──────────────────────────────────────────────────────────────────────
Source: "..\sounds\*.wav";              DestDir: "{app}\app\sounds"; Flags: ignoreversion

; ── Channels package ─────────────────────────────────────────────────────────
Source: "..\channels\__init__.py";      DestDir: "{app}\app\channels"; Flags: ignoreversion
Source: "..\channels\config.py";        DestDir: "{app}\app\channels"; Flags: ignoreversion
Source: "..\channels\telegram.py";      DestDir: "{app}\app\channels"; Flags: ignoreversion
Source: "..\channels\email.py";         DestDir: "{app}\app\channels"; Flags: ignoreversion

; ── Tools package ────────────────────────────────────────────────────────────
Source: "..\tools\__init__.py";        DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\base.py";            DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\registry.py";        DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\arxiv_tool.py";      DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\calculator_tool.py"; DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\calendar_tool.py";   DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\chart_tool.py";      DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\conversation_search_tool.py"; DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\documents_tool.py";  DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\duckduckgo_tool.py"; DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\filesystem_tool.py"; DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\gmail_tool.py";      DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\memory_tool.py";     DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\system_info_tool.py"; DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\tracker_tool.py";    DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\task_tool.py";       DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\telegram_tool.py";   DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\url_reader_tool.py"; DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\vision_tool.py";     DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\weather_tool.py";    DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\web_search_tool.py"; DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\wikipedia_tool.py";  DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\wolfram_tool.py";    DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\browser_tool.py";    DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\shell_tool.py";      DestDir: "{app}\app\tools"; Flags: ignoreversion
Source: "..\tools\youtube_tool.py";    DestDir: "{app}\app\tools"; Flags: ignoreversion

; ── Bundled Skills ───────────────────────────────────────────────────────────
Source: "..\bundled_skills\*";         DestDir: "{app}\app\bundled_skills"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\skills.py";                 DestDir: "{app}\app"; Flags: ignoreversion

; ── Embedded Python (with all packages pre-installed) ────────────────────────
Source: "build\python\*";              DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── Launcher scripts ─────────────────────────────────────────────────────────
Source: "launch_thoth.bat";            DestDir: "{app}"; Flags: ignoreversion
Source: "launch_thoth.vbs";            DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";                    Filename: "wscript.exe"; Parameters: """{app}\{#MyAppExeName}"""; IconFilename: "{app}\app\thoth.ico"; Comment: "Launch Thoth"
Name: "{group}\Uninstall {#MyAppName}";           Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";               Filename: "wscript.exe"; Parameters: """{app}\{#MyAppExeName}"""; IconFilename: "{app}\app\thoth.ico"; Tasks: desktopicon

[Run]
; ── Launch app after install (optional) ──────────────────────────────────────
Filename: "wscript.exe"; Parameters: """{app}\{#MyAppExeName}"""; Description: "Launch {#MyAppName}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\app\__pycache__"
Type: filesandordirs; Name: "{app}\app\tools\__pycache__"
Type: filesandordirs; Name: "{app}\app\channels\__pycache__"
