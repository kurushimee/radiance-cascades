class_name CascadeLayout
## The cascades' layout (design/cascades.md#layout): how many world cascades a scene gets, and the world cascades'
## direction bins, an equal-area cylindrical map of 2m azimuth by m height bins turned by a fixed rotation.

## Cascade 0's interval in texel spacings, at 16 bins.
const T0_SPACINGS: float = 1.6
## m of world cascade 0; cascade k has m · 2^k.
const BINS_PER_SIDE: int = 4
## The lab's generic_rotation(3), so that no bin lines up with the scene's axes: it turns a bin's map direction into
## the world, and cshd_directions.glslinc holds the same matrix.
const ROTATION: Basis = Basis(Vector3(0.69724373, -0.193968391, -0.690092345),
		Vector3(-0.705504985, -0.356164345, -0.612706843), Vector3(-0.126940528, 0.914069594, -0.385179023))


## The smallest cascade count that puts the top cascade's start inside the scene's diameter.
static func top_cascade(diameter: float, texel_size: float) -> int:
	return maxi(ceili(log(diameter / (T0_SPACINGS * texel_size)) / log(4.0)), 1)


static func bins_per_side(cascade: int) -> int:
	return BINS_PER_SIDE << cascade


## The world direction at map coordinates `cell`, in [0, 2m) × [0, m) for m bins per side.
static func direction(cell: Vector2, bins_per_side: int) -> Vector3:
	var azimuth: float = cell.x * PI / bins_per_side
	var height: float = cell.y * 2.0 / bins_per_side - 1.0
	var radius: float = sqrt(maxf(1.0 - height * height, 0.0))
	return ROTATION * Vector3(radius * cos(azimuth), radius * sin(azimuth), height)
