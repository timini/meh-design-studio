# Platform validation and application delivery

The target product is a local desktop application, with a headless CLI and Python library exposing the same domain operations. Today the implementation is CLI/library code: there is no completed graphical application or desktop installer. The PRD calls for evaluating reuse of Boundary Lab's desktop workflow before choosing a new UI. Solver and CAD workers must remain isolated from the interface.

## Automated coverage

| Layer | Configured platforms | What this establishes |
| --- | --- | --- |
| Core contracts, catalogue, jobs and available library tests | Linux, macOS, Windows; Python 3.11 and 3.14 | Platform-dependent file, queue, numeric and command behavior |
| CadQuery geometry and Gmsh mesh tests | Linux, macOS, Windows; Python 3.11 | Native CAD dependencies install and geometry tests execute on each hosted runner |
| Real Boundary Lab coupled solves | Local experiments so far; not a full hosted matrix | Integration evidence for the recorded local environment only |
| Packaged desktop application | Not implemented | No installer or desktop-support claim yet |

Matrix jobs do not cancel other operating systems when one fails. Superseded workflow runs are cancelled, and branch pushes do not duplicate pull-request runs. CAD jobs have a 30-minute limit; Linux graphics dependencies are installed only on Linux. These workflows configure checks, not proof that they passed. At the time of this change, GitHub Actions cannot start jobs because of account billing/spending restrictions. Local successes do not replace the missing platform results.

## Required before claiming desktop support

For each supported OS and CPU architecture, record the exact OS, architecture, Python, native CAD libraries, solver revision, Julia runtime and backend. Hosted runner labels alone do not establish coverage of both Intel and ARM Macs or all Windows versions.

1. Install into a clean user account and launch both the CLI and eventual UI, including paths with spaces and non-ASCII characters.
2. Generate a reference horn, export printable material geometry, build the analysis meshes and reopen the exported files. Check geometry invariants and physical tags; compare numeric properties within justified tolerances rather than demanding identical CAD file bytes.
3. Execute the same small coupled CPU solve; verify result integrity and compare complex outputs against a recorded reference with justified tolerances and unchanged source conventions. No amplitude fitting to make platforms agree.
4. Cancel during launch, meshing and solving; test timeouts, crashes and restart. Verify no solver children remain and incomplete results cannot be published.
5. Exercise file permissions, locked files, Unicode paths, source snapshots and reopening projects after application restart.
6. Test the packaged UI separately: worker failure must not close it, progress and cancellation must reflect durable job state, and 3D previews must match exported geometry.

CPU is the first reference backend. GPU backends require separate hardware-specific evidence; a successful CPU run does not qualify them. Physical acoustic accuracy also remains a separate validation gate, irrespective of operating-system coverage.
