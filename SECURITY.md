# Security

Retirement Conductor is designed to inspect and eventually change downstream
consumer systems. Until a deployment has passed the security and reliability
phase, use only disposable environments and data.

## Supported development boundary

- Read and plan are the default capabilities.
- Apply requires explicit, target-bound authorization.
- The general campaign process must not hold credentials for destructive
  producer actions.
- Native operations must use documented public interfaces.
- Development and tests must not target production systems.

## Sensitive material

Never commit or include in public artifacts:

- DataHub, Git provider, warehouse, or BI credentials;
- cookies, access tokens, API client secrets, private keys, or session data;
- unrestricted query text or query results;
- private repository content;
- personal or sensitive data;
- raw responses that reveal internal infrastructure or principals.

Use ignored environment files or a deployment secret provider. Logs and
reports must record safe identifiers and redacted summaries.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting for this repository. Include:

- affected version or commit;
- component and capability involved;
- safe reproduction steps;
- potential source, evidence, or credential exposure;
- whether mutation or false readiness is possible;
- suggested containment if known.

Do not open a public issue containing an exploitable sequence, credential, or
sensitive artifact.

## Security properties

The product is expected to preserve:

- no mutation from read-only or plan-only authority;
- exact source and target preconditions before apply;
- no readiness from partial, stale, ambiguous, or tampered evidence;
- no silent success after partial mutation;
- clear separation between integrity digests and trusted provenance;
- resumable safe state after interruption;
- minimum required evidence retention;
- stable audit history for policy decisions.

See [Risk register](docs/RISKS.md) and
[Security and reliability phase](docs/phases/07-security-reliability.md).
