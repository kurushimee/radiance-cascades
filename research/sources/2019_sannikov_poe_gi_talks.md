# Alexander Sannikov's Path of Exile GI talks

Two recorded talks on Path of Exile rendering. The 2019 talk covers the hierarchical screen-space shadows and screen-space GI that led to radiance cascades. The 2023 talk covers the first radiance cascades version in Path of Exile 2.

## ExileCon Dev Talk - Evolving Path of Exile's Renderer

| | |
|---|---|
| Author | Path of Exile |
| Date | 2020-04-06 |
| Kind | video |
| Link | https://www.youtube.com/watch?v=whyJzrVEgVc |

The talk is by Alexander Sannikov, a graphics programmer at Grinding Gear Games, and was recorded at ExileCon 2019. These notes cover the point-light shadow method and the screen-space global illumination method, the two techniques that led to radiance cascades.

### Source notes

- The captions are the English track named "en". The auto-generated track was not used.
- The captions give no ray, segment or sample counts and no probe layers; the GI is a screen-space gather in which every pixel acts as a point light, with a 3 ms frame budget. The 10 ms near 44:05 is dynamic atlas building, not GI. "Variance" refers to variance shadow maps, and "cascades" in the shadow part are shadow levels of detail.
- The ExileCon link `B-ODrtmtpzM` found elsewhere is a private video; the devtrackers list of ExileCon 2019 talks gives this renderer talk at `whyJzrVEgVc`, and no 2019 GDC talk on PoE's screen-space GI was found.
- The video runs 54 minutes 38 seconds. Timestamps are caption minutes.

### Point light shadows (about 09:00 to 18:30)

#### Problem and requirements

- A point is in shadow when an occluder blocks it from a point light.
- Shadows show where objects touch surfaces. The speaker says without them it is hard to tell whether an object touches the floor.
- The penumbra is the gradient at the shadow edge. It has zero width where an object touches the ground.
- The classical method renders a sharp shadow map and then blurs it. The speaker calls this two separate jobs.
- The speaker says penumbras of uniform width, as seen in other games, are not physically correct.
- Shadow maps suit directional lights and spotlights. An omnidirectional point light needs six cube-face shadow maps.
- The speaker says no one does this, because cube-face shadow maps are too expensive or do not scale.
- Point light shadows were added for the Delve league. Players could not turn them off in Delve.
- The requirement was shadows that are fast, look good, and work on any configuration.

#### Method name and stages

- The speaker names the method: Screenspace, Hierarchical, Variance, Shadow maps. The talk does not explain the word "variance".
- The input is a shadow map of a player light. White marks points lit by the light. Black marks points blocked by something.
- The speaker shows each stage by turning it off.
- Stage 1, one-pixel blur: without it, the shadow edges alias.
- Stage 2, depth-aware upscaling: without it, areas look blocky.
- Stage 3, cascades: the shadow is split into levels. Each level has its own detail and covers a different part of the screen.
- The first level covers the contact region, which is the sharpest part of the penumbra. It is small, and it gets the most precision.
- The next level needs less detail, because the penumbra there is blurred.
- The farthest part needs the least resolution.
- Stage 4, MIP levels: the speaker says load is spread evenly across the MIP levels.
- The lowest resolution is the cheapest, so the largest part of the shadow is computed at that resolution.
- The speaker says that in traditional methods the most-blurred far end costs the most, while this method spreads the load evenly.
- Restoring the stages in order gives the final image: depth-aware upscaling, then blur, then all MIP levels.

#### Cost model

- In the traditional method, each point light needs its own shadow map, so the scene is rendered once per light. The speaker's example is ten lights, which means ten renders of every object.
- This method gives each screen point a fixed number of shadow contributions. The speaker's example: with a hundred lights, each point is affected by two major lights.
- The cost is capped. Performance stays steady whatever the number of objects or lights.
- The speaker says a steady frame rate matters more than a high peak. The speaker compares a game at 300 FPS that drops to 5 with a game that stays between 60 and 100 FPS.
- The method uses data already on screen and renders no extra geometry.

#### Limits

