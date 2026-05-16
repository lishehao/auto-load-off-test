from __future__ import annotations

from dataclasses import dataclass

from app.application.use_cases.load_measurement import LoadMeasurementUseCase
from app.application.use_cases.load_reference import LoadReferenceUseCase
from app.application.use_cases.save_measurement import SaveMeasurementUseCase
from app.application.use_cases.settings_use_case import SettingsUseCase
from app.infrastructure.instruments.equips_factory import create_instrument_ports, resolve_visa_address
from app.infrastructure.instruments.resource_scanner import PyVisaResourceScanner
from app.infrastructure.persistence.measurement_repo_mat_csv import MatCsvMeasurementRepository
from app.infrastructure.persistence.reference_repo_mat import MatReferenceRepository
from app.infrastructure.persistence.settings_repo_json import JsonSettingsRepository
from app.presentation.tk.app_window import AppWindow
from app.presentation.tk.controller import TkController
from app.runtime.paths import AppPaths


@dataclass(slots=True)
class DesktopApp:
    window: AppWindow
    controller: TkController
    paths: AppPaths

    def run(self) -> None:
        self.controller.initialize()
        self.window.mainloop()


def build_desktop_app(paths: AppPaths | None = None) -> DesktopApp:
    app_paths = paths or AppPaths.default()
    window = AppWindow()
    vm = window.vm

    settings_repo = JsonSettingsRepository(config_path=app_paths.settings_path)
    measurement_repo = MatCsvMeasurementRepository()
    reference_repo = MatReferenceRepository()
    save_measurement_use_case = SaveMeasurementUseCase(measurement_repo)

    controller = TkController(
        window=window,
        vm=vm,
        settings_use_case=SettingsUseCase(settings_repo),
        save_measurement_use_case=save_measurement_use_case,
        load_measurement_use_case=LoadMeasurementUseCase(measurement_repo),
        load_reference_use_case=LoadReferenceUseCase(reference_repo),
        scanner=PyVisaResourceScanner(),
        ports_factory=create_instrument_ports,
        resolve_address=resolve_visa_address,
        paths=app_paths,
    )
    return DesktopApp(window=window, controller=controller, paths=app_paths)


def run_desktop_app(paths: AppPaths | None = None) -> None:
    build_desktop_app(paths=paths).run()

