# Copyright 2013-2014 Sebastian Kreft
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Functions to get information from git."""

import os.path
import subprocess

import gitlint.utils as utils


def repository_root():
    """Returns the root of the repository as an absolute path."""
    try:
        root = subprocess.check_output(
            ['git', 'rev-parse', '--show-toplevel'],
            stderr=subprocess.STDOUT).strip()
        # Convert to unicode first
        return root.decode('utf-8')
    except subprocess.CalledProcessError:
        return None


def last_commit():
    """Returns the SHA1 of the last commit."""
    try:
        root = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], stderr=subprocess.STDOUT).strip()
        # Convert to unicode first
        return root.decode('utf-8')
    except subprocess.CalledProcessError:
        return None

def commits_head_to_main(master='main') -> list:
    """Returns the list of SHA1 from Head to main."""
    try:
        commits = subprocess.check_output(
            ['git', 'log', 'origin/{}..HEAD'.format(master), '--oneline',
            '--no-merges', "--pretty=%H"], stderr=subprocess.STDOUT).strip()
        # Convert to unicode first
        commits = commits.decode('utf-8').split('\n')
        return commits
    except subprocess.CalledProcessError:
        return []



def _remove_filename_quotes(filename):
    """Removes the quotes from a filename returned by git status."""
    if filename.startswith('"') and filename.endswith('"'):
        return filename[1:-1]

    return filename


def modified_files(root, tracked_only=False, commits=None):
    """Returns a list of files that has been modified since the last commit.

    Args:
      root: the root of the repository, it has to be an absolute path.
      tracked_only: exclude untracked files when True.
      commits: SHA1 of the commits. If None, it will get the modified files in the
        working copy.

    Returns: a dictionary with the modified files as keys, and additional
      information as value. In this case it adds the status returned by
      git status.
    """
    assert os.path.isabs(root), "Root has to be absolute, got: %s" % root

    if commits:
        list_of_modified = {}
        for commit in commits:
            modified_files_commit = _modified_files_with_commit(root, commit)
            #print("Modified files commit", modified_files_commit)
            list_of_modified.update(modified_files_commit)
        return list_of_modified
    # Convert to unicode and split
    status_lines = subprocess.check_output([
        'git', 'status', '--porcelain', '--untracked-files=all',
        '--ignore-submodules=all'
    ]).decode('utf-8').split(os.linesep)

    modes = ['M ', ' M', 'A ', 'AM', 'MM']
    if not tracked_only:
        modes.append(r'\?\?')
    modes_str = '|'.join(modes)

    modified_file_status = utils.filter_lines(
        status_lines,
        r'(?P<mode>%s) (?P<filename>.+)' % modes_str,
        groups=('filename', 'mode'))

    return dict((os.path.join(root, _remove_filename_quotes(filename)), mode)
                for filename, mode in modified_file_status)


def _modified_files_with_commit(root, commit):
    # Convert to unicode and split
    status_lines = subprocess.check_output([
        'git', 'diff-tree', '-r', '--root', '--no-commit-id', '--name-status',
        commit
    ]).decode('utf-8').split(os.linesep)

    modified_file_status = utils.filter_lines(
        status_lines,
        r'(?P<mode>A|M)\s(?P<filename>.+)',
        groups=('filename', 'mode'))

    # We need to add a space to the mode, so to be compatible with the output
    # generated by modified files.
    return dict((os.path.join(root, _remove_filename_quotes(filename)),
                 mode + ' ') for filename, mode in modified_file_status)

def modified_lines_for_pr(filename, extra_data, commits=[]):
    """Returns the lines that have been modifed for the list of commit IDs
    Args:
      filename: the file to check.
      extra_data: is the extra_data returned by modified_files. Additionally, a
        value of None means that the file was not modified.
      commits: the complete sha1 (40 chars) of the commits. Note that specifying
        this value will only work (100%) when commit == last_commit (with
        respect to the currently checked out revision), otherwise, we could miss
        some lines.

    Returns: a list of lines that were modified, or None in case all lines are
      new.
    """
    line_numbers_map = []
    for commit in commits:
        #print(filename, commit)
        result = modified_lines(filename, extra_data, commit=commit)
        #print("Result: ", result)
        if result:
            line_numbers_map = line_numbers_map + result
    #print("Line numbers: ", line_numbers_map)
    return line_numbers_map
    
def modified_lines(filename, extra_data, commit=None):
    """Returns the lines that have been modifed for this file.

    Args:
      filename: the file to check.
      extra_data: is the extra_data returned by modified_files. Additionally, a
        value of None means that the file was not modified.
      commit: the complete sha1 (40 chars) of the commit. Note that specifying
        this value will only work (100%) when commit == last_commit (with
        respect to the currently checked out revision), otherwise, we could miss
        some lines.

    Returns: a list of lines that were modified, or None in case all lines are
      new.
    """
    if extra_data is None:
        return []
    if extra_data not in ('M ', ' M', 'MM'):
        return None

    if commit is None:
        commit = '0' * 40
    commit = commit.encode('utf-8')

    # Split as bytes, as the output may have some non unicode characters.
    blame_lines = subprocess.check_output(
        ['git', 'blame', '--porcelain', filename]).split(
            os.linesep.encode('utf-8'))
    modified_line_numbers = utils.filter_lines(
        blame_lines, commit + br' (?P<line>\d+) (\d+)', groups=('line', ))
    line_numbers = list(map(int, modified_line_numbers))
    return line_numbers if line_numbers else []

