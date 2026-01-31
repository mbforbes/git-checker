"""Warning: these tests are AI-written. Better than nothing (right? right???)."""

import unittest
import os
import shutil
import tempfile
import subprocess as sp

# Import the logic to be tested
from checker import check_git_dir


class TestGitChecker(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _create_repo(self, name: str) -> str:
        repo_path = os.path.join(self.test_dir, name)
        os.makedirs(repo_path)
        sp.check_call(
            ["git", "init"], cwd=repo_path, stdout=sp.DEVNULL, stderr=sp.DEVNULL
        )
        # Configure user for commits
        sp.check_call(
            ["git", "config", "user.email", "you@example.com"],
            cwd=repo_path,
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )
        sp.check_call(
            ["git", "config", "user.name", "Your Name"],
            cwd=repo_path,
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )
        return repo_path

    def _run_git(self, repo_path: str, args: list):
        sp.check_call(
            ["git"] + args, cwd=repo_path, stdout=sp.DEVNULL, stderr=sp.DEVNULL
        )

    def test_empty_repo(self):
        """
        Scenario: Empty repo (git init).
        Expectation: Not dirty, no unpushed branches.
        User confirmed: "a no-commit repo with no files is fine"
        """
        path = self._create_repo("empty")
        status = check_git_dir(path)
        self.assertFalse(status.dirty, "Empty repo should not be dirty")
        self.assertEqual(
            status.unpushed_branches, [], "Empty repo has no branches to be unpushed"
        )

    def test_untracked_file(self):
        """
        Scenario: Untracked file.
        Expectation: Dirty = True.
        """
        path = self._create_repo("untracked")
        with open(os.path.join(path, "foo.txt"), "w") as f:
            f.write("content")

        status = check_git_dir(path)
        self.assertTrue(status.dirty, "Untracked file should make repo dirty")

    def test_staged_file(self):
        """
        Scenario: Staged file, no commit.
        Expectation: Dirty = True.
        """
        path = self._create_repo("staged")
        with open(os.path.join(path, "foo.txt"), "w") as f:
            f.write("content")
        self._run_git(path, ["add", "foo.txt"])

        status = check_git_dir(path)
        self.assertTrue(status.dirty, "Staged file should make repo dirty")

    def test_committed_local_only(self):
        """
        Scenario: Committed files, but no remote configured.
        Expectation: Not dirty. Unpushed branches?
        The current logic only checks branches with a configured remote.
        So a local-only repo is considered 'clean' / no action needed by this tool.
        """
        path = self._create_repo("local_only")
        with open(os.path.join(path, "foo.txt"), "w") as f:
            f.write("content")
        self._run_git(path, ["add", "foo.txt"])
        self._run_git(path, ["commit", "-m", "initial"])

        status = check_git_dir(path)
        self.assertFalse(status.dirty, "Clean working tree")
        self.assertEqual(
            status.unpushed_branches,
            [],
            "No remote configured, so no unpushed branches reported",
        )

    def test_modified_file(self):
        """
        Scenario: Modified file after commit.
        Expectation: Dirty = True.
        """
        path = self._create_repo("modified")
        with open(os.path.join(path, "foo.txt"), "w") as f:
            f.write("content")
        self._run_git(path, ["add", "foo.txt"])
        self._run_git(path, ["commit", "-m", "initial"])

        with open(os.path.join(path, "foo.txt"), "w") as f:
            f.write("changed")

        status = check_git_dir(path)
        self.assertTrue(status.dirty, "Modified file should make repo dirty")

    def test_upstream_sync(self):
        """
        Scenario: Remote exists.
        1. Fully synced -> Clean.
        2. Local ahead -> Unpushed.
        """
        # Create "remote" repo (bare)
        remote_path = os.path.join(self.test_dir, "remote.git")
        os.makedirs(remote_path)
        sp.check_call(
            ["git", "init", "--bare"],
            cwd=remote_path,
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )

        # Create local repo and push initial
        local_path = self._create_repo("local")
        self._run_git(local_path, ["remote", "add", "origin", remote_path])

        with open(os.path.join(local_path, "f1"), "w") as f:
            f.write("1")
        self._run_git(local_path, ["add", "f1"])
        self._run_git(local_path, ["commit", "-m", "c1"])
        self._run_git(local_path, ["push", "-u", "origin", "main"])

        # Case 1: Synced
        status = check_git_dir(local_path)
        self.assertFalse(status.dirty)
        self.assertEqual(status.unpushed_branches, [])

        # Case 2: Ahead (Unpushed)
        with open(os.path.join(local_path, "f2"), "w") as f:
            f.write("2")
        self._run_git(local_path, ["add", "f2"])
        self._run_git(local_path, ["commit", "-m", "c2"])

        status = check_git_dir(local_path)
        self.assertFalse(status.dirty, "Working tree is clean")
        self.assertEqual(
            len(status.unpushed_branches), 1, "Should report unpushed branch"
        )
        self.assertIn(
            local_path, status.unpushed_branches[0], "Should report the repo path"
        )

    def test_detached_head(self):
        """
        Scenario: Detached HEAD.
        Expectation: Clean (if no mods), no unpushed branches (no remote config).
        """
        path = self._create_repo("detached")
        with open(os.path.join(path, "f1"), "w") as f:
            f.write("1")
        self._run_git(path, ["add", "f1"])
        self._run_git(path, ["commit", "-m", "c1"])

        # Detach
        p = sp.Popen(
            ["git", "rev-parse", "HEAD"],
            stdout=sp.PIPE,
            cwd=path,
            universal_newlines=True,
        )
        head_hash = p.communicate()[0].strip()
        self._run_git(path, ["checkout", head_hash])

        status = check_git_dir(path)
        self.assertFalse(status.dirty, "Detached HEAD should be clean")
        self.assertEqual(
            status.unpushed_branches,
            [],
            "Detached HEAD has no configured remote branch",
        )

    def test_dirty_and_unpushed(self):
        """
        Scenario: Repo is both ahead of remote AND has dirty working directory.
        Expectation: Dirty=True AND Unpushed=[...]
        """
        # Create remote
        remote_path = os.path.join(self.test_dir, "remote.git")
        os.makedirs(remote_path)
        sp.check_call(
            ["git", "init", "--bare"],
            cwd=remote_path,
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )

        # Local setup
        local_path = self._create_repo("local_combo")
        self._run_git(local_path, ["remote", "add", "origin", remote_path])

        # Initial push
        with open(os.path.join(local_path, "f1"), "w") as f:
            f.write("1")
        self._run_git(local_path, ["add", "f1"])
        self._run_git(local_path, ["commit", "-m", "c1"])
        self._run_git(local_path, ["push", "-u", "origin", "main"])

        # Make unpushed commit
        with open(os.path.join(local_path, "f2"), "w") as f:
            f.write("2")
        self._run_git(local_path, ["add", "f2"])
        self._run_git(local_path, ["commit", "-m", "c2"])

        # Make dirty file
        with open(os.path.join(local_path, "f3"), "w") as f:
            f.write("dirty")

        # Check status
        status = check_git_dir(local_path)

        self.assertTrue(status.dirty, "Should be dirty")
        self.assertEqual(
            len(status.unpushed_branches), 1, "Should have unpushed branch"
        )

    def test_fail_on_short_status_config(self):
        """
        Scenario: User has `git config status.short true` set.
        This causes `git status` (clean) to output NOTHING.
        Current implementation: Crashes in status_clean (IndexError).
        Robust implementation (--porcelain): Handles empty output correctly (Clean).
        """
        path = self._create_repo("short_status")
        # Set config to output short format
        self._run_git(path, ["config", "status.short", "true"])

        # Commit a file to make it a valid clean repo
        with open(os.path.join(path, "f1"), "w") as f:
            f.write("1")
        self._run_git(path, ["add", "f1"])
        self._run_git(path, ["commit", "-m", "c1"])

        # This currently crashes!
        status = check_git_dir(path)
        self.assertFalse(
            status.dirty,
            "Should handle 'status.short=true' on clean repo without crashing",
        )


if __name__ == "__main__":
    unittest.main()

if __name__ == "__main__":
    unittest.main()
