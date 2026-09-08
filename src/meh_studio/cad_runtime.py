"""CadQuery loading and a Windows-only native shutdown compatibility guard.

See CadQuery issue 1911 and proposed upstream fix 2092. No process exit codes
are suppressed; the guard prevents a known cross-CRT free during shutdown.
"""
import atexit
import sys

_registered = False


def _shutdown_swig_guard():
    if sys.platform != 'win32' or sys.implementation.name != 'cpython':
        return
    if not all(name in sys.modules for name in ('casadi','nlopt')):
        return
    runtime=sys.modules.get('swig_runtime_data5')
    capsule=getattr(runtime,'type_pointer_capsule',None)
    if capsule is None:
        return
    import ctypes
    setter=ctypes.pythonapi.PyCapsule_SetDestructor
    setter.argtypes=[ctypes.py_object,ctypes.c_void_p]
    setter.restype=ctypes.c_int
    # Only at interpreter shutdown: the OS reclaims this small shared type
    # table, avoiding a free through a different native allocator.
    setter(capsule,None)


def load_cadquery():
    global _registered
    if not _registered and sys.platform=='win32':
        atexit.register(_shutdown_swig_guard)
        _registered=True
    import cadquery
    return cadquery
