import sys, os

# Parent folder = D:\NetSim-astra (one level up from astra-shared)
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ui_dir = os.path.join(parent_dir, "astra-ui-app")
sp = os.path.join(ui_dir, "settings_private.py")

# Check env var first
if os.environ.get("CESIUM_TOKEN", "").strip():
    print("[OK] CESIUM_TOKEN set via environment variable.")
    sys.exit(0)

# Check settings_private.py
if not os.path.exists(sp):
    print("[WARN] settings_private.py not found.")
    sys.exit(1)

ns = {}
exec(open(sp).read(), ns)
token = ns.get("CESIUM_TOKEN", "").strip()
if not token or token.upper().startswith("REPLACE_WITH"):
    print("[WARN] CESIUM_TOKEN is empty or placeholder in settings_private.py.")
    sys.exit(1)

print("[OK] CESIUM_TOKEN found in settings_private.py.")
sys.exit(0)
