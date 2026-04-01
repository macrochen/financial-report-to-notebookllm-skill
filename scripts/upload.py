#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upload PDF files to NotebookLM using notebooklm-py CLI

Prerequisites:
  pip install notebooklm-py playwright
  playwright install chromium
  notebooklm login  # Authenticate first
"""

import sys
import os
import subprocess
import json
import shutil
import re
import time
import asyncio
import tempfile

# Ensure virtual environment's bin is in PATH
venv_bin = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv", "bin")
if os.path.exists(venv_bin):
    os.environ["PATH"] = venv_bin + os.pathsep + os.environ.get("PATH", "")

VENV_PYTHON = os.path.join(venv_bin, "python")
NOTEBOOKLM_BIN = os.path.join(venv_bin, "notebooklm")
SUMMARY_FALLBACK_TIMEOUT = 120.0
DEFAULT_API_TIMEOUT = 120.0


def python_api_enabled() -> bool:
    """Return whether Python API should be used as the primary implementation."""
    return os.environ.get("FINANCIAL_REPORT_NOTEBOOKLM_FORCE_CLI", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }


def _serialize_notebook(notebook) -> dict:
    """Convert a NotebookLM notebook object to the legacy dict shape."""
    return {
        "id": notebook.id,
        "title": notebook.title,
        "created_at": notebook.created_at.isoformat() if getattr(notebook, "created_at", None) else None,
        "is_owner": getattr(notebook, "is_owner", None),
    }


def _serialize_source(source, index: int | None = None) -> dict:
    """Convert a NotebookLM source object to the legacy dict shape."""
    return {
        "index": index,
        "id": source.id,
        "title": source.title,
        "type": str(source.kind),
        "url": source.url,
        "status": getattr(source, "status_str", str(source.status) if getattr(source, "status", None) is not None else None),
        "status_id": int(source.status) if getattr(source, "status", None) is not None else None,
        "created_at": source.created_at.isoformat() if getattr(source, "created_at", None) else None,
    }


def _serialize_artifact(artifact) -> dict:
    """Convert a NotebookLM artifact object to a JSON-friendly dict."""
    return {
        "id": artifact.id,
        "title": artifact.title,
        "kind": str(artifact.kind),
        "status": artifact.status_str,
        "status_id": artifact.status,
        "created_at": artifact.created_at.isoformat() if getattr(artifact, "created_at", None) else None,
        "url": artifact.url,
        "report_subtype": getattr(artifact, "report_subtype", None),
    }


def _run_api(coro_func, timeout: float = DEFAULT_API_TIMEOUT):
    """Run one async NotebookLM API call and return its result."""
    async def _runner():
        from notebooklm.client import NotebookLMClient

        async with await NotebookLMClient.from_storage(timeout=timeout) as client:
            return await coro_func(client)

    return asyncio.run(_runner())

def check_notebooklm_installed() -> bool:
    """Check if notebooklm CLI is installed"""
    if os.path.exists(VENV_PYTHON):
        return True
    if os.path.exists(NOTEBOOKLM_BIN):
        return True
    return shutil.which("notebooklm") is not None


def run_notebooklm_command(args: list, timeout: int = 120) -> tuple:
    """Run notebooklm command and return (success, output)"""
    if os.path.exists(VENV_PYTHON):
        cmd = [VENV_PYTHON, "-m", "notebooklm.notebooklm_cli"]
    elif os.path.exists(NOTEBOOKLM_BIN):
        cmd = [NOTEBOOKLM_BIN]
    else:
        cmd = ["notebooklm"]
    started_at = time.time()
    command_text = " ".join(cmd + args)

    try:
        result = subprocess.run(
            cmd + args, capture_output=True, text=True, timeout=timeout
        )
        elapsed = time.time() - started_at
        output = result.stdout + result.stderr
        diag = f"[command] {command_text}\n[elapsed] {elapsed:.2f}s\n"
        return result.returncode == 0, diag + output
    except subprocess.TimeoutExpired as e:
        elapsed = time.time() - started_at
        partial_output = (e.stdout or "") + (e.stderr or "")
        return (
            False,
            (
                f"[command] {command_text}\n"
                f"[elapsed] {elapsed:.2f}s\n"
                f"[timeout] {timeout}s\n"
                "NotebookLM command timed out.\n\n"
                f"{partial_output}"
            ),
        )
    except Exception as e:
        elapsed = time.time() - started_at
        return False, (
            f"[command] {command_text}\n"
            f"[elapsed] {elapsed:.2f}s\n"
            f"[error] {e}"
        )


def extract_uuid(text: str) -> str:
    """Extract the first UUID from command output."""
    match = re.search(r"[a-f0-9-]{36}", text or "")
    return match.group(0) if match else None


def extract_json_object(text: str):
    """Extract the outermost JSON object from command output."""
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def normalize_source_name(name: str) -> str:
    """Normalize source title/file names for comparison."""
    if not name:
        return ""
    base = os.path.basename(name.strip()).lower()
    for suffix in (".md", ".pdf", ".txt", ".docx", ".html"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break

    if "latest_market_snapshot" in base:
        return "latest_market_snapshot"
    if "recent_developments" in base:
        return "recent_developments"

    cn_q1 = re.search(r"(?P<code>\d{6}).*?(?P<year>20\d{2}).*?(第一季度|一季度|q1)", base)
    if cn_q1:
        return f"cn_{cn_q1.group('code')}_{cn_q1.group('year')}_q1"

    cn_semi = re.search(r"(?P<code>\d{6}).*?(?P<year>20\d{2}).*?(半年度报告|中期报告|semi)", base)
    if cn_semi:
        return f"cn_{cn_semi.group('code')}_{cn_semi.group('year')}_semi"

    cn_q3 = re.search(r"(?P<code>\d{6}).*?(?P<year>20\d{2}).*?(第三季度|三季度|q3)", base)
    if cn_q3:
        return f"cn_{cn_q3.group('code')}_{cn_q3.group('year')}_q3"

    cn_annual = re.search(r"(?P<code>\d{6}).*?(?P<year>20\d{2}).*?(年度报告|年年度报告|年报|annual)", base)
    if cn_annual:
        return f"cn_{cn_annual.group('code')}_{cn_annual.group('year')}_annual"

    return base


def prepare_upload_file(file_path: str) -> tuple[str, str | None]:
    """Stage a short ASCII filename for NotebookLM uploads when needed."""
    normalized_name = normalize_source_name(file_path) or "source"
    ext = os.path.splitext(file_path)[1].lower() or ".txt"
    basename = os.path.basename(file_path)
    needs_alias = len(basename) > 100 or not basename.isascii()

    if not needs_alias:
        return file_path, None

    staged_dir = tempfile.mkdtemp(prefix="notebooklm-upload-")
    staged_path = os.path.join(staged_dir, f"{normalized_name}{ext}")
    shutil.copyfile(file_path, staged_path)
    return staged_path, staged_dir


def create_notebook(title: str) -> str:
    """Create a new NotebookLM notebook, returns notebook ID or None"""
    print(f"📚 Creating notebook: {title}")

    if python_api_enabled():
        try:
            notebook = _run_api(lambda client: client.notebooks.create(title))
            print(f"✅ Created notebook via Python API: {notebook.id}")
            return notebook.id
        except Exception as e:
            print(f"⚠️ Python API create failed, falling back to CLI: {e}", file=sys.stderr)

    success, output = run_notebooklm_command(["create", title])

    if not success:
        print(f"❌ Failed to create notebook: {output}", file=sys.stderr)
        return None

    # Parse output to find notebook ID
    # Output format: "Created notebook: <title> (ID: <id>)" or similar
    for line in output.split("\n"):
        if "ID:" in line or "id:" in line:
            notebook_id = extract_uuid(line)
            if notebook_id:
                print(f"✅ Created notebook: {notebook_id}")
                return notebook_id
        notebook_id = extract_uuid(line)
        if notebook_id:
            print(f"✅ Created notebook: {notebook_id}")
            return notebook_id

    # Fallback: return trimmed output
    print(f"⚠️ Output: {output}")
    return output.strip().split()[-1] if output.strip() else None


def list_notebooks() -> tuple[bool, list]:
    """List all notebooks in the current account."""
    if python_api_enabled():
        try:
            notebooks = _run_api(lambda client: client.notebooks.list())
            rows = []
            for index, notebook in enumerate(notebooks, start=1):
                row = _serialize_notebook(notebook)
                row["index"] = index
                rows.append(row)
            return True, rows
        except Exception:
            pass

    success, output = run_notebooklm_command(["list", "--json"])
    if not success:
        return False, []

    data = extract_json_object(output)
    if not data:
        return False, []
    return True, data.get("notebooks", [])


def rename_notebook(notebook_id: str, new_title: str) -> tuple[bool, str]:
    """Rename one notebook."""
    if python_api_enabled():
        try:
            notebook = _run_api(lambda client: client.notebooks.rename(notebook_id, new_title))
            return True, json.dumps(_serialize_notebook(notebook), ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Python API rename failed, falling back to CLI: {e}", file=sys.stderr)
    return run_notebooklm_command(["rename", "--notebook", notebook_id, new_title])


def upload_source(notebook_id: str, file_path: str) -> tuple[bool, str]:
    """Upload a file as source to a notebook and return source ID when possible."""
    filename = os.path.basename(file_path)
    print(f"📤 Uploading: {filename}")

    staged_path, staged_dir = prepare_upload_file(file_path)
    last_output = ""
    try:
        for attempt in range(1, 4):
            cli_attempted = False
            if python_api_enabled():
                try:
                    source = _run_api(
                        lambda client: client.sources.add_file(
                            notebook_id,
                            staged_path,
                            wait=False,
                        )
                    )
                    print(f"   ✅ Uploaded via Python API")
                    if source.id:
                        print(f"   🆔 Source ID: {source.id}")
                    return True, source.id
                except Exception as e:
                    last_output = f"[python_api] {e}"
                    print(f"   ⚠️ Python API upload attempt {attempt}/3 failed", file=sys.stderr)
            if not python_api_enabled() or last_output:
                success, output = run_notebooklm_command(
                    ["source", "add", staged_path, "--notebook", notebook_id]
                )
                cli_attempted = True
                last_output = output
                if success:
                    print(f"   ✅ Uploaded successfully via CLI fallback")
                    source_id = extract_uuid(output)
                    if source_id:
                        print(f"   🆔 Source ID: {source_id}")
                    return True, source_id
                print(f"   ⚠️ CLI upload attempt {attempt}/3 failed", file=sys.stderr)
            if python_api_enabled() and not cli_attempted and not last_output:
                last_output = "Upload did not complete and no CLI fallback was attempted"
            if attempt < 3:
                time.sleep(5)
    finally:
        if staged_dir:
            shutil.rmtree(staged_dir, ignore_errors=True)

    print(f"   ❌ Failed: {last_output}", file=sys.stderr)
    return False, None


def upload_all_sources(notebook_id: str, files: list) -> dict:
    """Upload multiple files to a notebook"""
    results = {"success": [], "failed": [], "source_ids": []}

    for file_path in files:
        ok, source_id = upload_source(notebook_id, file_path)
        if ok:
            results["success"].append(file_path)
            if source_id:
                results["source_ids"].append({"file": file_path, "source_id": source_id})
        else:
            results["failed"].append(file_path)

    return results


def list_sources(notebook_id: str) -> tuple[bool, list]:
    """List all sources in a notebook as structured data."""
    try:
        from notebooklm.client import NotebookLMClient
    except Exception:
        NotebookLMClient = None

    if NotebookLMClient is not None and python_api_enabled():
        async def _list_sources() -> tuple[bool, list]:
            async with await NotebookLMClient.from_storage(timeout=SUMMARY_FALLBACK_TIMEOUT) as client:
                sources = await client.sources.list(notebook_id)
                rows = []
                for index, source in enumerate(sources, start=1):
                    rows.append(_serialize_source(source, index=index))
                return True, rows

        try:
            return asyncio.run(_list_sources())
        except Exception:
            pass

    success, output = run_notebooklm_command(["source", "list", "--notebook", notebook_id, "--json"])
    data = extract_json_object(output) if success else None
    if data:
        return True, data.get("sources", [])
    return False, []


def delete_source(notebook_id: str, source_id: str) -> tuple[bool, str]:
    """Delete one source from a notebook."""
    if python_api_enabled():
        try:
            _run_api(lambda client: client.sources.delete(notebook_id, source_id))
            return True, source_id
        except Exception as e:
            print(f"⚠️ Python API delete failed, falling back to CLI: {e}", file=sys.stderr)
    return run_notebooklm_command(["source", "delete", source_id, "--notebook", notebook_id, "--yes"])


def get_existing_source_map(notebook_id: str) -> tuple[bool, dict]:
    """Build a lookup map for existing notebook sources by normalized title."""
    success, sources = list_sources(notebook_id)
    if not success:
        return False, {}

    source_map = {}
    for source in sources:
        normalized = normalize_source_name(source.get("title", ""))
        if not normalized:
            continue
        source_map.setdefault(normalized, []).append(source)
    return True, source_map


def remove_matching_sources(notebook_id: str, match_names: list[str]) -> tuple[bool, list]:
    """Delete notebook sources whose normalized titles match any provided name."""
    ok, source_map = get_existing_source_map(notebook_id)
    if not ok:
        return False, []

    deleted = []
    wanted = {normalize_source_name(name) for name in match_names if name}

    for normalized in wanted:
        for source in source_map.get(normalized, []):
            source_id = source.get("id")
            if not source_id:
                continue
            success, _ = delete_source(notebook_id, source_id)
            if success:
                deleted.append(source_id)

    return True, deleted


def wait_for_sources(notebook_id: str, source_ids: list, timeout: int = 300) -> dict:
    """Wait for uploaded sources to finish processing."""
    results = {"ready": [], "failed": []}

    source_id_list = [
        item["source_id"] if isinstance(item, dict) else item
        for item in source_ids
    ]
    if python_api_enabled():
        try:
            ready_sources = _run_api(
                lambda client: client.sources.wait_for_sources(
                    notebook_id,
                    source_id_list,
                    timeout=float(timeout),
                ),
                timeout=float(timeout) + 30.0,
            )
            for source in ready_sources:
                results["ready"].append(
                    {
                        "source_id": source.id,
                        "output": json.dumps(_serialize_source(source), ensure_ascii=False),
                    }
                )
                print(f"   ✅ Source ready: {source.id}")
            results = verify_sources_ready(notebook_id, source_id_list, timeout=timeout)
            if not results["failed"]:
                return results
            print("⚠️ Source post-wait verification found pending items, falling back to CLI polling.", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ Python API wait failed, falling back to CLI: {e}", file=sys.stderr)

    for source_id in source_id_list:
        success, output = run_notebooklm_command(
            ["source", "wait", source_id, "--notebook", notebook_id, "--timeout", str(timeout), "--json"]
        )
        if success:
            results["ready"].append({"source_id": source_id, "output": output})
            print(f"   ✅ Source ready: {source_id}")
        else:
            results["failed"].append({"source_id": source_id, "output": output})
            print(f"   ⚠️ Source not ready: {source_id}", file=sys.stderr)

    return results


def verify_sources_ready(notebook_id: str, source_ids: list, timeout: int = 180, settle_seconds: int = 5) -> dict:
    """Poll source metadata until every uploaded source reports a ready state."""
    started_at = time.time()
    wanted_ids = {
        item["source_id"] if isinstance(item, dict) else item
        for item in source_ids
        if item
    }
    results = {"ready": [], "failed": []}
    seen_incomplete = False

    while time.time() - started_at <= timeout:
        ok, sources = list_sources(notebook_id)
        if ok and sources:
            ready = []
            pending = []
            indexed = {source.get("id"): source for source in sources if source.get("id")}
            for source_id in wanted_ids:
                source = indexed.get(source_id)
                status_id = source.get("status_id") if source else None
                if status_id == 2:
                    ready.append(source)
                else:
                    pending.append(
                        {
                            "source_id": source_id,
                            "status_id": status_id,
                            "status": source.get("status") if source else "missing",
                        }
                    )

            if not pending:
                if seen_incomplete and settle_seconds > 0:
                    print(f"   ⏳ Sources look ready; waiting {settle_seconds}s for NotebookLM to settle...")
                    time.sleep(settle_seconds)
                results["ready"] = [
                    {
                        "source_id": source["id"],
                        "output": json.dumps(source, ensure_ascii=False),
                    }
                    for source in ready
                ]
                return results

            seen_incomplete = True
            print(
                "   ⏳ Waiting for source processing: "
                + ", ".join(
                    f"{item['source_id']}={item['status'] or item['status_id']}"
                    for item in pending
                )
            )
        else:
            seen_incomplete = True
            print("   ⏳ Waiting for source list to become readable...")

        time.sleep(3)

    results["failed"] = [{"source_id": source_id, "output": "Timed out waiting for ready state"} for source_id in wanted_ids]
    return results


def get_notebook_summary(notebook_id: str, include_topics: bool = True) -> tuple[bool, str]:
    """Fetch AI summary from NotebookLM."""
    if python_api_enabled():
        try:
            async def _fetch_summary_with_api(client):
                description = await client.notebooks.get_description(notebook_id)
                parts = []
                if description.summary:
                    parts.append("Summary:\n" + description.summary)
                if include_topics and description.suggested_topics:
                    topic_lines = ["", "Suggested Topics:"]
                    for index, topic in enumerate(description.suggested_topics, start=1):
                        topic_lines.append(f"{index}. {topic.question}")
                    parts.append("\n".join(topic_lines))
                return "\n\n".join(parts) if parts else "No summary available"

            return True, _run_api(_fetch_summary_with_api)
        except Exception as e:
            print(f"⚠️ Python API summary failed, falling back to CLI: {e}", file=sys.stderr)

    args = ["summary", "--notebook", notebook_id]
    if include_topics:
        args.append("--topics")
    success, output = run_notebooklm_command(args)
    if success and "No summary available" not in output:
        return success, output

    should_fallback = (
        "Connection timed out calling SUMMARIZE" in output
        or "No summary available" in output
    )
    if not should_fallback:
        return success, output

    try:
        from notebooklm.client import NotebookLMClient
    except Exception as e:
        return False, output + f"\n[fallback_error] Failed to import notebooklm client: {e}"

    async def _fetch_summary() -> tuple[bool, str]:
        async with await NotebookLMClient.from_storage(timeout=SUMMARY_FALLBACK_TIMEOUT) as client:
            description = await client.notebooks.get_description(notebook_id)
            parts = []
            if description.summary:
                parts.append("Summary:\n" + description.summary)
            if include_topics and description.suggested_topics:
                topic_lines = ["", "Suggested Topics:"]
                for index, topic in enumerate(description.suggested_topics, start=1):
                    topic_lines.append(f"{index}. {topic.question}")
                parts.append("\n".join(topic_lines))
            if not parts:
                return True, "No summary available"
            return True, "\n\n".join(parts)

    try:
        return asyncio.run(_fetch_summary())
    except Exception as e:
        return False, output + f"\n[fallback_error] Python API summary fallback failed: {e}"


def ask_notebook_question(notebook_id: str, question: str, new_conversation: bool = True) -> tuple[bool, str]:
    """Ask one question and return the raw answer."""
    if python_api_enabled():
        try:
            result = _run_api(lambda client: client.chat.ask(notebook_id, question), timeout=300.0)
            return True, result.answer
        except Exception as e:
            print(f"⚠️ Python API ask failed, falling back to CLI: {e}", file=sys.stderr)

    args = ["ask", "--notebook", notebook_id]
    if new_conversation:
        args.append("--new")
    args.append(question)
    success, output = run_notebooklm_command(args)
    if success:
        return success, output

    should_fallback = any(
        marker in output
        for marker in (
            "Chat request failed",
            "Server disconnected without sending a response",
            "Connection timed out",
        )
    )
    if not should_fallback:
        return success, output

    try:
        from notebooklm.client import NotebookLMClient
    except Exception as e:
        return False, output + f"\n[fallback_error] Failed to import notebooklm client: {e}"

    async def _ask_via_python_api() -> tuple[bool, str]:
        async with await NotebookLMClient.from_storage(timeout=SUMMARY_FALLBACK_TIMEOUT) as client:
            result = await client.chat.ask(notebook_id, question)
            return True, result.answer

    try:
        return asyncio.run(_ask_via_python_api())
    except Exception as e:
        return False, output + f"\n[fallback_error] Python API ask fallback failed: {e}"


def list_artifacts(notebook_id: str, artifact_type: str = "all") -> tuple[bool, list, str]:
    """List notebook artifacts and return structured data when available."""
    if python_api_enabled():
        try:
            artifacts = _run_api(lambda client: client.artifacts.list(notebook_id))
            if artifact_type and artifact_type != "all":
                artifacts = [artifact for artifact in artifacts if str(artifact.kind) == artifact_type]
            rows = [_serialize_artifact(artifact) for artifact in artifacts]
            return True, rows, json.dumps({"artifacts": rows}, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Python API artifact listing failed, falling back to CLI: {e}", file=sys.stderr)

    args = ["artifact", "list", "--notebook", notebook_id, "--json"]
    if artifact_type and artifact_type != "all":
        args.extend(["--type", artifact_type])

    success, output = run_notebooklm_command(args)
    if not success:
        return False, [], output

    data = extract_json_object(output)
    if not data:
        return False, [], output
    return True, data.get("artifacts", []), output


def get_conversation_history(notebook_id: str, limit: int = 20) -> tuple[bool, str]:
    """Fetch recent NotebookLM conversation history as raw text."""
    if python_api_enabled():
        try:
            history = _run_api(lambda client: client.chat.get_history(notebook_id, limit=limit))
            return True, json.dumps(history, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Python API history failed, falling back to CLI: {e}", file=sys.stderr)
    args = ["history", "--notebook", notebook_id, "--limit", str(limit)]
    return run_notebooklm_command(args)


def generate_report(notebook_id: str, description: str = None, report_format: str = "briefing-doc") -> tuple:
    """Generate a NotebookLM report artifact."""
    if python_api_enabled():
        try:
            async def _generate_report_api(client):
                from notebooklm.rpc import ReportFormat

                if description:
                    status = await client.artifacts.generate_report(
                        notebook_id,
                        report_format=ReportFormat.CUSTOM,
                        custom_prompt=description,
                        language="zh-Hans",
                    )
                else:
                    status = await client.artifacts.generate_report(
                        notebook_id,
                        report_format=ReportFormat.BRIEFING_DOC,
                        language="zh-Hans",
                    )
                completed = await client.artifacts.wait_for_completion(notebook_id, status.task_id, timeout=900.0)
                return completed

            status = _run_api(_generate_report_api, timeout=960.0)
            output = json.dumps(
                {
                    "task_id": status.task_id,
                    "status": status.status,
                    "url": status.url,
                    "error": status.error,
                    "error_code": status.error_code,
                    "metadata": status.metadata,
                },
                ensure_ascii=False,
                indent=2,
            )
            return status.is_complete, output, status.task_id
        except Exception as e:
            print(f"⚠️ Python API report generation failed, falling back to CLI: {e}", file=sys.stderr)

    args = ["generate", "report", "--notebook", notebook_id, "--format", report_format, "--wait", "--json"]
    if description:
        args.append(description)
    success, output = run_notebooklm_command(args, timeout=900)
    artifact_id = extract_uuid(output)
    return success, output, artifact_id


def download_report(notebook_id: str, output_path: str, artifact_id: str = None) -> tuple[bool, str]:
    """Download the latest or specified report as markdown."""
    if python_api_enabled():
        try:
            downloaded_path = _run_api(
                lambda client: client.artifacts.download_report(
                    notebook_id,
                    output_path,
                    artifact_id=artifact_id,
                ),
                timeout=300.0,
            )
            return True, downloaded_path
        except Exception as e:
            print(f"⚠️ Python API report download failed, falling back to CLI: {e}", file=sys.stderr)

    args = ["download", "report", output_path, "--notebook", notebook_id, "--force"]
    if artifact_id:
        args.extend(["--artifact", artifact_id])
    else:
        args.append("--latest")
    return run_notebooklm_command(args)


def cleanup_temp_files(files: list, temp_dir: str = None):
    """Remove temporary files after upload"""
    for f in files:
        try:
            os.remove(f)
        except Exception:
            pass

    if temp_dir and (temp_dir.startswith("/var/folders") or "/tmp/" in temp_dir):
        try:
            shutil.rmtree(temp_dir)
            print(f"🧹 Cleaned up temp directory: {temp_dir}")
        except Exception:
            pass


def configure_notebook(notebook_id: str, prompt_file: str) -> bool:
    """Configure notebook with custom prompt"""
    if not os.path.exists(prompt_file):
        print(f"⚠️ Prompt file not found: {prompt_file}")
        return False

    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            prompt = f.read()
    except Exception as e:
        print(f"❌ Error reading prompt file: {e}")
        return False

    print(f"⚙️ Configuring notebook with custom prompt...")
    last_output = ""
    for attempt in range(1, 4):
        if python_api_enabled():
            try:
                async def _configure(client):
                    from notebooklm.rpc import ChatGoal, ChatResponseLength

                    await client.chat.configure(
                        notebook_id,
                        goal=ChatGoal.CUSTOM,
                        response_length=ChatResponseLength.LONGER,
                        custom_prompt=prompt,
                    )

                _run_api(_configure)
                print(f"   ✅ Configuration successful via Python API")
                return True
            except Exception as e:
                last_output = f"[python_api] {e}"
                print(f"   ⚠️ Configure attempt {attempt}/3 failed in Python API", file=sys.stderr)
        success, output = run_notebooklm_command(
            [
                "configure",
                "--notebook",
                notebook_id,
                "--persona",
                prompt,
                "--response-length",
                "longer",
            ]
        )
        last_output = output
        if success:
            print(f"   ✅ Configuration successful via CLI fallback")
            return True
        if attempt < 3:
            time.sleep(5)

    print(f"   ❌ Configuration failed: {last_output}", file=sys.stderr)
    return False


def main():
    """Main entry point"""
    if len(sys.argv) < 3:
        print("Usage: python upload.py <notebook_title> <pdf_file1> [pdf_file2] ...")
        print("       python upload.py <notebook_title> --json <json_file>")
        print("")
        print("The JSON file should contain output from download.py")
        sys.exit(1)

    # Check notebooklm is installed
    if not check_notebooklm_installed():
        print("❌ NotebookLM CLI not found!", file=sys.stderr)
        print("Install with: pip install notebooklm-py playwright")
        print("Then: playwright install chromium")
        print("Then authenticate with: notebooklm login")
        sys.exit(1)

    notebook_title = sys.argv[1]

    # Handle JSON input from download.py
    if sys.argv[2] == "--json":
        json_file = sys.argv[3]
        with open(json_file, "r") as f:
            data = json.load(f)
        files = data.get("files", [])
        temp_dir = data.get("output_dir")
        notebook_title = f"{data.get('stock_name', notebook_title)} 财务报告"
    else:
        files = sys.argv[2:]
        temp_dir = None

    if not files:
        print("❌ No files to upload", file=sys.stderr)
        sys.exit(1)

    print(f"📁 Files to upload: {len(files)}")

    # Create notebook
    notebook_id = create_notebook(notebook_title)
    if not notebook_id:
        sys.exit(1)

    # Upload all files
    results = upload_all_sources(notebook_id, files)

    # Summary
    print(f"\n{'=' * 50}")
    print(f"✅ Uploaded: {len(results['success'])} files")
    if results["failed"]:
        print(f"❌ Failed: {len(results['failed'])} files")
    print(f"📚 Notebook: {notebook_title}")
    print(f"🆔 ID: {notebook_id}")

    # Cleanup temp files
    if temp_dir:
        cleanup_temp_files(files, temp_dir)

    # Output JSON result
    result = {
        "notebook_id": notebook_id,
        "notebook_title": notebook_title,
        "uploaded": len(results["success"]),
        "failed": len(results["failed"]),
    }
    print("\n---JSON_OUTPUT---")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
