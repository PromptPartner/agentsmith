# Windows verifier sandbox options — W2-06

The finite-run verifier accepts an operator-approved command, then runs it with no network and
no writes outside its worktree. The Windows branch now attempts a classic AppContainer and returns
126 before the command if the boundary cannot be established. Native proof is still required.

## Platform evidence

- The hosted `windows-latest` runner is Windows Server 2025 in the
  [GitHub runner image list](https://github.com/actions/runner-images/blob/main/README.md).
- Microsoft describes [AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)
  as an operating-system boundary for files, network, processes, and credentials. A launcher would
  need to grant worktree writes and required system reads explicitly, while withholding network
  capabilities. Its child-process behavior must be tested with the actual verifier command.
- Microsoft's [Create Process in Sandbox API](https://learn.microsoft.com/en-us/windows/win32/secauthz/createprocessinsandbox)
  can specify read/write paths and AppContainer network isolation, but is experimental. Its stated
  minimum supported client is Windows 11, so it cannot be assumed available on the hosted Server
  runner without a native probe and support decision.
- Microsoft's [process-container OS matrix](https://github.com/microsoft/mxc/blob/main/docs/process-container/os-version-support.md)
  lists AppContainer with host-side DACL grants as its universal filesystem fallback. Its newer
  `processmodel.dll` tier requires a later enabled OS contract, and its BFS tier is disabled in
  shipping builds. This supports researching the classic AppContainer/DACL path first; it does
  not establish that AgentSmith's verifier works on the hosted runner. The
  [profile creation API](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile)
  is documented for Windows Server 2012 and later.
- [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
  manage and limit process groups. Their documented controls do not by themselves establish the
  required file and network boundary.

## Implemented prototype and remaining gate

`windows_verifier_sandbox.py` creates a unique AppContainer profile per verifier call, grants its
package SID write access to the disposable checker worktree and read access to Git metadata and
the Python/Git toolchains, then starts a Python wrapper with the security-capabilities process
attribute. The wrapper invokes the approved command and writes a UTF-8 result inside the worktree.
A kill-on-close Job Object contains descendants. Cleanup closes the job before removing the
temporary ACL grants and profile. The native test runs an approved Python command that reads an
input and writes inside the worktree while probing a sibling file and a local network listener;
it compares the worktree and Git ACLs before and after. The Microsoft
[launch guide](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer)
defines the process attribute and capability model, and the
[icacls reference](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls)
defines the scoped ACL operations. This description is of the implemented path, not a native
passing claim. The next gate is a passing Windows negative test, full graph lifecycle, and
same-commit/tree Linux, macOS, Windows aggregate.

The first hosted Windows boundary test reached `CreateProcessW` after profile and ACL setup but
returned Windows error 203 (`ERROR_ENVVAR_NOT_FOUND`) on run `35613620432`. The next revision
supplies the profile's `LOCALAPPDATA` path from Microsoft's
[`GetAppContainerFolderPath` API](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-getappcontainerfolderpath)
and
explicit user-profile path variables in the child environment. That is a diagnosis-driven
attempt, not passing boundary evidence; the next native test determines whether the host can
launch the confined process.
