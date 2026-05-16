# Extending The Application

This project is intentionally structured around extension seams rather than direct imports between every layer.

## Composition Root

`src/app/bootstrap.py` is the desktop composition root. It wires:

- repositories
- use cases
- instrument scanner
- instrument port factory
- address resolver
- Tk controller
- runtime paths

`src/main.py` should stay thin. If the app later gains CLI, scripted, or simulated run modes, add a new composition function instead of pushing more wiring into UI classes.

## Runtime Paths

`AppPaths` in `src/app/runtime/paths.py` centralizes the repo/runtime directories:

- `__config__/settings.json`
- `__data__/`
- `__data__/measurement/`

Use `AppPaths` instead of recomputing `Path(__file__).parents[...]` in new code.

## Adding A New Instrument

1. Add or verify the model label in `src/app/shared/mapping.py`.
2. Add the vendor driver mapping in `src/equips.py` only if the low-level SCPI behavior is known.
3. Prefer adding behavior through `app.infrastructure.instruments` adapters rather than calling `equips.py` from UI or use cases.
4. Keep `AwgPort` / `OscPort` as the application contract.
5. Add hardware-free tests with fake ports before doing live bench validation.

## Adding A New Persistence Format

Keep use cases depending on repository ports. Format-specific logic belongs under `app.infrastructure.persistence`.

For a new measurement format:

1. Add a loader/exporter implementation in infrastructure.
2. Keep `SweepResult` and `AppSettings` as the domain boundary.
3. Add round-trip tests with temporary directories.
4. Do not put file dialogs or Tk concerns in persistence code.

## Adding A New UI Field

New user-facing sweep/settings fields usually touch these files:

- `domain/models.py`
- `domain/validators.py`
- `infrastructure/persistence/settings_serializer.py`
- `infrastructure/persistence/settings_defaults.py`
- `presentation/tk/view_model.py`
- `presentation/tk/control_panel.py`
- `presentation/tk/mapper.py`
- tests for serializer and mapping behavior

If a field changes instrument behavior, add coverage at the application service or use-case level with fake ports.

## Boundary Tests

`tests/test_architecture_boundaries.py` prevents the main layering rules from drifting:

- domain stays pure
- application does not import presentation or infrastructure
- presentation does not import infrastructure

Treat failures in those tests as design feedback, not just lint failures.
