# P0 Technical Spikes

Disposable harness only. It exercises Temporal's local test server, a mock provider, SQLite transaction semantics, a typed in-memory Shot Graph, and local FFmpeg/ffprobe. It does not contain product features or paid-provider calls.

Run from the repository root:

```powershell
python -m venv ..\p0-spikes-venv
..\p0-spikes-venv\Scripts\python -m pip install -r spikes\requirements.txt
..\p0-spikes-venv\Scripts\python spikes\p0_harness.py
```

The command writes reproducible outputs under `evidence/spikes/`.
