import os
import sys
import warnings

# Suppress known upstream third-party FutureWarning (e.g. Keras/TF np.object warning)
warnings.filterwarnings("ignore", category=FutureWarning, module="keras.*")
warnings.filterwarnings("ignore", message=".*np\\.object.*", category=FutureWarning)

# Ensure TCL and TK library paths are discovered and exported before any GUI test runs
def _ensure_tcl_env():
    if "TCL_LIBRARY" not in os.environ:
        tcl_dir = os.path.join(sys.prefix, "tcl", "tcl8.6")
        if os.path.exists(tcl_dir):
            os.environ["TCL_LIBRARY"] = tcl_dir
        else:
            lib_tcl = os.path.join(sys.prefix, "Lib", "tcl8.6")
            if os.path.exists(lib_tcl):
                os.environ["TCL_LIBRARY"] = lib_tcl

    if "TK_LIBRARY" not in os.environ:
        tk_dir = os.path.join(sys.prefix, "tcl", "tk8.6")
        if os.path.exists(tk_dir):
            os.environ["TK_LIBRARY"] = tk_dir
        else:
            lib_tk = os.path.join(sys.prefix, "Lib", "tk8.6")
            if os.path.exists(lib_tk):
                os.environ["TK_LIBRARY"] = lib_tk

_ensure_tcl_env()
