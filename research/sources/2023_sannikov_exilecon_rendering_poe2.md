# ExileCon 2023: Rendering Path of Exile 2

| | |
|---|---|
| Author | Alexander Sannikov (Grinding Gear Games) |
| Date | 2023-07 |
| Kind | Talk (53 min); GI part runs from 27:00 to 39:00, Q&A after |
| Link | https://www.youtube.com/watch?v=TrHHTQqmAaM |

The public debut of radiance cascades, as one of about a dozen PoE2 rendering techniques. The GI section explains the idea for a general audience; the Q&A adds the shipped cost and the reasons screen space is enough for PoE2.

## GI section

- PoE1 shipped (2018) the first screen-space, variance-based GI in a released game (presented at ExileCon 2019). Its weakness was a denoiser that blurred detail.
- PoE's screen-space shadows already used cascades: blurry penumbra parts render at low resolution, and only the small sharp part near contact renders at full resolution. RC brings that property to GI.
- Radiance probes are "tiny cameras" capturing cubemaps. Every studio picks its own point between many small probes and few large ones; RC uses all of them at once as a hierarchy, called a "radiance probe hierarchy" in the talk.
- Development started as a 2D test, since 2D GI is almost as hard as 3D. It worked on the first try. Progress was posted on the author's YouTube channel months before the talk.
- Worked example: cascade 0 is a 4×4 grid with 4 rays each (64 segments); cascade 1 has fewer probes with 8 rays each (32 segments). Combined, every cascade 0 probe gets 8 rays, 128 in total. The combined rays are slightly bent where segments join; shorter segments make them straighter. More cascades give 64, 128, 256 rays while the cost approaches a constant.
- In PoE2's screen-space version, cascade 0 looks like "bad AO" (only the tiny neighborhood), and each higher cascade holds longer-range, lower-frequency light. The first cascade is the most expensive one.
- Emissive surfaces and directly lit surfaces cost the same for GI, so emissive-only scenes are the standard test.
- A world-space variant (shown on the author's channel) has no screen-space data and lights from sources behind the camera.
- The same data gives specular GI: mirror dungeons, porcelain-like highlights, combined diffuse and specular in game.

## Q&A facts

- The probe grid hierarchy is fixed and independent of scene content. Cost is constant at roughly 1 ms, whether one or a million fireballs are on screen, so it never drops the frame rate in heavy fights.
- Screen space is enough because PoE2 has a fixed top-down camera; there are no relevant lights behind the camera.
- PoE2 has no TAA because the game is too dynamic, which is part of why RC avoids temporal reuse.
- RC was not shipped in the PoE1 engine update at the time because of the size of the change.
