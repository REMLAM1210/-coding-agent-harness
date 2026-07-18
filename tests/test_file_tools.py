import os
import tempfile
from harness.models import Action, Workspace
from harness.tools.file_tools import ReadFileTool, WriteFileTool, ListFilesTool


def test_write_then_read():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        wt = WriteFileTool()
        rt = ReadFileTool()
        w_result = wt.execute(Action(type="WriteFile", args={"path": "foo.py", "content": "print('hi')"}), ws)
        assert w_result.success
        r_result = rt.execute(Action(type="ReadFile", args={"path": "foo.py"}), ws)
        assert r_result.success
        assert r_result.output == "print('hi')"


def test_read_nonexistent():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        rt = ReadFileTool()
        result = rt.execute(Action(type="ReadFile", args={"path": "nope.py"}), ws)
        assert result.success is False
        assert "not found" in result.error.lower()


def test_path_traversal_blocked():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        rt = ReadFileTool()
        result = rt.execute(Action(type="ReadFile", args={"path": "../../../etc/passwd"}), ws)
        assert result.success is False
        assert "traversal" in result.error.lower() or "outside" in result.error.lower()


def test_list_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        wt = WriteFileTool()
        wt.execute(Action(type="WriteFile", args={"path": "a.py", "content": "x"}), ws)
        wt.execute(Action(type="WriteFile", args={"path": "b.py", "content": "y"}), ws)
        lt = ListFilesTool()
        result = lt.execute(Action(type="ListFiles", args={"pattern": "*.py"}), ws)
        assert result.success
        files = result.output.strip().split("\n")
        assert set(files) == {"a.py", "b.py"}


def test_path_traversal_prefix_confusion_blocked():
    # cwd is a directory whose name is a prefix of a sibling directory.
    # Old startswith-based check would let ../foobar/x slip through because
    # "/tmp/foo" is a string prefix of "/tmp/foobar/x".
    with tempfile.TemporaryDirectory() as base:
        cwd = os.path.join(base, "foo")
        sibling = os.path.join(base, "foobar")
        os.makedirs(cwd)
        os.makedirs(sibling)
        secret = os.path.join(sibling, "secret.txt")
        with open(secret, "w") as f:
            f.write("private")
        ws = Workspace(cwd=cwd)
        rt = ReadFileTool()
        result = rt.execute(Action(type="ReadFile", args={"path": "../foobar/secret.txt"}), ws)
        assert result.success is False
        assert "traversal" in result.error.lower() or "outside" in result.error.lower()


def test_list_files_rejects_outside_workspace():
    # A glob pattern that escapes the workspace must not leak sibling files.
    with tempfile.TemporaryDirectory() as base:
        cwd = os.path.join(base, "foo")
        sibling = os.path.join(base, "foobar")
        os.makedirs(cwd)
        os.makedirs(sibling)
        secret = os.path.join(sibling, "leak.txt")
        with open(secret, "w") as f:
            f.write("private")
        ws = Workspace(cwd=cwd)
        lt = ListFilesTool()
        result = lt.execute(Action(type="ListFiles", args={"pattern": "../foobar/*.txt"}), ws)
        assert result.success
        assert result.output.strip() == ""
