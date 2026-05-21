"""Coordination layer for the SpecBox NativeBackend (multi-developer).

This package lives **outside** the SpecBackend ABC on purpose: identity,
authorization and (in H3) UC claims are concerns of team coordination, not of
the spec-storage abstraction. Keeping them here leaves the three existing
backends (Trello / Plane / FreeForm) untouched.

Modules
-------
- :mod:`identity` — developer model, token hashing, authentication (Frontier 1)
  and project-scoped authorization. (H2: UC-201, UC-202, UC-203.)
- ``claims`` / ``branches`` — UC claim exclusion and branch registry. (H3.)
"""
