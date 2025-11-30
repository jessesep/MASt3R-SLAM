# Gaussian Splatting Quick Reference

**30-Second Cheatsheet: SLAM → Gaussian Splats**

---

## One-Command Pipeline

```bash
# 1. Run SLAM with PLY export
python main_live.py --source webcam --save-ply

# 2. Train Gaussian Splatting
python train_gaussian_splat.py \
    --input results/live/*.ply \
    --keyframes logs/keyframes/ \
    --method nerfstudio \
    --use-glomap

# 3. View results
ns-viewer --load-config gaussian_splats/splatfacto/*/config.yml
```

**Done!** 🎉

---

## Using the Control GUI

1. `python slam_control_gui.py`
2. ✅ Check "**Save PLY on exit (for Gaussian Splatting)**"
3. Select source (NDI, Webcam, Dataset)
4. Click "🚀 Launch SLAM"
5. Wait for completion
6. Run training pipeline (see above)

---

## Common Commands

### Export SLAM to COLMAP

```bash
./export_to_colmap.py \
    --input logs/my_dataset.ply \
    --keyframes logs/keyframes/ \
    --output colmap_exports/my_dataset/
```

### Train with Nerfstudio (Recommended)

```bash
./train_gaussian_splat.py \
    --input logs/my_dataset.ply \
    --keyframes logs/keyframes/ \
    --method nerfstudio \
    --use-glomap
```

### Train with OpenSplat (Production)

```bash
./train_gaussian_splat.py \
    --input logs/my_dataset.ply \
    --keyframes logs/keyframes/ \
    --method opensplat \
    --export-ply
```

### View Nerfstudio Results

```bash
ns-viewer --load-config gaussian_splats/splatfacto/*/config.yml
```

### Export for Web

```bash
ns-export gaussian-splat \
    --load-config gaussian_splats/splatfacto/*/config.yml \
    --output-dir web_export/
```

---

## Installation (One-Time Setup)

```bash
# Install GLOMAP (10-100x faster!)
conda install -c conda-forge glomap

# Install COLMAP
conda install conda-forge::colmap

# Install Nerfstudio
pip install nerfstudio
```

---

## File Locations

| File | Location |
|------|----------|
| PLY output | `logs/*.ply` or `results/live/*.ply` |
| Keyframes | `logs/keyframes/*.png` |
| Trajectory | `logs/*.txt` |
| COLMAP export | `colmap_exports/*/` |
| Trained model | `gaussian_splats/*/` |

---

## Troubleshooting Quick Fixes

| Problem | Solution |
|---------|----------|
| No PLY file | Add `--save-ply` flag or check GUI checkbox |
| GLOMAP not found | `conda install -c conda-forge glomap` |
| Out of memory | Reduce `--iterations` or use OpenSplat |
| Poor quality | Provide camera intrinsics with `--fx --fy --cx --cy` |

---

## Performance Tips

- **Use GLOMAP** (`--use-glomap`) for 10-100x faster preprocessing
- **RTX 5090 + WSL2**: Expect ~15-20 min for complete pipeline
- **Lower-end GPUs**: Use `--iterations 15000` for faster training
- **Best quality**: Provide actual camera intrinsics, not estimates

---

## TouchDesigner Integration

```bash
# SLAM with NDI input + OSC output
python main_live.py \
    --source ndi \
    --ndi-name "TouchDesigner Output" \
    --save-ply \
    --osc-enable

# Train after capture
./train_gaussian_splat.py \
    --input results/live/live_ndi_*.ply \
    --keyframes logs/keyframes/ \
    --method nerfstudio \
    --use-glomap
```

---

**Full documentation:** See `GAUSSIAN_SPLATTING_SETUP.md`

**Happy Splatting!** ✨
