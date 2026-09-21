"""Run an approved Windows verifier in a temporary classic AppContainer.

The package SID receives access only to the disposable worktree, Git metadata
needed by linked worktrees, and the Python/Git executables. No network capability
is granted. All child processes stay in a kill-on-close Windows Job Object.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


class SandboxError(RuntimeError):
    pass


class STARTUPINFO(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
                ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
                ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
                ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
                ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
                ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE),
                ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]


class STARTUPINFOEX(ctypes.Structure):
    _fields_ = [("StartupInfo", STARTUPINFO), ("lpAttributeList", ctypes.c_void_p)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


class SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [("AppContainerSid", ctypes.c_void_p), ("Capabilities", ctypes.c_void_p),
                ("CapabilityCount", wintypes.DWORD), ("Reserved", wintypes.DWORD)]


class BASIC_LIMIT(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD)]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                 "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class EXTENDED_LIMIT(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", BASIC_LIMIT), ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


def _win32_error(label: str) -> SandboxError:
    return SandboxError(f"{label}: Windows error {ctypes.get_last_error()}")


def _acl(path: Path, sid: str, rights: str, *, remove: bool = False) -> None:
    action = ["/remove:g", f"*{sid}"] if remove else ["/grant", f"*{sid}:(OI)(CI)({rights})"]
    result = subprocess.run(["icacls", str(path), *action, "/L"],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        raise SandboxError(f"ACL {'cleanup' if remove else 'grant'} failed on {path}: "
                           f"{(result.stderr or result.stdout).strip()[:300]}")


def _original_dacl(path: Path, advapi: ctypes.WinDLL) -> bytes:
    """Preserve the root DACL before icacls triggers inheritance propagation."""
    needed = wintypes.DWORD()
    advapi.GetFileSecurityW(str(path), 4, None, 0, ctypes.byref(needed))
    if not needed.value:
        raise _win32_error("GetFileSecurityW size")
    descriptor = ctypes.create_string_buffer(needed.value)
    if not advapi.GetFileSecurityW(str(path), 4, descriptor, needed.value,
                                  ctypes.byref(needed)):
        raise _win32_error("GetFileSecurityW")
    return descriptor.raw


def _restore_dacl(path: Path, descriptor: bytes, advapi: ctypes.WinDLL) -> None:
    # Unlike SetNamedSecurityInfo, SetFileSecurity does not propagate to children.
    if not advapi.SetFileSecurityW(str(path), 4, ctypes.create_string_buffer(descriptor)):
        raise _win32_error("SetFileSecurityW")


def run_verifier(command: str, cwd: Path, common: Path, timeout: int,
                 env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Return exit 126 if the operating-system boundary cannot be established."""
    if os.name != "nt":
        return subprocess.CompletedProcess([], 126, "", "Windows AppContainer requires Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    userenv = ctypes.WinDLL("userenv", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    ole = ctypes.WinDLL("ole32", use_last_error=True)
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    kernel.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, wintypes.DWORD,
                                                         wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t)]
    kernel.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t,
                                                  ctypes.c_void_p, ctypes.c_size_t,
                                                  ctypes.c_void_p, ctypes.c_void_p]
    kernel.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
                                      ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_void_p,
                                      ctypes.POINTER(PROCESS_INFORMATION)]
    kernel.CreateProcessW.restype = wintypes.BOOL
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                               wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel.ResumeThread.restype = wintypes.DWORD
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    userenv.CreateAppContainerProfile.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR,
                                                   wintypes.LPCWSTR, ctypes.c_void_p,
                                                   wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)]
    userenv.CreateAppContainerProfile.restype = ctypes.c_long
    userenv.DeleteAppContainerProfile.argtypes = [wintypes.LPCWSTR]
    userenv.DeleteAppContainerProfile.restype = ctypes.c_long
    userenv.GetAppContainerFolderPath.argtypes = [wintypes.LPCWSTR,
                                                  ctypes.POINTER(wintypes.LPWSTR)]
    userenv.GetAppContainerFolderPath.restype = ctypes.c_long
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi.FreeSid.argtypes = [ctypes.c_void_p]
    advapi.FreeSid.restype = ctypes.c_void_p
    advapi.GetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
                                       wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.GetFileSecurityW.restype = wintypes.BOOL
    advapi.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
    advapi.SetFileSecurityW.restype = wintypes.BOOL

    cwd, common = cwd.resolve(), common.resolve()
    name = "AgentSmith.Verifier." + uuid.uuid4().hex
    token = uuid.uuid4().hex
    script = cwd / f".agentsmith-verifier-{token}.py"
    request_path = cwd / f".agentsmith-verifier-{token}.request.json"
    result_path = cwd / f".agentsmith-verifier-{token}.result.json"
    sid_pointer = ctypes.c_void_p()
    sid_text = wintypes.LPWSTR()
    folder_pointer = wintypes.LPWSTR()
    attributes = None
    attributes_ready = False
    job = process = thread = None
    grants: list[tuple[Path, bytes]] = []
    profile_created = False
    outcome = subprocess.CompletedProcess([command], 126, "", "verifier sandbox did not start")
    cleanup_errors: list[str] = []
    try:
        # A fresh identity makes ACL removal unambiguous even after a failed run.
        result = userenv.CreateAppContainerProfile(name, name, "Temporary verifier",
                                                    None, 0, ctypes.byref(sid_pointer))
        if result != 0 or not sid_pointer.value:
            raise SandboxError(f"CreateAppContainerProfile failed: HRESULT {result:#x}")
        profile_created = True
        if not advapi.ConvertSidToStringSidW(sid_pointer, ctypes.byref(sid_text)):
            raise _win32_error("ConvertSidToStringSidW")
        sid = sid_text.value
        if userenv.GetAppContainerFolderPath(sid, ctypes.byref(folder_pointer)) != 0:
            raise SandboxError("GetAppContainerFolderPath failed")
        script.write_text(
            "import json, subprocess, sys\n"
            "from pathlib import Path\n"
            "request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
            "try:\n"
            "    result = subprocess.run(request['command'], shell=True, text=True, "
            "capture_output=True, timeout=request['timeout'], errors='replace')\n"
            "    report = {'returncode': result.returncode, 'stdout': result.stdout, "
            "'stderr': result.stderr}\n"
            "except subprocess.TimeoutExpired:\n"
            "    report = {'returncode': 126, 'stdout': '', 'stderr': 'verifier timed out'}\n"
            "Path(sys.argv[2]).write_text(json.dumps(report), encoding='utf-8')\n",
            encoding="utf-8",
        )
        request_path.write_text(json.dumps({"command": command, "timeout": timeout}), encoding="utf-8")

        # Inheritable ACLs cover existing files and future children. The common
        # Git store is read-only; only the disposable checker worktree is writable.
        allowed: list[tuple[Path, str]] = [(cwd, "M"), (common, "RX"),
                                           (Path(sys.prefix).resolve(), "RX")]
        git = shutil.which("git")
        if git:
            allowed.append((Path(git).resolve().parent.parent, "RX"))
        for path, rights in allowed:
            if path not in (granted for granted, _ in grants):
                grants.append((path, _original_dacl(path, advapi)))
                _acl(path, sid, rights)

        size = ctypes.c_size_t()
        kernel.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        attributes = ctypes.create_string_buffer(size.value)
        if not kernel.InitializeProcThreadAttributeList(attributes, 1, 0, ctypes.byref(size)):
            raise _win32_error("InitializeProcThreadAttributeList")
        attributes_ready = True
        caps = SECURITY_CAPABILITIES(sid_pointer, None, 0, 0)
        if not kernel.UpdateProcThreadAttribute(attributes, 0, 0x20009, ctypes.byref(caps),
                                                ctypes.sizeof(caps), None, None):
            raise _win32_error("UpdateProcThreadAttribute")
        startup = STARTUPINFOEX()
        startup.StartupInfo.cb = ctypes.sizeof(startup)
        startup.lpAttributeList = ctypes.cast(attributes, ctypes.c_void_p)
        creation_env = {**env, "SystemRoot": os.environ["SystemRoot"],
                        "WINDIR": os.environ["SystemRoot"],
                        "COMSPEC": str(Path(os.environ["SystemRoot"]) / "System32/cmd.exe"),
                        "PATHEXT": os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD"),
                        "LOCALAPPDATA": folder_pointer.value, "APPDATA": str(cwd),
                        "USERPROFILE": str(cwd), "HOMEDRIVE": cwd.drive,
                        "HOMEPATH": str(cwd)[len(cwd.drive):],
                        "HOME": str(cwd), "TMP": str(cwd), "TEMP": str(cwd)}
        block = ctypes.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in
                                                    sorted(creation_env.items(), key=lambda item: item[0].upper()))
                                              + "\0\0")
        executable = sys.executable
        cmdline = ctypes.create_unicode_buffer(subprocess.list2cmdline(
            [executable, str(script), str(request_path), str(result_path)]))
        info = PROCESS_INFORMATION()
        # CREATE_SUSPENDED prevents any child running before it joins the job.
        flags = 0x00080000 | 0x00000400 | 0x00000004
        if not kernel.CreateProcessW(executable, cmdline, None, None, False, flags, block,
                                     str(cwd), ctypes.byref(startup), ctypes.byref(info)):
            raise _win32_error("CreateProcessW")
        process, thread = info.hProcess, info.hThread
        job = kernel.CreateJobObjectW(None, None)
        if not job:
            raise _win32_error("CreateJobObjectW")
        limits = EXTENDED_LIMIT()
        limits.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise _win32_error("SetInformationJobObject")
        if not kernel.AssignProcessToJobObject(job, process):
            raise _win32_error("AssignProcessToJobObject")
        if kernel.ResumeThread(thread) == 0xFFFFFFFF:
            raise _win32_error("ResumeThread")
        wait = kernel.WaitForSingleObject(process, max(1, timeout) * 1000)
        if wait == 0x00000102:
            raise SandboxError("verifier timed out")
        if wait != 0:
            raise _win32_error("WaitForSingleObject")
        exit_code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(process, ctypes.byref(exit_code)):
            raise _win32_error("GetExitCodeProcess")
        if exit_code.value or not result_path.is_file():
            raise SandboxError(f"AppContainer verifier runner failed with exit {exit_code.value}")
        report = json.loads(result_path.read_text(encoding="utf-8"))
        if (not isinstance(report, dict) or set(report) != {"returncode", "stdout", "stderr"}
                or not isinstance(report["returncode"], int)
                or not isinstance(report["stdout"], str)
                or not isinstance(report["stderr"], str)):
            raise SandboxError("AppContainer verifier runner produced an invalid result")
        outcome = subprocess.CompletedProcess([command], report["returncode"],
                                              report["stdout"], report["stderr"])
    except (OSError, ValueError, SandboxError) as exc:
        outcome = subprocess.CompletedProcess([command], 126, "", str(exc))
    finally:
        # Closing the job kills descendants before the temporary ACLs are revoked.
        if job and not kernel.CloseHandle(job):
            cleanup_errors.append("could not close verifier job")
        if thread:
            kernel.CloseHandle(thread)
        if process:
            kernel.CloseHandle(process)
        if attributes_ready:
            kernel.DeleteProcThreadAttributeList(attributes)
        for path, descriptor in reversed(grants):
            try:
                _acl(path, sid_text.value, "", remove=True)
            except (OSError, SandboxError) as exc:
                cleanup_errors.append(str(exc))
            try:
                _restore_dacl(path, descriptor, advapi)
            except (OSError, SandboxError) as exc:
                cleanup_errors.append(str(exc))
        for path in (script, request_path, result_path):
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                cleanup_errors.append(str(exc))
        if sid_text:
            kernel.LocalFree(ctypes.cast(sid_text, ctypes.c_void_p))
        if folder_pointer:
            ole.CoTaskMemFree(ctypes.cast(folder_pointer, ctypes.c_void_p))
        if sid_pointer.value:
            advapi.FreeSid(sid_pointer)
        if profile_created:
            if userenv.DeleteAppContainerProfile(name) != 0:
                cleanup_errors.append("could not delete AppContainer profile")
    if cleanup_errors:
        return subprocess.CompletedProcess([command], 126, "", "; ".join(cleanup_errors)[:500])
    return outcome
