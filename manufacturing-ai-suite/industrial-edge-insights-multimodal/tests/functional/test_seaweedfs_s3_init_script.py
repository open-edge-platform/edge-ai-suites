import os
import stat
import subprocess
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "configs/seaweedfs-s3/s3-init-buckets.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _prepare_script(tmp_path: Path) -> Path:
    script_copy = tmp_path / "s3-init-buckets.sh"
    script_copy.write_text(SCRIPT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    script_copy.chmod(script_copy.stat().st_mode | stat.S_IXUSR)
    return script_copy


def _prepare_fake_bins(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "weed.log"
    exec_marker = tmp_path / "weed-exec.log"
    _write_executable(
        bin_dir / "curl",
        "#!/bin/sh\n"
        "exit 0\n",
    )
    _write_executable(
        bin_dir / "weed",
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> "{log_path}"\n'
        'case "$1 $2" in\n'
        '  -config_dir=*\\ shell)\n'
        "  cat >> \"" + str(log_path) + "\"\n"
        "  exit 0\n"
        "  ;;\n"
        "esac\n"
        f'printf "%s\\n" "$*" > "{exec_marker}"\n'
        "exit 0\n",
    )
    return log_path, exec_marker


def _base_env(bin_dir: Path, template_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "S3_STORAGE_USER": "sampleuser",
            "S3_STORAGE_PASS": "samplepass123",
            "DEFAULT_S3_BUCKETS": "bucket-one",
            "S3_BUCKET_TTL": "30m",
            "WEED_MASTER_ADDRESS": "seaweedfs-master:9333",
            "WEED_FILER_ADDRESS": "seaweedfs-filer:8888",
            "TMP_TEMPLATE_PATH": str(template_path),
        }
    )
    return env


def test_s3_init_script_uses_authenticated_weed_shell(tmp_path: Path) -> None:
    config_dir = tmp_path / "seaweedfs-config"
    config_dir.mkdir()
    template_path = config_dir / "s3_config.json.template"
    template_path.write_text('{"user":"${S3_STORAGE_USER}","pass":"${S3_STORAGE_PASS}"}', encoding="utf-8")
    script_copy = _prepare_script(tmp_path)
    log_path, exec_marker = _prepare_fake_bins(tmp_path)
    env = _base_env(tmp_path / "bin", template_path)

    subprocess.run(
        [str(script_copy), f"-config_dir={config_dir}", "s3", "-filer=seaweedfs-filer:8888", "-ip.bind=0.0.0.0", "-config=/tmp/s3_config.json"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    weed_log = log_path.read_text(encoding="utf-8")
    assert f"-config_dir={config_dir} shell -master=seaweedfs-master:9333 -filer=seaweedfs-filer:8888" in weed_log
    assert "s3.bucket.create -name=bucket-one" in weed_log
    assert "fs.configure -locationPrefix=/buckets/bucket-one/ -ttl=30m -apply" in weed_log
    assert exec_marker.exists()


def test_s3_init_script_rejects_invalid_bucket_names(tmp_path: Path) -> None:
    config_dir = tmp_path / "seaweedfs-config"
    config_dir.mkdir()
    template_path = config_dir / "s3_config.json.template"
    template_path.write_text('{"user":"${S3_STORAGE_USER}","pass":"${S3_STORAGE_PASS}"}', encoding="utf-8")
    script_copy = _prepare_script(tmp_path)
    _log_path, exec_marker = _prepare_fake_bins(tmp_path)
    env = _base_env(tmp_path / "bin", template_path)
    env["DEFAULT_S3_BUCKETS"] = "invalid bucket"

    result = subprocess.run(
        [str(script_copy), f"-config_dir={config_dir}", "s3", "-filer=seaweedfs-filer:8888", "-ip.bind=0.0.0.0", "-config=/tmp/s3_config.json"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "invalid: whitespace is not allowed" in result.stdout
    assert not exec_marker.exists()


def test_s3_init_script_uses_default_addresses_when_env_is_unset(tmp_path: Path) -> None:
    config_dir = tmp_path / "seaweedfs-config"
    config_dir.mkdir()
    template_path = config_dir / "s3_config.json.template"
    template_path.write_text('{"user":"${S3_STORAGE_USER}","pass":"${S3_STORAGE_PASS}"}', encoding="utf-8")
    script_copy = _prepare_script(tmp_path)
    log_path, exec_marker = _prepare_fake_bins(tmp_path)
    env = _base_env(tmp_path / "bin", template_path)
    env.pop("WEED_MASTER_ADDRESS")
    env.pop("WEED_FILER_ADDRESS")

    subprocess.run(
        [str(script_copy), f"-config_dir={config_dir}", "s3", "-filer=seaweedfs-filer:8888", "-ip.bind=0.0.0.0", "-config=/tmp/s3_config.json"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    weed_log = log_path.read_text(encoding="utf-8")
    assert f"-config_dir={config_dir} shell -master=seaweedfs-master:9333 -filer=seaweedfs-filer:8888" in weed_log
    assert exec_marker.exists()
