# AAP setup for the health check (`aap/configure.yaml`)

A standalone playbook that creates, in Ansible Automation Platform (AAP) 2.4,
everything needed to run the OpenShift pre-upgrade health check as a job:

| Object | Name (default) | What it is |
| --- | --- | --- |
| Project | `OCP pre-upgrade health check` | Pulls this git repository; updates on every launch |
| Inventory | `OCP pre-upgrade health check - localhost` | One host, `localhost` - the playbook talks to clusters over their API, not SSH |
| Job template | `OCP pre-upgrade health check` | Runs `playbook.yml` in the chosen execution environment, with the survey below |

It is independent of the health check itself: it only talks to the AAP API,
never to an OpenShift cluster. Running it again updates the same objects
(matched by name) instead of creating duplicates.

## The survey users see at launch

| Question | Variable | Type | Notes |
| --- | --- | --- | --- |
| Cluster | `ocp_api_host` | Multiple choice | The API URLs listed in `aap_clusters` |
| OpenShift username | `ocp_username` | Text, optional | Blank = log in as the AAP user who launched the job (`awx_user_name`) |
| OpenShift password | `ocp_password` | Password | Stored encrypted, shown as `$encrypted$`; exchanged once for an OAuth token, which is revoked at the end of the run |
| Upgrade channel | `upgrade_channel` | Multiple choice | `eus`, `stable`, `fast` (default `eus`) |
| Target version | `upgrade_target_version` | Text, optional | Exact `x.y.z`, e.g. `4.20.34`; blank = the channel's latest |
| Options | `survey_options` | Multi-select, optional | Plain-language switches, see below; "Skip ODF checks" is ticked by default |
| Advanced settings | `survey_advanced` | Text box, optional | `name: value` lines for a few allowlisted thresholds, see below |

### Options

Each ticked option sets variables for that run only:

| Option | Sets |
| --- | --- |
| Skip Portworx checks | `portworx_enabled: false` |
| Skip OpenShift Virtualization checks | `cnv_enabled: false` |
| Skip ODF checks (ticked by default) | `odf_enabled: false` |
| Skip CRD finalizer scan (faster) | `finalizer_scan_include_crs: false` |
| Don't fail the job on CRITICAL | `fail_on_critical: false` |
| ACM hub: check hub and managed clusters | `acm_enabled: true` |

### Advanced settings

One `name: value` per line, for example:

```yaml
finalizer_scan_stuck_after_seconds: 1800
etcd_db_warn_pct: 0.7
```

Only these names are accepted: `etcd_quota_bytes`, `etcd_db_warn_pct`,
`etcd_db_crit_pct`, `etcd_took_warn_ms`, `etcd_took_crit_ms`,
`finalizer_scan_stuck_after_seconds`, `api_report_min_requests`,
`upgrade_path_timeout`. Values must be numbers above 0 (`*_pct` between 0
and 1). Anything else - a different variable, a typo, text instead of a
number - stops the job at the start with a message naming the problem, so
the box can't change the cluster, the login or certificate checks.

Both lists live in `group_vars/all.yml` (`survey_option_flags`,
`survey_option_defaults`, `survey_advanced_allowlist`): edit them there and
re-run this playbook to update the survey. Whatever was chosen is listed in
the report as an INFO finding ("Run options").

AAP surveys can't show a question only when another answer is picked, so
both questions are always visible; leaving them as they are runs the
default checks.

Every launch also gets the fixed extra vars in `aap_job_extra_vars`
(`ocp_auth_method: password`, `ocp_validate_certs: true`).

After a run, the job's **Artifacts** (Details page) hold the summary under
`ocp_preupgrade_health.<cluster>`: overall status, counts, versions and the
CRITICAL findings.

## Prerequisites

- **AAP 2.4** with an existing **organization**, reachable over HTTPS from
  where you run this playbook.
- **An AAP OAuth token** for a user who is admin of that organization:
  AAP UI > Users > *your user* > Tokens > Add, scope **Write**.
- **The `ansible.controller` or `awx.awx` collection** - the playbook uses
  whichever is installed. `ansible.controller` is already in AAP's
  `ee-supported-rhel8` image (option A below); `awx.awx` is on public Galaxy
  (option B).
- **The git repository URL** AAP will pull from, and - if the repository is
  private - the name of an existing AAP **Source Control** credential.
- **An execution environment registered in AAP.** `Default execution
  environment` (ee-supported-rhel8) has everything the health check needs;
  the custom one in `../execution-environment.yml` is optional.

## 1. Fill in the settings

All settings are in **`aap/vars.yaml`**, which `aap/configure.yaml` loads by
itself. Replace the `CHANGE-ME` placeholders there (in your own repository -
keep real values out of public copies):

```bash
vi aap/vars.yaml
```

