import os, torch, importlib, subprocess, sys

print("=== SYSTEM ===")
os.system("nvcc --version | head -n 5")
os.system("gcc --version | head -n 1")
print("CUDA_HOME =", os.getenv("CUDA_HOME"))
print()

print("=== PYTORCH ===")
print("Torch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("Device:", torch.cuda.get_device_name(0))
    print("Arch list:", torch.cuda.get_arch_list())
print()

print("=== MODULE IMPORT TESTS ===")
modules = ["lietorch", "asmk", "curope", "mast3r", "mast3r_slam", "in3d", "moderngl", "imgui"]
for m in modules:
    try:
        importlib.import_module(m)
        print(f"✓ {m} imported")
    except Exception as e:
        print(f"✗ {m} failed:", e)
print()

print("=== GPU ARCH VERIFICATION (curope) ===")
try:
    import curope
    path = os.path.join(os.path.dirname(curope.__file__), "curope.cpython-311-x86_64-linux-gnu.so")
    cmd = f"cuobjdump --list-text {path} | grep sm_"
    subprocess.run(cmd, shell=True, check=False)
except Exception as e:
    print("curope arch check failed:", e)
print()

print("=== EGL / OpenGL LIBRARIES ===")
os.system("ls -la /lib/x86_64-linux-gnu/libEGL.so* /lib/x86_64-linux-gnu/libGL.so* 2>/dev/null")
print()
print("=== DONE ===")
