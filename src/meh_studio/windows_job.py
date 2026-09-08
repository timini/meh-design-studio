"""Windows child-tree lifetime using a kill-on-close Job Object.

Children start suspended and are assigned before their main thread is resumed.
https://learn.microsoft.com/windows/win32/procthread/job-objects
"""
import ctypes as c
from ctypes import wintypes as w
import os

CREATE_SUSPENDED = 0x00000004


class BasicLimits(c.Structure):
    _fields_ = [("process_time",c.c_longlong),("job_time",c.c_longlong),("flags",w.DWORD),
                ("minimum_working_set",c.c_size_t),("maximum_working_set",c.c_size_t),
                ("active_processes",w.DWORD),("affinity",c.c_size_t),
                ("priority",w.DWORD),("scheduling",w.DWORD)]


class IoCounters(c.Structure):
    _fields_ = [(name,c.c_ulonglong) for name in ("reads","writes","others","read_bytes","write_bytes","other_bytes")]


class ExtendedLimits(c.Structure):
    _fields_ = [("basic",BasicLimits),("io",IoCounters),("process_memory",c.c_size_t),
                ("job_memory",c.c_size_t),("peak_process_memory",c.c_size_t),("peak_job_memory",c.c_size_t)]


class ThreadEntry(c.Structure):
    _fields_ = [("size",w.DWORD),("usage",w.DWORD),("thread_id",w.DWORD),
                ("process_id",w.DWORD),("base_priority",w.LONG),("delta_priority",w.LONG),("flags",w.DWORD)]


class WindowsJob:
    def __init__(self):
        if os.name != "nt":
            raise ValueError("Windows Job Objects require Windows")
        self.kernel = c.WinDLL("kernel32",use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([c.c_void_p,w.LPCWSTR],w.HANDLE),
            "SetInformationJobObject": ([w.HANDLE,c.c_int,c.c_void_p,w.DWORD],w.BOOL),
            "OpenProcess": ([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),
            "AssignProcessToJobObject": ([w.HANDLE,w.HANDLE],w.BOOL),
            "CloseHandle": ([w.HANDLE],w.BOOL),
            "CreateToolhelp32Snapshot": ([w.DWORD,w.DWORD],w.HANDLE),
            "Thread32First": ([w.HANDLE,c.POINTER(ThreadEntry)],w.BOOL),
            "Thread32Next": ([w.HANDLE,c.POINTER(ThreadEntry)],w.BOOL),
            "OpenThread": ([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),
            "ResumeThread": ([w.HANDLE],w.DWORD),
        }
        for name,(args,result) in signatures.items():
            function = getattr(self.kernel,name)
            function.argtypes,function.restype = args,result
        self.handle = self.kernel.CreateJobObjectW(None,None)
        if not self.handle:
            raise c.WinError(c.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle,9,c.byref(limits),c.sizeof(limits)):
            error = c.get_last_error()
            self.close()
            raise c.WinError(error)

    def __enter__(self):
        return self

    def __exit__(self,*_):
        self.close()

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None

    def assign_and_resume(self,pid):
        # PROCESS_SET_QUOTA | PROCESS_TERMINATE are the assignment rights.
        process = self.kernel.OpenProcess(0x0101,False,pid)
        if not process:
            raise c.WinError(c.get_last_error())
        try:
            if not self.kernel.AssignProcessToJobObject(self.handle,process):
                raise c.WinError(c.get_last_error())
        finally:
            self.kernel.CloseHandle(process)
        snapshot = self.kernel.CreateToolhelp32Snapshot(0x00000004,0)  # TH32CS_SNAPTHREAD
        if snapshot == c.c_void_p(-1).value:
            raise c.WinError(c.get_last_error())
        try:
            entry = ThreadEntry()
            entry.size = c.sizeof(entry)
            found = self.kernel.Thread32First(snapshot,c.byref(entry))
            while found:
                if entry.process_id == pid:
                    thread = self.kernel.OpenThread(0x0002,False,entry.thread_id)  # THREAD_SUSPEND_RESUME
                    if not thread:
                        raise c.WinError(c.get_last_error())
                    try:
                        if self.kernel.ResumeThread(thread) == 0xFFFFFFFF:
                            raise c.WinError(c.get_last_error())
                    finally:
                        self.kernel.CloseHandle(thread)
                    return
                found = self.kernel.Thread32Next(snapshot,c.byref(entry))
            raise ValueError("cannot locate the suspended child thread")
        finally:
            self.kernel.CloseHandle(snapshot)
