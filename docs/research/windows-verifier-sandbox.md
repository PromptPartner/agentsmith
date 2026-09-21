# Windows verifier sandbox options — W2-06

The finite-run verifier accepts an operator-approved command, then runs it with no network and
no writes outside its worktree. The current Windows path returns 126 before executing the command.
That is the correct fail-closed behavior until the same boundary can be enforced on Windows.

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
- [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
  manage and limit process groups. Their documented controls do not by themselves establish the
  required file and network boundary.

## Next implementation gate

Prototype an AppContainer launcher in an isolated Windows fixture. Prove that the approved
verifier can read its inputs and write inside the worktree, while attempts to write a sibling
path or use the network fail. Then run the full graph lifecycle and all native evidence phases
on one committed tree. Until that proof exists, keep exit 126 and the W2-06 aggregate closed.
