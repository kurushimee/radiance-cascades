---
paths:
  - "**/*.gd"
---

# GDScript style guide

## Formatting

Aim for at most 120 characters per line. A small overrun is acceptable when wrapping would make the line harder to read.

## Static typing

It is strictly required to always use static typing without exceptions. This covers variables, constants, function parameters, return types, and `for` loop variables where the type is not inferred from a typed collection. In rare cases that `Variant` genuinely needs to be used, it still needs to be specified explicitly.

Lambdas follow exactly the same rules as methods: typed parameters and a return type (`func(node: Node3D) -> void:`). The single exception: a lambda parameter the lambda does not use may stay untyped, and then its name must start with `_` (`func(_node) -> void: counter.value += 1`).

Default to explicit type declaration (`var foo: int`). Inferred typing with `:=` is allowed only when the type is obvious **at the declaration site** without looking anywhere else:

- `.new()` / a constructor: `var uniform := RDUniform.new()`, `var offset := Vector3(0.0, 1.0, 0.0)`;
- literals and built-in conversion functions whose result type is fixed: `str()`, `int()`, `float()`, `bool()`.

Do **not** use `:=` with the result of a project or engine method call (`var device := RenderingServer.get_rendering_device()`): the function may live elsewhere and its return type is not visible at the call site. Write the type out.

Engine-dictated signatures (e.g. `_get_property_list() -> Array[Dictionary]`) are used as the engine defines them.

### Collections

Arrays and Dictionaries must be typed: `var foo: Array[Node3D]`, `var bar: Dictionary[StringName, int]`.

GDScript does not support nested collection typing. When a nested collection is needed:

- **The inner collection holds POD values / strings**: use the untyped inner collection and state its content type in a comment: `var samples_by_level: Dictionary[int, Array] = {}  # Array[float]`
- **The inner collection holds structured data** (`Dictionary[K, Dictionary]`, `Array[Dictionary]` and the like): do not nest. Declare an inner `class` (or a `class_name`) for the record and type the collection with it.

## Null and validity checks

- **Any `Object`** (nodes, resources, `RefCounted`, …): `if !is_instance_valid(obj):` / `if is_instance_valid(obj):`. Do not use `obj == null`, `obj != null` or bare `if obj:` for objects.
- **POD types and strings** (`int`, `float`, `bool`, `String`, `StringName`, vectors, …): `if !value:` / `if value:` is acceptable. Remember it treats `0`, `0.0` and `""` as false; compare explicitly when those are meaningful values.

## Logical operators

Use `&&`, `||`, `!` instead of `and`, `or`, `not`.

Exception: the type-check form `x is not Type` is allowed; it reads better than `!(x is Type)`.

## Identifier naming

Always use readable, descriptive names for variables, arguments, and functions.

Prefix with `_` **only**:

- private variables used ONLY within this script;
- private functions used ONLY within this script;
- **internal hook methods** that are meant to be overridden or called by the owning framework, but must never be called directly by external systems. Subclasses override them; other code goes through the public API that invokes them.

Do **not** prefix with `_`:

- public/static variables and methods intended to be called from outside;
- enums;
- constants;
- signals;
- inner classes.

## Declaration order

Place declarations in this order from the top of the file:

1. `@tool`, `@icon`, `@static_unload`
2. `extends`
3. `class_name`
4. `## doc comment`
5. signals
6. enums
7. constants
8. static variables
9. `@onready` variables
10. `@export` variables (grouping with `@export_group` / `@export_subgroup` as the file needs)
11. remaining regular variables
12. `_static_init()`
13. remaining static methods
14. overridden built-in virtual methods, in this order:
    1. `_init()`
    2. `_enter_tree()`
    3. `_ready()`
    4. `_process()`
    5. `_physics_process()`
    6. remaining virtual methods
15. overridden custom methods
16. remaining methods
17. inner classes

Standalone setter/getter functions (`set_foo()` / `get_foo()`) have no special slot: they are ordinary methods and follow the same ordering and access rules as any other method.

## Access modifier order

Within each group of the declaration order above, put public members first, then private ones:

1. public
2. private

---

# GDScript conventions

## Custom types

When it makes sense, always prefer subclasses `class`/new external `class_name`s over bundling data within Dictionaries.

## Resource references

All resource and scene references must be exported with `@export` variables. Referencing them by path is prohibited unless strictly necessary: `load()` / `preload()` / `ResourceLoader.load()` are a last resort for a reference that cannot be an `@export` variable, and the call must be justified in a comment (`# gdstyle-ignore[load]: <reason>`, see "Automated check" below).

**Exception:** `@tool` scripts that run **only in the editor** (editor plugins, authoring tools, editor-only branches guarded by `Engine.is_editor_hint()`) are not subject to this restriction. This does not extend to `@tool` scripts that also run in the game.

It is strictly prohibited to load any external scripts by path. If a script needs to be referenced from outside, it must be assigned a unique `class_name`.

## Logging

Any logged error invalidates a scene capture, so `push_error()` is only for real defects.

## Assertions

`assert(condition, message)` is for invariants that indicate a programming error. Asserts are stripped from release builds, so never put logic with side effects inside them and never rely on them for runtime handling.

## StringName

Use `StringName` literals (`&"name"`) where they pay off: frequently compared identifiers, Dictionary keys, shader parameter names. Do not convert every string by default.

## Warning suppression

`@warning_ignore("warning_name")` is allowed where the warning is understood and intentional.

## Node visibility

Use `visible = condition` if you want the visibility to depend on a condition. Otherwise, just use `show()` and `hide()` methods instead of `visible = true` or `visible = false` respectively.

## Node creation/configuration

Whenever at all possible, register all nodes and their properties in .tscn scene files instead of instantiating and configuring them at runtime in .gd scripts:

- If you ever find yourself calling `.new()` on a `Node`-derived class and then using `add_child()` with it, double-check whether you can avoid doing this and instead create this node statically within a scene file. If you want to show this node only at a certain time, but it still otherwise doesn't benefit from dynamic creation, put it into .tscn and `.show()`/`.hide()` it.

## Children nodes

NEVER use `$` (or the identical `get_node()` syntax it resolves to) when you can use `%` instead. Give nodes unique names in their scenes to access them without relying on a specific node layout within the scene that may change.

---

# Automated check

Run `python scripts/gdscript_style_audit.py` before finishing any `.gd` change. It checks **only lines you added or changed** in uncommitted and untracked `.gd` files under `src/`. `--base main` checks everything a branch changed. `load()` is not flagged under `src/editor/`.

The checks are regex heuristics. When a flagged line is a justified exception (a last-resort `load()`, an engine-dictated signature, a false positive), suppress it with a comment on the same line or the line directly above. The reason is mandatory (a marker without one suppresses nothing), and reviewers read it:

```gdscript
# gdstyle-ignore[load]: no export slot — path comes from a save file
var scene: PackedScene = load(scene_path)
```

Rule ids: `logical-ops`, `dollar-node`, `get-node-literal`, `null-compare`, `load`, `untyped-var`, `untyped-const`, `infer-call`, `infer-collection-literal`, `infer-node-path`, `untyped-param`, `missing-return-type`, `untyped-collection`, `visible-literal`, `private-access`.

Declaration order, naming, and `.tscn`-over-runtime nodes are not checked automatically.
