# Sourced by every scripts/test-*.sh before anything else. Hooks, `git rebase --exec` and wrappers
# export Git's repository variables; a fixture that inherits them works on that repository instead
# of its own temporary one. Same list as scripts/_fixture_git.py (a test keeps them equal).
unset GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_CONFIG GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT \
  GIT_OBJECT_DIRECTORY GIT_DIR GIT_WORK_TREE GIT_IMPLICIT_WORK_TREE GIT_GRAFT_FILE \
  GIT_INDEX_FILE GIT_NO_REPLACE_OBJECTS GIT_REPLACE_REF_BASE GIT_PREFIX GIT_SHALLOW_FILE \
  GIT_COMMON_DIR GIT_NAMESPACE

for _fixture_git_name in $(env | sed -n 's/^\(GIT_CONFIG_\(KEY\|VALUE\)_[0-9][0-9]*\)=.*/\1/p'); do
  unset "$_fixture_git_name"
done
unset _fixture_git_name
