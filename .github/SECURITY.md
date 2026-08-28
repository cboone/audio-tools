# Security Policy

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via GitHub's private vulnerability reporting:

1. Go to the repository's **Security** tab (in the top navigation bar, next to Issues/Pull Requests)
1. Click "Report a vulnerability" in the left sidebar under Advisories
1. Fill out the form with details

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment:** Within 24 hours
- **Initial assessment:** Within 48 hours
- **Resolution target:** Depends on severity, but as soon as possible

### What Qualifies as a Security Issue

- Injection vulnerabilities (SQL, command, template, etc.)
- Sensitive data exposure
- Authentication or authorization bypass
- Path traversal or directory traversal
- Credential exposure risks
- Malicious input in an audio file that leads to code execution or resource exhaustion when a tool parses it

### Out of Scope

- Issues in upstream dependencies such as `numpy`, `scipy`, `soundfile` or `libsndfile` (report to them directly)
- Issues requiring physical access to the machine
- Social engineering attacks
