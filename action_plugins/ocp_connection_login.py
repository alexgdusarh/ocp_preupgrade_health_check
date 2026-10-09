# -*- coding: utf-8 -*-
"""Return the play's connection username and password.

An AAP *Machine* credential reaches a job as `ansible-playbook -u <user>`
plus an answered `--ask-pass` prompt: the password only lives in the play's
connection settings, never in a variable, environment variable or file. This
playbook runs against localhost over the API, so it uses that login for the
OpenShift OAuth exchange instead (tasks/00_facts.yml, password method).

Always register the result with no_log: true - it carries the password.
"""
from __future__ import annotations

from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    _requires_connection = False

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        pc = self._play_context
        result.update(
            changed=False,
            username=str(getattr(pc, "remote_user", "") or ""),
            password=str(getattr(pc, "password", "") or ""),
        )
        return result
