"""Capture native LTspice schematic windows, never simulate or save a schematic.

All generated files and isolated ASC copies live in the explicitly supplied
artifact directory. Existing LTspice windows are recorded and never targeted.
Zoom commands are discovered from the application's actual Win32 menus.
Screenshots are evidence only: this tool does not judge their visual correctness.
"""
from __future__ import annotations

import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'Programs/ADI/LTspice/LTspice.exe'
USER = C.WinDLL('user32', use_last_error=True)
GDI = C.WinDLL('gdi32', use_last_error=True)
CALLBACK = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)


def bind(lib, name, result, *args):
    function = getattr(lib, name)
    function.restype = result
    function.argtypes = args
    return function


bind(USER, 'EnumWindows', W.BOOL, CALLBACK, W.LPARAM)
bind(USER, 'EnumChildWindows', W.BOOL, W.HWND, CALLBACK, W.LPARAM)
bind(USER, 'GetWindowThreadProcessId', W.DWORD, W.HWND, C.POINTER(W.DWORD))
bind(USER, 'GetWindowTextLengthW', C.c_int, W.HWND)
bind(USER, 'GetWindowTextW', C.c_int, W.HWND, W.LPWSTR, C.c_int)
bind(USER, 'GetClassNameW', C.c_int, W.HWND, W.LPWSTR, C.c_int)
bind(USER, 'IsWindowVisible', W.BOOL, W.HWND)
bind(USER, 'IsWindow', W.BOOL, W.HWND)
bind(USER, 'GetMenu', W.HMENU, W.HWND)
bind(USER, 'GetSubMenu', W.HMENU, W.HMENU, C.c_int)
bind(USER, 'GetMenuItemCount', C.c_int, W.HMENU)
bind(USER, 'GetMenuItemID', W.UINT, W.HMENU, C.c_int)
bind(USER, 'GetMenuState', W.UINT, W.HMENU, W.UINT, W.UINT)
bind(USER, 'GetMenuStringW', C.c_int, W.HMENU, W.UINT, W.LPWSTR, C.c_int, W.UINT)
bind(USER, 'SendMessageW', W.LPARAM, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
bind(USER, 'PostMessageW', W.BOOL, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
bind(USER, 'ShowWindow', W.BOOL, W.HWND, C.c_int)
bind(USER, 'SetWindowPos', W.BOOL, W.HWND, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.UINT)
bind(USER, 'GetWindowRect', W.BOOL, W.HWND, C.POINTER(W.RECT))
bind(USER, 'GetSystemMetrics', C.c_int, C.c_int)
bind(USER, 'GetWindowDC', W.HDC, W.HWND)
bind(USER, 'ReleaseDC', C.c_int, W.HWND, W.HDC)
bind(USER, 'PrintWindow', W.BOOL, W.HWND, W.HDC, W.UINT)
bind(GDI, 'CreateCompatibleDC', W.HDC, W.HDC)
bind(GDI, 'CreateCompatibleBitmap', W.HBITMAP, W.HDC, C.c_int, C.c_int)
bind(GDI, 'SelectObject', W.HANDLE, W.HDC, W.HANDLE)
bind(GDI, 'DeleteObject', W.BOOL, W.HANDLE)
bind(GDI, 'DeleteDC', W.BOOL, W.HDC)
bind(GDI, 'GetDIBits', C.c_int, W.HDC, W.HBITMAP, W.UINT, W.UINT, C.c_void_p, C.c_void_p, W.UINT)
try:
    USER.SetProcessDpiAwarenessContext(C.c_void_p(-4))
except AttributeError:
    USER.SetProcessDPIAware()


class BitmapHeader(C.Structure):
    _fields_ = [('size', W.DWORD), ('width', W.LONG), ('height', W.LONG),
                ('planes', W.WORD), ('bits', W.WORD), ('compression', W.DWORD),
                ('image_size', W.DWORD), ('xppm', W.LONG), ('yppm', W.LONG),
                ('colors_used', W.DWORD), ('colors_important', W.DWORD)]


def window_info(handle):
    text = C.create_unicode_buffer(USER.GetWindowTextLengthW(handle) + 1)
    USER.GetWindowTextW(handle, text, len(text))
    kind = C.create_unicode_buffer(256)
    USER.GetClassNameW(handle, kind, len(kind))
    pid = W.DWORD()
    USER.GetWindowThreadProcessId(handle, C.byref(pid))
    rect = W.RECT()
    USER.GetWindowRect(handle, C.byref(rect))
    return dict(hwnd=int(handle), pid=pid.value, title=text.value, class_name=kind.value,
                visible=bool(USER.IsWindowVisible(handle)),
                rect=[rect.left, rect.top, rect.right, rect.bottom])


def windows(parent=None):
    result = []
    @CALLBACK
    def callback(handle, unused):
        result.append(window_info(handle))
        return True
    if parent:
        USER.EnumChildWindows(parent, callback, 0)
    else:
        USER.EnumWindows(callback, 0)
    return result


def menu_items(menu, prefix=''):
    result = []
    if not menu:
        return result
    for index in range(USER.GetMenuItemCount(menu)):
        text = C.create_unicode_buffer(1024)
        USER.GetMenuStringW(menu, index, text, len(text), 0x400)
        label = text.value
        path = prefix + '/' + label
        sub = USER.GetSubMenu(menu, index)
        result.append(dict(path=path, label=label,
                           command_id=USER.GetMenuItemID(menu, index),
                           state=USER.GetMenuState(menu, index, 0x400),
                           submenu=bool(sub)))
        if sub:
            result.extend(menu_items(sub, path))
    return result


def capture_window(handle, path):
    rect = W.RECT()
    USER.GetWindowRect(handle, C.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    source = USER.GetWindowDC(handle)
    memory = GDI.CreateCompatibleDC(source)
    bitmap = GDI.CreateCompatibleBitmap(source, width, height)
    previous = GDI.SelectObject(memory, bitmap)
    try:
        ok = bool(USER.PrintWindow(handle, memory, 2))
        GDI.SelectObject(memory, previous)
        header = BitmapHeader(C.sizeof(BitmapHeader), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        buffer = C.create_string_buffer(width * height * 4)
        rows = GDI.GetDIBits(memory, bitmap, 0, height, buffer, C.byref(header), 0)
        if not ok or rows != height:
            raise RuntimeError(f'PrintWindow={ok}; GetDIBits rows={rows}, expected={height}')
        image = Image.frombuffer('RGB', (width, height), buffer.raw, 'raw', 'BGRX', 0, 1)
        image.save(path)
        return dict(method='Win32 PrintWindow(PW_RENDERFULLCONTENT)', width=width, height=height,
                    print_window_success=ok, dib_rows=rows, rect=[rect.left, rect.top, rect.right, rect.bottom])
    finally:
        GDI.SelectObject(memory, previous)
        GDI.DeleteObject(bitmap)
        GDI.DeleteDC(memory)
        USER.ReleaseDC(handle, source)


def capture_one(source, executable, output, timeout=20):
    before = windows()
    original_handles = {item['hwnd'] for item in before}
    directory = output / source.stem
    directory.mkdir(parents=True, exist_ok=True)
    copied = directory / source.name
    shutil.copy2(source, copied)
    metadata = dict(source=str(source.resolve()), inspection_copy=str(copied.resolve()),
                    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    visual_acceptance='not_evaluated', clipping='not_visually_evaluated',
                    preexisting_ltspice_windows=[w for w in before if 'ltspice' in (w['title'] + w['class_name']).lower()])
    process = subprocess.Popen([str(executable), str(copied)], cwd=directory)
    metadata['launched_pid'] = process.pid
    owned = None
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            candidates = [w for w in windows() if w['pid'] == process.pid and w['visible'] and w['hwnd'] not in original_handles]
            metadata['observed_process_windows'] = candidates
            owned = next((w for w in candidates if 'ltspice' in (w['title'] + w['class_name']).lower() and w['class_name'] != '#32770'), None)
            if owned:
                break
            if process.poll() is not None:
                raise RuntimeError(f'Launched process exited {process.returncode}; no isolated native window. Existing windows were not targeted.')
            time.sleep(.25)
        if not owned:
            raise TimeoutError('No owned LTspice application window observed within timeout')
        handle = owned['hwnd']
        metadata['owned_window'] = owned
        time.sleep(.7)
        USER.ShowWindow(handle, 9)  # Restore only our inspection window.
        # Rendering size is native pixels, not a resized image. No global settings.
        width, height = 1800, 1050
        USER.SetWindowPos(handle, 0, 20, 20, width, height, 0x14)  # NOZORDER | NOACTIVATE
        time.sleep(.5)
        metadata['child_windows'] = windows(handle)
        items = menu_items(USER.GetMenu(handle))
        metadata['menu'] = items
        zoom = [item for item in items if not item['submenu'] and
                any(term in item['label'].replace('&', '').lower() for term in ('zoom to fit', 'zoom extents', 'zoom to full', 'zoom fit'))]
        if len(zoom) != 1:
            raise RuntimeError(f'Unique enabled native zoom-fit menu command not discovered; candidates={zoom}')
        if zoom[0]['state'] & 3:
            raise RuntimeError(f'Native zoom-fit command disabled: {zoom[0]}')
        metadata['zoom_command'] = zoom[0]
        USER.SendMessageW(handle, 0x111, zoom[0]['command_id'], 0)
        metadata['zoom_fit_command_sent'] = True
        time.sleep(.8)
        screenshot = directory / (source.stem + '_ltspice.png')
        metadata['capture'] = capture_window(handle, screenshot)
        metadata['screenshot'] = str(screenshot.resolve())
        metadata['post_zoom_window'] = window_info(handle)
        metadata['post_zoom_children'] = windows(handle)
        metadata['status'] = 'captured_not_visually_reviewed'
        metadata['pitfalls'] = ['Native zoom-fit command issued; readable values and clipping require independent visual judge.',
                               'Full application frame included; PrintWindow evidence is not a visual correctness check.']
    except Exception as exc:
        metadata['status'] = 'capture_failed'
        metadata['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        # Closing only this new unmodified inspection frame is authorized.
        if owned and USER.IsWindow(owned['hwnd']):
            USER.PostMessageW(owned['hwnd'], 0x10, 0, 0)
            try:
                process.wait(timeout=4)
                metadata['inspection_process_exit_code'] = process.returncode
            except subprocess.TimeoutExpired:
                metadata['close_pitfall'] = 'Owned window did not close promptly; process left intact, never force-terminated.'
        metadata['inspection_copy_sha256_after'] = hashlib.sha256(copied.read_bytes()).hexdigest()
        metadata['inspection_copy_unchanged'] = metadata['inspection_copy_sha256_after'] == metadata['source_sha256']
        (directory / 'capture_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('schematics', nargs='*', type=Path)
    parser.add_argument('--executable', type=Path, default=DEFAULT_EXE)
    parser.add_argument('--artifacts', type=Path, default=ROOT / 'tests/artifacts/phase_7_visual/native')
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    if args.probe:
        data = dict(executable=str(args.executable), executable_exists=args.executable.is_file(),
                    desktop_size=[USER.GetSystemMetrics(0), USER.GetSystemMetrics(1)], windows=windows())
        for item in data['windows']:
            if 'ltspice' in (item['title'] + item['class_name']).lower():
                item['menu'] = menu_items(USER.GetMenu(item['hwnd']))
        print(json.dumps(data, indent=2))
        return
    if not args.schematics:
        parser.error('Supply one or more ASC files')
    output = args.artifacts.resolve()
    output.mkdir(parents=True, exist_ok=True)
    records = [capture_one(path.resolve(strict=True), args.executable.resolve(strict=True), output) for path in args.schematics]
    summary = dict(executable=str(args.executable.resolve()), captures=records,
                   simulations_run=False, schematics_saved=False, existing_windows_targeted=False,
                   visual_acceptance='not_evaluated')
    (output / 'capture_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps([dict(source=r['source'], status=r['status'], screenshot=r.get('screenshot'), error=r.get('error')) for r in records], indent=2))


if __name__ == '__main__':
    main()
