"""외부 API·DB 없이 임시 폴더에서 백업 삭제와 CLI 실패 처리를 검증합니다."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from generate import generate as generator


@pytest.fixture
def fixed_today(monkeypatch):
    # UTC로는 11월 19일인 시각에도 한국 날짜는 11월 20일입니다.
    now = datetime(2026, 11, 20, 0, 30, tzinfo=ZoneInfo("Asia/Seoul"))
    monkeypatch.setattr(generator, "article_timestamp", lambda: now)


def test_cleanup_keeps_seven_days_and_removes_old_jsonl_and_png(tmp_path, fixed_today, capsys):
    old = tmp_path / "2026-11-13"
    (old / "images").mkdir(parents=True)
    (old / "articles-2026-11-13.jsonl").write_text("{}\n")
    (old / "images" / "thumbnail.png").write_bytes(b"png")
    retained = [tmp_path / f"2026-11-{day}" for day in range(14, 21)]
    future = tmp_path / "2026-11-21"
    for folder in [*retained, future]:
        folder.mkdir()

    generator.cleanup_old_outputs(tmp_path)

    assert not old.exists()
    assert all(folder.is_dir() for folder in [*retained, future])
    assert str(old) in capsys.readouterr().out
    # 정리를 재실행해도 보관 대상은 유지합니다.
    generator.cleanup_old_outputs(tmp_path)
    assert all(folder.is_dir() for folder in retained)


def test_cleanup_preserves_non_dates_files_and_symlink_targets(tmp_path, fixed_today):
    root = tmp_path / "output"
    root.mkdir()
    for name in ("notes", "2026-02-30", "2026-1-01"):
        (root / name).mkdir()
    regular_file = root / "2020-01-01"
    regular_file.write_text("keep")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "backup.jsonl").write_text("keep")
    link = root / "2020-01-02"
    link.symlink_to(outside, target_is_directory=True)

    generator.cleanup_old_outputs(root)

    assert {item.name for item in root.iterdir()} == {
        "notes", "2026-02-30", "2026-1-01", "2020-01-01", "2020-01-02", ".articles.lock"
    }
    assert regular_file.read_text() == "keep"
    assert link.is_symlink()
    assert (outside / "backup.jsonl").read_text() == "keep"


def test_cleanup_missing_output_is_noop(tmp_path):
    root = tmp_path / "missing"
    generator.cleanup_old_outputs(root)
    assert not root.exists()


@pytest.mark.parametrize("keep_days", [0, -1])
def test_cleanup_rejects_nonpositive_retention(tmp_path, keep_days):
    with pytest.raises(ValueError, match="보관 일수"):
        generator.cleanup_old_outputs(tmp_path, keep_days=keep_days)


def test_cleanup_custom_retention(tmp_path, fixed_today):
    old = tmp_path / "2026-11-19"
    today = tmp_path / "2026-11-20"
    old.mkdir()
    today.mkdir()
    generator.cleanup_old_outputs(tmp_path, keep_days=1)
    assert not old.exists()
    assert today.is_dir()


@pytest.fixture
def cli(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", [
        "generate", "--text-model", "test-text", "--image-model", "test-image",
        "--output-root", str(tmp_path),
    ])
    monkeypatch.setenv("OPENROUTER_API_KEY", "unit-test-only")
    monkeypatch.delenv("OPENROUTER_API_KEY_SECRET", raising=False)
    monkeypatch.delenv("THUMBNAIL_BUCKET", raising=False)
    return tmp_path


def test_cleanup_failure_warns_without_failing_successful_generation(monkeypatch, cli, capsys):
    saved = cli / "2026-11-20" / "articles-2026-11-20.jsonl"
    calls = []

    def generate(*args, **kwargs):
        calls.append("generate")
        return saved

    def fail_cleanup(root):
        assert root == cli
        assert calls == ["generate"]
        raise PermissionError("test cleanup denied")

    monkeypatch.setattr(generator, "generate", generate)
    monkeypatch.setattr(generator, "cleanup_old_outputs", fail_cleanup)
    assert generator.main() is None
    output = capsys.readouterr().out
    assert f"기사 1건 저장: {saved}" in output
    assert "경고: 오래된 백업 정리 실패: test cleanup denied" in output
    assert calls == ["generate"]


def test_generation_failure_exits_without_cleanup(monkeypatch, cli):
    def fail_generate(*args, **kwargs):
        raise ValueError("test generation failed")

    def unexpected_cleanup(root):
        pytest.fail("생성 실패 시에는 정리하지 않아야 합니다.")

    monkeypatch.setattr(generator, "generate", fail_generate)
    monkeypatch.setattr(generator, "cleanup_old_outputs", unexpected_cleanup)
    with pytest.raises(SystemExit) as error:
        generator.main()
    assert error.value.code == 1


@pytest.mark.parametrize("secret", ["db pass", " \tdb pass\r\n"])
def test_cli_strips_secret_password_before_generation(monkeypatch, cli, secret):
    import os
    import sys

    monkeypatch.setattr(sys, "argv", [
        *sys.argv, "--write-db", "--date", "2026-11-24",
        "--run-id", "test-secret-password",
        "--image-base-url", "https://example.com/images",
    ])
    for name, value in {
        "PGHOST": "test-db", "PGPORT": "5432", "PGDATABASE": "test-db",
        "PGUSER": "test-user", "PGPASSWORD": "old-password",
        "PGPASSWORD_SECRET": "test-secret-resource",
    }.items():
        monkeypatch.setenv(name, value)

    def read_secret(resource):
        assert resource == "test-secret-resource"
        return secret

    def generate(*args, **kwargs):
        # DB 연결에 쓰이는 환경변수를 확인하고 비밀번호 중간의 공백은 유지합니다.
        assert os.environ["PGPASSWORD"] == "db pass"
        return cli / "articles-test.jsonl"

    monkeypatch.setattr(generator, "read_secret", read_secret)
    monkeypatch.setattr(generator, "generate", generate)
    assert generator.main() is None
