# Copyright (C) 2025 Atlas Iris
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

class BaseController:
    def __init__(self, name):
        self.name = name
    
    def receive_message(self, message):
        raise NotImplementedError
    
    def send_message(self, target, message):
        raise NotImplementedError