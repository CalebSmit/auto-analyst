"""The look of the three surfaces, in one place.

Three pages that link to each other and look like three different products is worse than
one plain page. This holds the shared vocabulary - colour, type, spacing, the handful of
components each page assembles - so that changing how a card looks changes it everywhere,
and nobody has to notice the two other copies.

No build step, no framework, no CDN. The pages are strings of HTML served from Python, and
this is a string of CSS served with them. That is not a limitation being worked around: a
firm's internal tool that needs npm to render a table is a tool that stops rendering the
year nobody maintains it.
"""

from ui.theme import CSS, SHELL

__all__ = ["CSS", "SHELL"]
