class_name CameraRays
## The vectors from which cshd_camera.glslinc builds the ray through a pixel, so traced rays meet the surfaces the
## raster draws at pixel centres.


## The camera's position, its right and up vectors scaled to the edges of the view, and its forward vector, each
## padded to four floats.
static func basis(camera: Camera3D) -> PackedFloat32Array:
	var projection: Projection = camera.get_camera_projection()
	var transform: Transform3D = camera.global_transform
	var right: Vector3 = transform.basis.x / projection.x.x
	var up: Vector3 = transform.basis.y / projection.y.y
	var forward: Vector3 = -transform.basis.z
	return PackedFloat32Array([
		transform.origin.x, transform.origin.y, transform.origin.z, 0.0,
		right.x, right.y, right.z, 0.0,
		up.x, up.y, up.z, 0.0,
		forward.x, forward.y, forward.z, 0.0,
	])
