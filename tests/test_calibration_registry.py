from pathlib import Path
from renca.calibration import CalibrationRecord, CalibrationRegistry, calibration_status, vimp_fingerprint
from renca.models import VimpSpec

def test_gate_requires_exact_binding_and_formal_evidence() -> None:
    spec=VimpSpec(); record=CalibrationRecord(scenario_family="linear",sample_size=300,inference_folds=5,vimp_fingerprint=vimp_fingerprint(spec),critical_value=-2.,calibration_replications=5000,evaluation_replications=5000,empirical_rejection_rate=.04,upper_rejection_bound=.049,status="validated")
    registry=CalibrationRegistry(records=[record])
    assert calibration_status(registry,"linear",300,5,spec)=="calibrated_success"
    assert calibration_status(registry,"bounded",300,5,spec)=="uncalibrated"
    registry.records[0].upper_rejection_bound=.06
    assert calibration_status(registry,"linear",300,5,spec)=="calibration_failed"
