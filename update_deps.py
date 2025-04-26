import subprocess

def run(cmd):
    print(f"▶️ Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

print("📦 Updating pip...")
run(["pip", "install", "--upgrade", "pip"])

print("\n🔍 Checking for outdated packages...")
result = subprocess.run(
    ["pip", "list", "--outdated", "--format=freeze"],
    capture_output=True, text=True
)

outdated = [line.split("==")[0] for line in result.stdout.strip().split("\n") if "==" in line]

if not outdated:
    print("✅ All packages are up to date!")
else:
    print(f"⬆️  Outdated packages: {outdated}")
    for pkg in outdated:
        run(["pip", "install", "--upgrade", pkg])

print("✅ Done!")