- The speaker says the method depends on several specific properties of PoE and its engine. Removing any one of them would make the method not good enough.
- The speaker says the method would produce artifacts in general-purpose games such as 3D shooters.
- The method is built for the in-house engine.

### Screen-space global illumination (about 18:30 to 28:00)

#### Scope and effects

- The GI feature is optional. It is on by default in all demos.
- GI adds a secondary light bounce. Example: light from a staircase bounces into areas that would otherwise get no light.
- The speaker says GI gives an ambient-occlusion-like feel and ties the picture together.
- Spells can act as light sources and light a scene.
- Demo: a scene lit by one spotlight. Without GI, the rest of the scene is black.
- Demo: a scene where all the lighting is indirect, from a single light source.
- Example: a dragon that is an emissive material. It lights its surroundings with no light sources placed.

#### Model

- In screen space, every visible pixel acts as a point light source with its own shadows.
- The speaker says the method is optimized for the case of infinitely many light sources.
- The governing equation is the rendering equation, which describes light transport in any 3D scene.
- A path tracer can be written in about fifteen lines of code, according to the speaker. The speaker says the full calculation takes about five hours (caption wording unclear).
- The frame budget for this GI is about 3 ms.
- The speaker says offline renderers such as Maya, a Max renderer and V-Ray do the same task, but take far longer than 3 ms.

#### Methods not used

- Temporal reprojection assumes that frames change little. The speaker says PoE changes too fast for that. The result would blur, and ambient occlusion would lag behind moving objects.
- Baking does not fit the dynamic level generator. Each tile can connect to any neighboring tile, and the speaker says these tile interactions cannot be baked.
- Ray tracing hardware (RTX) is not used. The speaker says the method still runs faster in the end, because the algorithm is smarter, not because more hardware is used. No figures are given.

#### Sampling method

1. Baseline: for each screen point, gather light from a finite set of other screen points. The baseline sample pattern is exponential sampling, which is common in ambient occlusion. The speaker says this looks poor.
2. Same sample count: neighboring pixels use different random seeds. The total work stays the same, but the samples are spread more randomly over the screen, which looks like more samples.
3. A box filter is applied over the fixed 4 by 4 pixel random pattern.
4. Lower MIP levels are used for pixels far from the light. The speaker describes these levels as averaged information.
5. MIP mapping is also applied to the color information.
- The speaker says every step keeps the same number of samples, the same shader cost and the same calculation time.

#### Execution

- The GI and the point light shadows run entirely on the GPU.
- The CPU stays free for gameplay. The speaker says the CPU is heavily loaded with gameplay, so this split matters.
- The speaker says the GI and the shadow work do not block each other.

## Most Performant Global Illumination POE2 Rendering

| | |
|---|---|
| Author | Cakez |
| Date | 2023-08-01 |
| Kind | video |
| Link | https://www.youtube.com/watch?v=ShiFEvlzbew |

The video is a recording of a talk by Alexander Sannikov on rendering in Path of Exile 2. These notes cover only the global illumination section, from about 30:41 to the end, which describes a hierarchy of cascades built from radiance probes.

### Source notes

- The captions are auto-generated, and some words are wrong. For example, the captions read "global elimination" where the talk means global illumination. Corrections are marked only where the meaning is clear.
- The talk never uses the phrase "radiance cascades". It uses "cascades" and "radiance probes".
- The video runs 45 minutes 11 seconds. Timestamps are caption minutes.

### Problem statement (31:00)

- Global illumination is light bouncing between surfaces.
- Each point casts light onto every other point, receives light from every other point, and can block light between them.
- The speaker calls this many-to-many interaction notoriously hard to compute.
- Path tracing is simple to write. The speaker says it takes minutes per frame.
- The speaker says the industry methods the speaker knew did not fit the game.

### Earlier screen-space GI in PoE (32:00)

- The speaker says PoE was the first game to ship with screen-space GI. The captions give the basis of that method as "based on variants", which is unclear.
- The earlier GI lacked a property that the screen-space shadows had.
- The screen-space shadows use cascades. The first cascade covers a large part at low resolution. The next covers a part at higher resolution. The last covers a small part that needs the highest resolution.
- Each part is computed at its own resolution, so the total cost is lower.
- The speaker wanted GI to use the same cascade property.

