# Copyright (C) 2025 Atlas Iris
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

# class solution:
#     def generateParenthesis(self, n: int) -> list[str]:
#         ans, sol = [], []

#         def backtracking(openn, close):
#             if len(sol) == 2*n:
#                 ans.append(''.join(sol))
#                 return
            
#             if openn < n:
#                 sol.append('(')
#                 backtracking(openn+1, close)
#                 sol.pop()

#             if openn > close:
#                 sol.append(')')
#                 backtracking(openn, close+1)
#                 sol.pop()
            
#         backtracking(0, 0)
#         return ans