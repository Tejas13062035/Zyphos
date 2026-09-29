"""Patch torch_audiomentations for newer torchaudio (2.9+) API removals.

torchaudio entered maintenance mode at 2.8 and removed several deprecated
functions in 2.9: set_audio_backend() and info(). torch_audiomentations
still calls both unconditionally (see github.com/iver56/torch-audiomentations
issue #184, unresolved upstream as of this writing). We need torchaudio 2.9+
for RTX 50-series (Blackwell, sm_120) GPU support, so we patch around the
missing APIs instead of downgrading torchaudio, which would break the GPU.
"""
import sys

path = sys.argv[1]
with open(path) as f:
    content = f.read()

replacements = [
    (
        'torchaudio.set_audio_backend("soundfile")',
        'if hasattr(torchaudio, "set_audio_backend"):\n'
        '    torchaudio.set_audio_backend("soundfile")',
    ),
    (
        '        info = torchaudio.info(file_path)\n',
        '        if hasattr(torchaudio, "info"):\n'
        '            info = torchaudio.info(file_path)\n'
        '        else:\n'
        '            import soundfile as _sf\n'
        '            _sf_info = _sf.info(str(file_path))\n'
        '            class _Info:\n'
        '                num_frames = _sf_info.frames\n'
        '                sample_rate = _sf_info.samplerate\n'
        '            info = _Info()\n',
    ),
]

changed = False
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        changed = True
    else:
        print("WARNING: patch target not found:", repr(old[:60]))

if changed:
    with open(path, 'w') as f:
        f.write(content)
    print("Patched:", path)
else:
    print("No changes made to:", path)
