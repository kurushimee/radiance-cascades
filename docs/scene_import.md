# Scene import

Read in the 4.7.2-stable source and checked again in NVIDIA's fork at `135dff3887`; paths are relative to the engine repository.

## Import script order

`ResourceImporterScene::import` runs `_generate_meshes`, which builds the `ArrayMesh`es and unwraps UV2, before it calls the import script's `_post_import` (`editor/import/3d/resource_importer_scene.cpp`). The script therefore sees `MeshInstance3D` nodes with UV2 and the imported materials on their mesh surfaces. A node's surface override material wins over the mesh's, and glTF import leaves the overrides empty.

Each mesh also has a `shadow_mesh` with one surface per surface of the mesh (`ImporterMesh::create_shadow_mesh`, `scene/resources/3d/importer_mesh.cpp`). The renderer draws surface *i*'s depth prepass and shadows from the shadow mesh's surface *i* (`render_forward_clustered.cpp`), so a script that removes a surface from the mesh must remove it from the shadow mesh too. Otherwise the removed surface keeps casting shadows, and each surface after it is drawn with another surface's geometry. 4.7.2 drew the mismatch without an error, while on NVIDIA's fork a Bistro bottle's shifted shadow surface reached a draw without indices, which the fork refuses: `Vertex amount (169) must be a multiple of the amount of vertices required by the render primitive (3)`.

## Textures used in 3D

A texture file imports with `compress/mode` Lossless and no mipmaps, and with `detect_3d/compress_to` set to VRAM Compressed. When the renderer first draws a material that uses the texture in 3D, the editor switches it to VRAM compression with mipmaps and reimports it; a texture under a `hint_normal` uniform also gets `compress/normal_map`, which keeps only red and green (`ResourceImporterTexture::update_imports` in `editor/import/resource_importer_texture.cpp`, with the callbacks in `material_storage.cpp`). A headless import draws nothing, so its textures keep the Lossless import: the 75 textures of 4096² that Intel Sponza's materials use then take 4.7 GiB, enough on an 8 GB GPU for DLSS Ray Reconstruction to fail with `sl::eWarnOutOfVRAM`, and distant surfaces sample them without mipmaps. A tool sets the same options in the `.import` files instead. DDS files are not imported: `ResourceFormatDDS` (`modules/dds/texture_loader_dds.cpp`) loads them with the compression and mipmaps they hold.

## Reimport after editing an .import file

The editor's scan reimports a source when its `.import` file has a new modification time and a new MD5; a new time alone only refreshes the stored times (`editor/file_system/editor_file_system.cpp`). A tool can therefore change import options by writing the `.import` file and running `godot --headless --path <project> --import`.

## glTF materials

`modules/gltf/gltf_document.cpp`:

- Import converts `emissiveFactor` from linear to sRGB, Godot's storage for `emission`, and turns emission on. Export applies the same `linear_to_srgb` to the already sRGB `emission`, where `baseColorFactor` gets the correct `srgb_to_linear`, so an exported emission colour is too bright and a round trip changes it. Write emissive glTF directly rather than through `GLTFDocument` export.
- `KHR_materials_emissive_strength` is exported only when emission is on and its energy multiplier is not 1. On import it sets the energy multiplier but does not turn emission on; only `emissiveFactor` or `emissiveTexture` do.
- `alphaMode` `BLEND` imports as `TRANSPARENCY_ALPHA_DEPTH_PRE_PASS` and `MASK` as `TRANSPARENCY_ALPHA_SCISSOR`.

## FBX materials and lights

`modules/fbx/fbx_document.cpp`:

- An emission texture sets the emission colour to black and keeps the default `EMISSION_OP_ADD`, so the material emits the texture alone: `(emission + texture) · energy` (`scene/resources/material.cpp`). A material with an emission colour in the file gets emission turned on even when that colour is black.
- Transparency comes from the albedo texture's alpha: `Image.detect_alpha()` returning blend gives `TRANSPARENCY_ALPHA_DEPTH_PRE_PASS`, and bit alpha gives `TRANSPARENCY_ALPHA_SCISSOR`. A material is double-sided when the file enables its double-sided feature (`fbx_document.cpp`).
- A light's energy is the file's intensity unscaled, in whatever unit the authoring tool used, and omni and spot lights get a range of 4096. Shadows follow the light's own cast-shadows property, which the importer passes through its `GODOT_fbx_light` data.
