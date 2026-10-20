# Scene import

Read in the 4.7.2-stable source; paths are relative to the engine repository.

## Import script order

`ResourceImporterScene::import` runs `_generate_meshes`, which builds the `ArrayMesh`es and unwraps UV2, before it calls the import script's `_post_import` (`editor/import/3d/resource_importer_scene.cpp`). The script therefore sees `MeshInstance3D` nodes with UV2 and the imported materials on their mesh surfaces. A node's surface override material wins over the mesh's, and glTF import leaves the overrides empty.

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
- Transparency comes from the albedo texture's alpha: `Image.detect_alpha()` returning blend gives `TRANSPARENCY_ALPHA_DEPTH_PRE_PASS`, and bit alpha gives `TRANSPARENCY_ALPHA_SCISSOR`. A material is double-sided only when the file says so explicitly.
- A light's energy is the file's intensity unscaled, in whatever unit the authoring tool used, and omni and spot lights get a range of 4096. Shadows are on only when the file's Godot extension data asks for them.
