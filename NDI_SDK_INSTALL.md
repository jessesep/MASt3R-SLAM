# NDI SDK Installation for WSL2 Ubuntu 24.04

## Download NDI SDK

1. Visit: https://ndi.tv/sdk/
2. Select "NDI SDK for Linux"
3. Download the .tar.gz file

## Install on WSL2

```bash
# Extract the downloaded file (replace with actual filename)
cd ~/Downloads
tar -xzf Install_NDI_SDK_v6_Linux.tar.gz

# Run the installer
cd NDI\ SDK\ for\ Linux/
sudo ./ndi-sdk-install

# This will install to /usr/local/lib
```

## Install Python NDI

```bash
conda activate mast3r-slam-blackwell
pip install ndi-python
```

## Test NDI

```python
# Test script
import NDIlib as ndi

if not ndi.initialize():
    print("Failed to initialize NDI")
    exit(1)

finder = ndi.find_create_v2()
print("NDI initialized successfully!")

# Wait for sources
import time
time.sleep(2)

sources = ndi.find_get_current_sources(finder)
print(f"Found {len(sources)} NDI sources:")
for i, source in enumerate(sources):
    print(f"  [{i}] {source.ndi_name}")

ndi.find_destroy(finder)
ndi.destroy()
```

## Troubleshooting

### Library not found error
```bash
# Add NDI library to system path
echo 'export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

### No sources found
- Check firewall (Windows + WSL2)
- Ensure TouchDesigner and WSL2 on same network
- Try running as administrator/sudo

## TouchDesigner NDI Output Setup

1. In TouchDesigner: Add "NDI Out TOP"
2. Set output name (e.g., "TouchDesigner_SLAM")
3. Enable output
4. Check "Active" checkbox

## Test from MASt3R-SLAM

```bash
python -c "from mast3r_slam.live_camera import NDICamera; cam = NDICamera()"
```

If successful, you'll see "Found X NDI sources" and the connection message!
