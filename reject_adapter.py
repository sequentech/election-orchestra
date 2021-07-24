# -*- coding: utf-8 -*-

#
# SPDX-FileCopyrightText: 2013-2021 Agora Voting SL <contact@nvotes.com>
#
# SPDX-License-Identifier: AGPL-3.0-only
#
import requests
import ssl
from requests.adapters import HTTPAdapter

class RejectAdapter(HTTPAdapter):
    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        raise Exception('Policy set to reject connection to ' + request.url)