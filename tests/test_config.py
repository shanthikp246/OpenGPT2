from pathlib import Path

from zero_code_platform.config import PlatformConfig


def test_example_round_trip(tmp_path: Path):
    config_path = tmp_path / "platform.yaml"
    PlatformConfig.write_example(config_path)

    loaded = PlatformConfig.load(config_path)

    assert loaded.rag is not None
    assert loaded.rag.mode == "local"
    assert loaded.fine_tune is not None
    assert loaded.fine_tune.model_output_dir.endswith("checkpoints")
