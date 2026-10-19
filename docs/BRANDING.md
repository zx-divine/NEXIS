# Official NEXIS branding

The canonical artwork is `assets/branding/NEXIS_logo.png`. Its SHA-256 is
`f778b2f53df2636d33739b97b0f7c7584ed27dccd662f03f7696cac909261c09`.
The source PNG is unchanged. No cropping, recolouring or background removal was applied.

`scripts/prepare_branding.py` generates `assets/branding/NEXIS.ico` with square
16, 24, 32, 48, 64, 128 and 256 pixel frames, then copies both assets into the
Python package. Pillow is needed only for this build step. The runtime uses Qt.

The original PNG appears in the startup splash, About page and first-run welcome
wizard. The wizard explains the existing local functionality and saves history
and reduced-motion preferences only when Finish is selected. Cancelling leaves
preferences unchanged. Its completion flag is an additive SQLite setting; existing
data is preserved. The current version remains 1.1.0; this branding task does not
claim implementation of the separate v1.3 AI/provider roadmap.

## Packaged assets and identity

`nexis.branding.asset()` resolves resources relative to its module, never the
working directory or an absolute developer path. PyInstaller puts the original
PNG and ICO under `_internal/nexis/assets/branding`; setuptools includes identical
package data in wheels. Copy the entire `dist/NEXIS` folder for portable use.

The executable embeds the ICO. QApplication and MainWindow load the same ICO for
native title-bar and taskbar icons. Before creating QApplication, startup sets
the stable Windows AppUserModelID `NEXIS.Desktop`. Inno Setup uses that exact value
on both shortcuts. Keep it stable across versions and install locations.

`installer/NEXIS.iss` creates a per-user installation, a Start Menu shortcut and an
optional desktop shortcut. Both refer to the installed executable's icon resource;
the installer and uninstaller use the same branding. No administrator rights,
automatic startup registration or taskbar pin changes are requested.

## Rebuild

With project development dependencies installed:

```text
python scripts/prepare_branding.py
python -m PyInstaller --noconfirm NEXIS.spec
ISCC.exe installer\NEXIS.iss
python scripts/check_package.py
python scripts/check_windows_branding.py
```

For the workspace runtime, `scripts/dev.py build` invokes PyInstaller with
`.dev-deps` available. `scripts/build.py` runs asset preparation, tests, lint and
PyInstaller in an ordinary installed development environment. Inno Setup compilation
is explicit and separate. Keep prior builds outside `dist/NEXIS` if Windows ACLs
prevent PyInstaller from cleaning its previous output.

## Verification

Local build and installation completed on 2026-10-16:

- Executable: `dist/NEXIS/NEXIS.exe`; 213 distribution files, 120.33 MiB total.
- Installer: `dist/installer/NEXIS-Desktop-1.1.0.0-Setup.exe`; 39,289,189 bytes.
- Installed per-user under `%LOCALAPPDATA%/Programs/NEXIS Desktop`, with actual Start Menu and desktop shortcuts. Neither shortcut nor destination existed before this test.
- Installed executable hash matches the built executable. Native installed smoke passed all 11 pages, splash/About/welcome logo loading, process identity and both small/large WM_GETICON checks from `C:/Windows/Temp`.
- Actual shortcut targets, icon locations and AppUserModelIDs match the installed application. Windows shell icon extraction succeeded for both shortcuts, executable and installer. Extracted images were inspected.
- Wheel build includes PNG and ICO bytes identical to the canonical assets.
- Detailed evidence: `branding-windows/verification.json`, `branding-windows/shortcuts.json`, `branding-windows/shell-icons.json`, `branding-installed-native/packaged-smoke.json`, and `package-smoke-v1.1.0/package-verification.json`.

The compiler was obtained from the official Inno Setup 6.7.3 GitHub release after
announcing the download and installation. Its SHA-256 matched the official release
asset digest: `9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732`.
It is installed under `.tools/InnoSetup`. No source was pushed or release published.

Automated tests cover all seven ICO directory entries, PNG preservation, resource
resolution after changing working directory, Qt image loading, actual Windows
process identity, and welcome Finish/Cancel persistence. The full suite passed:
114 passed, 1 skipped (Windows symlink-creation privilege).

`scripts/check_package.py` checks the frozen executable's PE icon-group sizes,
version, bundled PNG hash and path, loaded splash/About/welcome assets and process
AppUserModelID with Python removed from PATH. Native Windows smoke output additionally
records actual WM_GETICON handles and extracted native window icons.

`scripts/check_windows_branding.py` asks Windows SHGetFileInfo for the executable
and shortcut icons and saves the images under `docs/branding-windows`. The shell
may add its own overlays, such as NTFS compression arrows; the artwork is unchanged.
`scripts/read_shortcut.js` reads existing shortcut targets, icon locations and
AppUserModelID without saving or modifying them.

On-screen taskbar grouping and Start Menu/Explorer presentation are separate visual
checks; programmatic icon and shortcut checks do not demonstrate every Windows
shell cache state, DPI configuration, or previously pinned shortcut. No icon caches
are deleted, Explorer is not restarted, and old user pins are not modified.

Implementation references: [Microsoft process AppUserModelID](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-setcurrentprocessexplicitappusermodelid),
[Inno shortcut properties](https://jrsoftware.org/ishelp/topic_iconssection.htm),
[Inno executable icon](https://jrsoftware.org/ishelp/topic_setup_setupiconfile.htm).
