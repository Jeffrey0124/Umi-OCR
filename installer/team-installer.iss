#define MyAppName "Umi-OCR Team"
#define MyAppVersion "2.1.8"
#define MyAppExeName "Umi-OCR.exe"

[Setup]
AppId={{BD035C23-75A7-4062-9C82-E176CEBE847F}
AppName={#MyAppName}
AppVersion=2.1.8
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Umi-OCR Team
DefaultDirName={localappdata}\Programs\Umi-OCR-Team
DefaultGroupName=Umi-OCR Team
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir=..\dist
OutputBaseFilename=Umi-OCR-Team-Setup_2.1.8
SetupIconFile=..\UmiOCR-data\qt_res\images\icons\umiocr.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=2.1.8.0
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Files]
Source: "..\Umi-OCR.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\UmiOCR-data\*"; DestDir: "{app}\UmiOCR-data"; Excludes: ".settings,.pre_settings,logs\*,temp_doc\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "generated\team.settings"; DestDir: "{app}\UmiOCR-data"; DestName: ".settings"; Flags: ignoreversion onlyifdoesntexist

[Icons]
Name: "{group}\Umi-OCR Team"; Filename: "{app}\Umi-OCR.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Umi-OCR Team"; Filename: "{app}\Umi-OCR.exe"; WorkingDir: "{app}"
