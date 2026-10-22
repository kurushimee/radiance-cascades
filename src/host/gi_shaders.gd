class_name GIShaders
extends Resource
## The shaders the GI dispatches, kept in one resource so that a scene links them all at once.

@export var triangles: RDShaderFile = null
@export var capture: RDShaderFile = null
@export var capture_samples: RDShaderFile = null
@export var probe_classify: RDShaderFile = null
@export var probe_map: RDShaderFile = null
@export var probe_groups: RDShaderFile = null
@export var probe_data: RDShaderFile = null
@export var atlas_view: RDShaderFile = null
@export var texel_view: RDShaderFile = null
@export var light_visibility: RDShaderFile = null
@export var direct: RDShaderFile = null
@export var direct_view: RDShaderFile = null
@export var sky_table: RDShaderFile = null
