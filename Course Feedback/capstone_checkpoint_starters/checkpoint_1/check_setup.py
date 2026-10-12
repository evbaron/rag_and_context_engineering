"""Check that the project is set up, and say how to fix whatever is not.

    python check_setup.py             # all checks, including one tiny chat call and one embedding call
    python check_setup.py --offline   # skip the two API calls

Every line starts with [OK], [WARN], or [FAIL]. Fix the first [FAIL], then run it again.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import platform
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIREMENTS = HERE / "requirements.txt"
CORPUS_FILES = {"wikipedia": "*.html", "papers": "*.pdf", "emails": "*.txt"}


class Checker:
    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def ok(self, message: str) -> None:
        print(f"[OK]   {message}")

    def warn(self, message: str, fix: str) -> None:
        self.warnings += 1
        print(f"[WARN] {message}\n       fix: {fix}")

    def fail(self, message: str, fix: str) -> None:
        self.failures += 1
        print(f"[FAIL] {message}\n       fix: {fix}")


def check_python(c: Checker) -> None:
    version = platform.python_version()
    if sys.version_info[:2] == (3, 12):
        c.ok(f"Python {version}")
    elif sys.version_info[:2] == (3, 11):
        c.warn(f"Python {version}; the course is tested with 3.12", "install Python 3.12 and recreate .venv with it")
    else:
        c.fail(
            f"Python {version} at {sys.executable}",
            "install Python 3.12, then recreate the environment: python3.12 -m venv .venv "
            "(Windows: py -3.12 -m venv .venv). On macOS, /usr/bin/python3 is Apple's 3.9: do not use it.",
        )


def check_virtual_environment(c: Checker) -> None:
    if sys.prefix == sys.base_prefix:
        c.fail(
            f"not inside a virtual environment (python is {sys.executable})",
            "activate it: source .venv/bin/activate (macOS/Linux) or .venv\\Scripts\\activate (Windows)",
        )
        return
    c.ok(f"virtual environment: {sys.prefix}")
    project_venv = HERE / ".venv"
    if project_venv.exists() and Path(sys.prefix).resolve() != project_venv.resolve():
        c.warn("the active environment is not this folder's .venv", "activate this folder's .venv unless that is intended")


def check_packages(c: Checker) -> None:
    pins = re.findall(r"^([A-Za-z0-9_.\-]+)==([^\s#]+)", REQUIREMENTS.read_text(encoding="utf-8"), re.M)
    missing, wrong = [], []
    for name, version in pins:
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
            continue
        if installed != version:
            wrong.append(f"{name} {installed} (needs {version})")
    if missing:
        c.fail(f"missing packages: {', '.join(missing)}", "pip install -r requirements.txt")
    if wrong:
        c.fail(f"wrong versions: {'; '.join(wrong)}", "pip install -r requirements.txt")
    if not missing and not wrong:
        c.ok(f"all {len(pins)} pinned packages installed at the right versions")


def check_ragkit(c: Checker) -> bool:
    spec = importlib.util.find_spec("ragkit")
    if spec is None or spec.origin is None:
        c.fail("ragkit cannot be imported", "in this folder, run: pip install -e .")
        return False
    location = Path(spec.origin).resolve().parent.parent
    if location != HERE:
        c.warn(f"ragkit is imported from {location}, not from this folder", "in this folder, run: pip install -e .")
    else:
        c.ok("ragkit is installed from this folder (editable install)")
    return True


def check_settings(c: Checker) -> bool:
    from ragkit import config

    if config.ENV_FILE.is_file():
        c.ok(f".env found: {config.ENV_FILE}")
    else:
        c.fail(f"no .env file in {HERE}", "copy .env.example to .env, then fill it in")

    key_ok = True
    try:
        config.api_key()
        c.ok("OPENROUTER_API_KEY is set")
    except config.SetupError:
        key_ok = False
        c.fail("OPENROUTER_API_KEY is not set", "copy .env.example to .env, then put the course key on its OPENROUTER_API_KEY line")

    try:
        scenario = config.scenario()
        c.ok(f"scenario: {scenario}")
        folder = config.corpus_dir()
        pattern = CORPUS_FILES[scenario]
        count = len(list(folder.glob(pattern)))
        if count:
            c.ok(f"corpus: {count:,} {pattern} files in {folder}")
        else:
            c.fail(f"no {pattern} files in {folder}", f"set RAG_CORPUS_DIR to the folder with the {scenario} files")
    except config.SetupError as error:
        c.fail(str(error), "edit RAG_SCENARIO and RAG_CORPUS_DIR in .env")

    try:
        work = config.work_dir()
        probe = work / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        c.ok(f"work folder (logs, reports, indexes): {work}")
    except OSError as error:
        c.fail(f"cannot write to the work folder: {error}", "set RAG_WORK_DIR in .env to a writable folder")
    return key_ok


def check_api(c: Checker) -> None:
    from langchain_openai import OpenAIEmbeddings

    from ragkit import config
    from ragkit.llm import ask, build_messages, make_llm

    try:
        _, call = ask(make_llm(), build_messages("Reply with the single word: ready"), role="setup_check")
        c.ok(f"chat model {call.model} answered in {call.latency_s:.1f} s")
    except Exception as error:
        if "402" in str(error):
            c.fail("chat call refused: the key's remaining credit is too low (OpenRouter error 402)",
                   "ask for more credit on the key, or check its usage at https://openrouter.ai/settings/keys")
        else:
            c.fail(f"chat call failed: {type(error).__name__}: {error}", "check the key, RAG_MODEL, and the network")

    try:
        embeddings = OpenAIEmbeddings(
            model=config.embedding_model(), api_key=config.api_key(), base_url=config.OPENROUTER_BASE_URL
        )
        vector = embeddings.embed_query("ready")
        c.ok(f"embedding model {config.embedding_model()} returned a vector of {len(vector)} numbers")
    except Exception as error:
        c.fail(f"embedding call failed: {type(error).__name__}: {error}", "check the key, RAG_EMBEDDING_MODEL, and the network")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the project setup.")
    parser.add_argument("--offline", action="store_true", help="skip the chat and embedding calls")
    args = parser.parse_args()

    c = Checker()
    check_python(c)
    check_virtual_environment(c)
    check_packages(c)
    key_ok = False
    if check_ragkit(c):
        key_ok = check_settings(c)
        if args.offline:
            print("[SKIP] chat and embedding calls (--offline)")
        elif key_ok:
            check_api(c)
    print()
    if c.failures:
        print(f"{c.failures} problem(s) to fix. Fix the first [FAIL] above, then run this again.")
        sys.exit(1)
    print("Setup complete." + (f" ({c.warnings} warning(s) above.)" if c.warnings else ""))


if __name__ == "__main__":
    main()
