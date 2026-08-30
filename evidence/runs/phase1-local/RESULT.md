# Phase 1 local vertical-slice evidence

## Result

PASS — a browser-submitted project (`门外的人`) was created through Next.js, persisted through FastAPI's Phase-1 repository boundary, rendered as three deterministic Mock shots with FFmpeg, and displayed as a playable browser MP4.

## Media probe

```text
codec_name=h264
width=720
height=1280
r_frame_rate=30/1
codec_name=aac
sample_rate=48000
```

## Browser verification

- Home page showed the title, both labelled input controls, and the generation button.
- No Next.js error overlay was present.
- After submission, the page contained one `<video>` element and the `ROUGH_CUT_READY` state.
- Screenshot: `phase1-browser-playback.png`.

## Notes

- The first browser attempt exposed a local CORS mismatch (`127.0.0.1:3000` versus `localhost:3000`); the API now explicitly allows both local development origins.
- Persistence is the Product Owner-approved, temporary Phase-1 SQLite implementation behind `ProjectRepository`; it is not budget or production-concurrency evidence.
