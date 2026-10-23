# Project video

`make_video.py` makes the 2–3 minute screencast the course guidelines ask for (§7), with a
voice-over and subtitles, in three versions (*cuts*) told for different audiences:

| cut | story | output |
|---|---|---|
| `problems` | **the shop's eight everyday problems and how each one is solved**: who owes what, forgotten promises, a busy counter, stock running out, crops bought from farmers, where the money went, computers and English, trust and safety; then how it works for the shop, setting it up (clone, install, test, run) and how it is tested | `out/high-table-holdings-problems.mp4` (2:51) |
| `tour` | a feature tour: build and test, Today, Counter, Khata, Stock, Money, Reports, the assistant, Hindi, themes, safety, architecture | `out/high-table-holdings.mp4` (2:59) |
| `technical` | **for the Software Engineering & Management class**: scope and process; requirements from user stories to numbered FRs; state and sequence diagrams; DFD level 0 and 2; the ER model; decision table DT-3; the LEDGER and ENTRY algebraic specs; layers and the 13 decision records; the real interest and transaction code; FR-9.1 traced to its tests and the screen; testing; WBS, activity network and PERT; project management; deployment. The diagrams, tables, specs and code are read from the course pack and the source at render time | `out/high-table-holdings-technical.mp4` (about 2:40) |

Both are 1920×1080, 30 fps, H.264 + AAC.

```bash
python sme/video/make_video.py --cut problems              # all steps, about 10 minutes
python sme/video/make_video.py --cut problems slides build # only re-draw the slides and the video
python sme/video/make_video.py --cut problems preview      # one still per shot in out/preview-problems/
python sme/video/make_video.py --cut technical             # the technical version
python sme/video/make_video.py                             # the tour (the default cut)
```

The app captures (`capture`) and slides (`slides`) are shared by both cuts; `voice`, `preview` and
`build` are per cut. The technical slides draw their Mermaid diagrams with Mermaid 11.4.1 from jsDelivr, so
rendering them needs the internet once.

| step | does | output |
|---|---|---|
| `capture` | starts the real program on a **made-up demo shop** in a temporary folder and drives it: sign-in, Today, a three-line sale with paid-now, undo, a crop purchase and sale, a GST bill, the audit log, khata, collections, stock, money, reports, three questions to the assistant, Hindi, colour themes, backup and updates settings, the screen lock | `out/frames/*.png`, `out/capture.json` |
| `slides` | the slides of both cuts (for `problems`: title, the shop, the eight problems, a card per problem, how it works, quality, closing), drawn as HTML by Microsoft Edge | `out/slides/*.png` |
| `voice` | the narration (Microsoft Ravi, English (India)) and the assistant's spoken answer (Microsoft Kalpana, Hindi), with Windows' own voices | `out/voice/` (tour), `out/voice-problems/` |
| `build` | times every shot to the narration, adds the camera moves, highlights and subtitles, and encodes with ffmpeg | the cut's `.mp4` |

**Team names.** Fill in `team.json` (`team_no`, `members`) and run
`python sme/video/make_video.py --cut problems slides build` (and the same without `--cut` for the
tour). The names then appear on the title and closing slides.

**What is real.** Every app picture is the actual program (5.7.0), captured with PrintWindow; the
shop's own data is never opened. The terminal part shows a real fresh clone, install and test run
on the development PC, shortened with `…` (the full log was 175 lines; the run ended
`280 passed, 36 skipped in 39.60s`). The assistant's Hindi answer is the one the program gave in
the capture, spoken by the same Windows voice the program uses (first sentence only).

**Changing the script.** The narration, subtitles and shot timings are in `storyboard_problems()`,
`storyboard_technical()` and `storyboard_tour()`; the problem cards' wording is in `PROBLEMS`. Each
`Line` has the subtitle text and, where the voice needs help with a word, what it should say;
each `Shot` names a frame, the line (and fraction of it) when it appears, and an optional
highlight box in the app's 1366×745 pixels with a zoom. Run `preview` to check the framing before
`build`.

**Needs** Windows, ffmpeg on `PATH`, Microsoft Edge, and the app's own requirements (Pillow,
numpy and pywin32 come with them).