### Radiance probes and the hierarchy (33:30)

- The common GI method uses radiance probes. A probe is placed in the level and captures a cube map of its surroundings. Objects are lit from the nearest probe.
- The question is how many probes to place, and at what resolution. Studios answer it differently.
- The speaker's answer is to use a hierarchy of both. A few high-resolution probes sit in one layer, and a layer with many more probes at lower resolution sits alongside it. The captions are partly unclear at this point.
- The speaker calls this a radiance probe hierarchy.

### 2D prototype (35:00)

- The speaker built the idea in 2D first, because 3D was harder to build.
- The speaker says 2D GI is almost as hard as 3D GI.
- The speaker says the 2D idea worked on its first implementation.
- The 2D experiment is on the speaker's YouTube channel.

### Cascades in 2D (36:00)

- Each cascade has a different number of rays. Each one matches a different probe resolution.
- Left example: a grid of probes, each probe casting four rays.
- Right example: fewer probes, each probe casting more rays.
- The speaker says each probe can have eight rays after the cascades are combined.
- Each ray is built from segments. The segments are slightly bent. Shorter segments approximate straight lines better, and the rays converge to straight lines as the segments shorten.
- Numbers as spoken: 16 probes with eight rays each, giving 128 rays in total after combining.
- The speaker also gives 64 segments for one cascade and 32 segments for the other. The captions read "30 64" for the first figure.
- These figures are not fully consistent in the captions. Check the source for exact values.

### Scaling with cascade count (38:00)

- The speaker shows ray counts for increasing cascade counts: 64, a value the captions read as 120, and 256. The speaker says the counts are powers of two.
- The total cost of all cascades approaches a constant as cascades are added.
- Each cascade after the first is cheaper than the one before it.
- The speaker says a hundred cascades cost about the same as one cascade.
- The number of rays grows exponentially with the number of cascades.
- The total cost of an infinite number of cascades is bounded by a constant.
- The speaker summarizes it as each cascade capturing twice more rays for what the captions call "twice less speed". The speaker calls this an exploit.

### 3D version in PoE (40:00)

- The speaker implemented the 2D method in 3D for PoE.
- Cascade 1 captures only a tiny neighborhood of each point. The speaker says it looks like poor ambient occlusion.
- Cascade 2 captures longer-range light at a lower frequency.
- Each later cascade captures even lower frequencies and longer ranges.
- Each cascade covers one range. Combined, they give fine detail and long-range light in one result.

### Storage layout (41:00)

- The first level has many tiny probes in small grids.
- Higher levels have larger probes, and fewer of them.
- Memory per level decreases as the cascade count rises.
- The speaker says the first cascade is the more expensive one, in terms of memory.

### Emissive surfaces (41:45)

- The speaker says light from emissive surfaces costs the same to compute as light from directly lit surfaces.
- The speaker says emissive test scenes are a typical way to test GI methods.

### Screen space and world space (42:30)

- The PoE build uses screen-space probes and screen-space information.
- The speaker says the same cascade hierarchy can run in world space, and the speaker's posted demo does this.
- The world-space demo uses no screen-space data. It can light from sources behind the camera. PoE does not need that.
- The speaker says the world-space form may suit other games.

### Specular GI (42:50)

- The encoding stores light reaching each point from every direction. The speaker says this lets the same method compute specular GI.
- A dungeon with narrow materials shows specular GI.
- A curtain of porcelain-like material shows highlights from specular GI.
- Diffuse and specular combined are used in the game.

### Speed and convergence (43:30)

- The in-game version is faster than the earlier screen-space method, according to the speaker.
- Correct GI methods converge to the same image. The speaker therefore shows no side-by-side comparison. The question is how quickly each method produces that image.
- The speaker says the method scales better than the earlier PoE method and better than anything else the speaker has seen. No numbers are given.

### Limits stated

- The in-game version uses screen-space data, so light from sources behind the camera is not handled. The speaker says PoE does not need it.
- No frame times, resolutions or hardware are given for the GI.