| Variable | Replace with |
| --- | --- |
| `aap_organization` | Existing AAP organization, e.g. `CHANGE-ME-organization` |
| `aap_scm_url` | Git URL AAP pulls from, e.g. `https://git.example.com/team/ocp_preupgrade_health_check.git` |
| `aap_scm_branch` | Branch to run (default `main`) |
| `aap_playbook` | Path of the health-check playbook from the repository root: `playbook.yml` (default), or e.g. `automation/openshift/playbook.yaml` when it sits in a folder of a larger repository |
| `aap_scm_credential` | Name of an existing Source Control credential, or `""` for a public repository |
| `aap_execution_environment` | EE name as shown in AAP (default `Default execution environment`) |
| `aap_clusters` | One API URL per cluster, e.g. `https://api.cluster-a.example.com:6443` |
| `aap_upgrade_channels` / `aap_default_upgrade_channel` | Channels offered in the survey, and the default |
| `aap_project_name`, `aap_inventory_name`, `aap_job_template_name` | Object names, if you want others |
| `aap_job_extra_vars` | Extra vars fixed on every launch |

The playbook stops before touching AAP while `aap_organization`,
`aap_scm_url` or `aap_clusters` still contain `CHANGE-ME`, and lists which.
Any setting can also be overridden for one run with `-e`, e.g.
`-e aap_scm_branch=test`.

## 2. Set the connection (environment variables only)

The AAP host and token are read from the environment, never from a file in
the repository. `read -s` keeps the token out of your shell history and off
the screen:

```bash
export CONTROLLER_HOST=https://aap.example.com
read -rsp 'AAP token: ' CONTROLLER_OAUTH_TOKEN; echo; export CONTROLLER_OAUTH_TOKEN
export CONTROLLER_VERIFY_SSL=true   # the default; keep certificate checks on
```

If AAP's certificate is signed by an internal CA, that CA must be trusted
where the playbook runs (the host's trust store, or the EE image).

## 3. Run it

Run from the repository root.

### Option A - inside AAP's execution environment (recommended)

Uses the same image AAP runs jobs in, so `ansible.controller` is already
there. Log in to the registry once (`podman login registry.redhat.io`), then:

```bash
podman run --rm \
  -v "$PWD":/runner/project:Z -w /runner/project \
  -e CONTROLLER_HOST -e CONTROLLER_OAUTH_TOKEN -e CONTROLLER_VERIFY_SSL \
  registry.redhat.io/ansible-automation-platform-24/ee-supported-rhel8:latest \
  ansible-playbook aap/configure.yaml
```

`-e NAME` without a value passes the variable from your shell into the
container, so the token is never written on the command line.

### Option B - with a local Ansible

```bash
ansible-galaxy collection install awx.awx
ansible-playbook aap/configure.yaml
```

`awx.awx` has the same modules as `ansible.controller`; the playbook finds
either one.

### When you're done

```bash
unset CONTROLLER_OAUTH_TOKEN
```

## 4. Check the result

1. **Resources > Projects**: the project's last sync is **Successful**. A
   failed sync usually means a wrong `aap_scm_url`, branch or Source Control
   credential.
2. **Resources > Templates**: open the job template, **Launch**, and the
   survey above appears. Pick a cluster and enter an OpenShift password.
3. When the job finishes, **Details > Artifacts** shows the
   `ocp_preupgrade_health` summary. The report files themselves are not
   kept after the job yet (see `../execution-environment.txt`, section 6).

## When the project is a folder in a larger repository

AAP has no separate folder setting: the job template's playbook is a path
from the repository root, which `aap_playbook` sets (AAP's playbook list
shows playbooks in subfolders too). AAP runs from the repository root, so
the folder's `ansible.cfg` is ignored; the playbook doesn't need it -
`filter_plugins/`, `group_vars/` and `templates/` next to `playbook.yml` are
found on their own. The same applies to `aap/configure.yaml` itself: run it
by its path - it still finds `aap/vars.yaml` next to it, e.g.

```bash
ansible-playbook automation/openshift/aap/configure.yaml
```

## Changing or removing things

- **Change** any setting in `aap/vars.yaml` and run the playbook again;
  existing objects are updated in place, including the survey.
- **Remove** the objects in the AAP UI (job template first, then inventory
  and project); this playbook only creates and updates.

## Troubleshooting

| Message | Cause |
| --- | --- |
| `Set CONTROLLER_HOST and CONTROLLER_OAUTH_TOKEN, and replace the CHANGE-ME values ...` | A variable is not exported, or a placeholder is left (the message names it) |
| `... unknown error when trying to connect to https://...` | `CONTROLLER_HOST` is wrong or not reachable from where the playbook runs (inside a container: from the container) |
| `CERTIFICATE_VERIFY_FAILED` | AAP's CA is not trusted where the playbook runs - add it to the trust store or EE; don't turn verification off |
| A `401` or `403` response | The token expired, was revoked, was created with Read scope, or its user isn't admin of the organization |
| `Request to /api/v2/organizations/?name=... returned 0 items, expected 1` | `aap_organization` doesn't match an existing organization (names are case-sensitive) |
| `Request to /api/v2/execution_environments/?name=... returned 0 items, expected 1` | `aap_execution_environment` doesn't match an EE registered in AAP |
| `couldn't resolve module/action 'project'` | Neither `ansible.controller` nor `awx.awx` is installed - use option A, or install `awx.awx` (option B) |
