# Copyright (C) 2025 Atlas Iris
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

class BaseClass:
    """
    Base interface for all algorithms within the PDSNO system.
    Defines the standard lifecycle: initialize → execute → finalize.
    """

    def initialize(self, context: dict):
        """
        Prepare environment and validate input context.

        Parameters:
            context (dict): Configuration and environment data required by the algorithm.
        """
        raise NotImplementedError(
            "The 'initialize' method must be implemented by subclasses."
        )

    def execute(self, data: any):
        """
        Perform the core logic of the algorithm.

        Parameters:
            data (any): Input data to process.
        
        Returns:
            any: Output results or decisions from algorithm execution.
        """
        raise NotImplementedError(
            "The 'execute' method must be implemented by subclasses."
        )

    def finalize(self):
        """
        Perform cleanup, resource release, and return final results if applicable.
        """
        raise NotImplementedError(
            "The 'finalize' method must be implemented by subclasses."
        )
