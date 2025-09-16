"""Application version information."""

__all__ = ["__version__"]

# Semantic version of the running application. This is used by the auto-update
# service to determine whether a release in the feed is newer than the current
# build. The value is intentionally defined here instead of importing from
# package metadata to keep the kiosk deployable as a frozen app.
__version__ = "0.9.0"

