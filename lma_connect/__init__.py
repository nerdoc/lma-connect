"""LMA Connect — mobile-first conference companion app.

Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc.

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

────────────────────────────────────────────────────────────────────────
Provenance and attribution
────────────────────────────────────────────────────────────────────────

The constants below are the single source of truth for who built this app,
under which licence it may be used and adapted, and where the source code
lives. They are deliberately hard-coded — not event data an organizer can
edit in the admin — because an AGPL deployment must stay traceable back to
its authors no matter whose conference it is branded for.

The footer of every page renders APP_NAME and links to `/about/`, which
prints this same information. That link is also how this deployment
satisfies AGPL §13: users interacting with the app remotely are offered
the source of the version they are running.

If you fork and modify LMA Connect, the licence requires you to keep this
attribution, mark your changes and release your version under the AGPL as
well. Add yourself to the credits — do not remove the original authors.
"""

#: Product name. Hard-coded on purpose: an organizer brands the *event*,
#: never the software underneath it.
APP_NAME = "LMA Connect"

#: Kept in sync with `[project].version` in pyproject.toml.
VERSION = "0.1.0"

#: Who wrote it. Shown on /about/ and in the machine-readable metadata.
AUTHOR = "Janne Cadamuro"
ORGANIZATION = "LabMed Alliance Inc."
COPYRIGHT_HOLDER = f"{AUTHOR} / {ORGANIZATION}"

#: First year of publication — the footer widens this to a range as years pass.
COPYRIGHT_YEAR = 2026

#: SPDX identifier, so tooling (and humans) can read the licence off the code.
LICENSE_SPDX = "AGPL-3.0-or-later"
LICENSE_NAME = "GNU Affero General Public License v3.0 or later"
LICENSE_URL = "https://www.gnu.org/licenses/agpl-3.0.html"

#: Where the source of *this* app lives — required by AGPL §13 for anyone who
#: runs a modified version as a network service. This is the public home of
#: the project; the working repository (`git remote -v`) may differ until the
#: code is published there. §13 is only satisfied once this URL actually
#: serves the source, so it has to go public before the app does.
SOURCE_URL = "https://github.com/labmedalliance/lma-connect"

#: One-line summary, reused by /about/ and the PWA manifest.
DESCRIPTION = (
    "Mobile-first conference companion for scientific and professional events — "
    "program, speakers, live Q&A, polls, abstracts and expo, built with Django and HTMX."
)

__version__ = VERSION
__author__ = COPYRIGHT_HOLDER
__license__ = LICENSE_SPDX
