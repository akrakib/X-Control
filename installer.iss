; Optional: Inno Setup (jrsoftware.org) diye Setup.exe banate chaile build.bat-er pore eta compile korun
[Setup]
AppName=XControl
AppPublisher=akrakib
AppVersion=1.0
DefaultDirName={autopf}\XControl
DefaultGroupName=XControl
OutputBaseFilename=XControl_Setup
OutputDir=dist
SetupIconFile=xcontrol.ico
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\XControl.exe"; DestDir: "{app}"

[Icons]
Name: "{group}\XControl"; Filename: "{app}\XControl.exe"
Name: "{commondesktop}\XControl"; Filename: "{app}\XControl.exe"
