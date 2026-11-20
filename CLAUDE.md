# Claude Project Guidance

Read [AGENTS.md](AGENTS.md) before planning, implementing, or reviewing changes, and use [README.md](README.md) for the user-facing workflow.

## Binding desktop product boundary

This is a **single-user, local academic-writing assistant**, not a general-purpose concurrent agent platform. The supported desktop workflow has **one opened project, one selected conversation, and one executing research turn at a time**. Saved projects and conversations can be switched **sequentially** after the current turn completes or Stop fully settles. Users should resolve pending approvals before starting another turn. Multiple simultaneously active projects, concurrent turns across conversations, and multiple desktop instances sharing the same data are **out of scope**.

Do **not** introduce complex cross-project locks, generalized concurrency orchestration, or a global state controller to solve unsupported parallel usage. Stop, approval resolution, and document operations belonging to the active turn remain valid parts of that **single** workflow. Fix real defects that arise under supported sequential operation (for example failed persistence, Stop retry, approval handling, and crash/restart recovery) with narrow, testable changes rather than enterprise-style mechanisms.

When reviewing a proposed fix, first state whether its triggering scenario is **supported normal use** or **unsupported simultaneous work**. Do not turn the latter into implementation requirements without explicit user approval.
